"""CatBoost models: will an auction sell, and what will a watch sell for.

Both models are validated with five-fold cross-validation grouped by seller, so no
seller appears in both the training and the validation folds. SHAP values come from
CatBoost's exact TreeSHAP implementation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor, Pool
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import TZ
from . import data as D

SEED = 43
N_SPLITS = 5
CB_PARAMS = dict(iterations=600, learning_rate=0.03, depth=4, l2_leaf_reg=5, random_seed=SEED, verbose=0,
                 allow_writing_files=False, thread_count=4)
# the auction sample is small (525 rows), so the classifier uses shallow trees and fewer rounds
SALE_PARAMS = dict(CB_PARAMS, iterations=200, depth=2, l2_leaf_reg=10)

LABELS = {
    "model": "Model", "condition_group": "Condition", "start_vs_market": "Opening price vs market",
    "best_offer_enabled": "Best Offer", "auction_with_bin": "Buy It Now option", "has_reserve": "Reserve price",
    "free_shipping": "Free shipping", "shipping_cost": "Shipping cost", "seller_feedback_score": "Seller feedback score",
    "seller_feedback_pct": "Seller positive feedback %", "top_rated_buying": "Top Rated Plus",
    "returns_accepted": "Returns accepted", "image_count": "Photos", "duration_days": "Auction length (days)",
    "end_hour": "End hour (MT)", "end_weekend": "Ends on a weekend", "case_size": "Case size (mm)",
    "cellular": "Cellular", "seller_listings": "Seller's listings", "format": "Format", "material": "Case material",
    "hermes": "Hermès", "premium_band": "Premium band", "titanium": "Titanium", "detail": "Full item details",
    "us_location": "Ships from US",
}


def _market_reference() -> tuple[pd.Series, pd.Series]:
    """Median fixed-price sale by model x condition (and by model as a fallback). Auction outcomes are not used."""
    s = D.sold_watches()
    s = s[s["is_auction"] == 0]
    return s.groupby(["model", "condition_group"])["final_price"].median(), s.groupby("model")["final_price"].median()


def market_value(model: pd.Series, cond: pd.Series) -> pd.Series:
    by_mc, by_m = _market_reference()
    v = [by_mc.get((m, c), np.nan) for m, c in zip(model, cond)]
    return pd.Series(v, index=model.index).fillna(model.map(by_m))


def _cat(df, cols):
    for c in cols:
        df[c] = df[c].astype(object).where(df[c].notna(), "NA").astype(str)
    return df


# ------------------------------------------------------------------ sale probability (auctions)

SALE_CAT = ["model", "condition_group", "free_shipping", "end_weekend"]
# Best Offer and Buy It Now flags are left out: the collector stores the latest buying options, and eBay
# removes both from an auction once it receives a bid, so the flags would reveal the outcome. The seller's
# listing count is left out because unsold auctions are often relisted, which raises the count.
SALE_NUM = ["start_vs_market", "has_reserve", "shipping_cost", "seller_feedback_score", "seller_feedback_pct",
            "top_rated_buying", "returns_accepted", "image_count", "duration_days", "end_hour", "case_size",
            "cellular"]


def sale_frame() -> pd.DataFrame:
    """Ended auctions first observed before their first bid, so the opening price is known."""
    a = D.ended_auctions()
    a = a[a["first_bid_count"] == 0].copy()
    a["market"] = market_value(a["model"], a["condition_group"])
    a["start_vs_market"] = a["price_first_obs"] / a["market"]
    a["duration_days"] = ((a["ended_at"] - a["start_time"]).dt.total_seconds() / 86400).round(1)
    loc = a["ended_at"].dt.tz_convert(TZ)
    a["end_hour"] = loc.dt.hour
    a["end_weekend"] = np.where(loc.dt.dayofweek >= 5, "yes", "no")
    a["free_shipping"] = a["free_shipping"].map({True: "yes", False: "no"})
    for c in ["has_reserve"]:
        a[c] = a[c].astype(int)
    return a.reset_index(drop=True)


def _sale_X(a):
    X = a[SALE_CAT + SALE_NUM].copy()
    return _cat(X, SALE_CAT)


def _logit_baseline():
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), SALE_CAT),
        ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), SALE_NUM)])
    return make_pipeline(pre, LogisticRegression(C=0.5, max_iter=2000))


def boot_auc(y, p, n_boot=2000, seed=SEED):
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    out = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() != y[i].max():
            out.append(roc_auc_score(y[i], p[i]))
    return tuple(np.quantile(out, [0.025, 0.975]))


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def calibrate(p, ab):
    """Apply Platt scaling (slope, intercept) on the logit scale."""
    a, b = ab
    return 1 / (1 + np.exp(-(a * _logit(p) + b)))


def reliability(y, p, bins=5):
    q = pd.qcut(p, bins, duplicates="drop")
    t = pd.DataFrame({"y": y, "p": p, "bin": q}).groupby("bin", observed=True).agg(
        predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size")).reset_index(drop=True)
    from .stats import wilson
    ci = [wilson(int(round(o * n)), n) for o, n in zip(t["observed"], t["n"])]
    t["lo"], t["hi"] = [c[0] for c in ci], [c[1] for c in ci]
    return t


def calibration_fit(y, p):
    """Calibration intercept and slope from a logistic regression of y on logit(p)."""
    import statsmodels.api as sm
    m = sm.Logit(y, sm.add_constant(_logit(p))).fit(disp=0)
    return dict(intercept=float(m.params[0]), slope=float(m.params[1]))


def fit_sale_model() -> dict:
    a = sale_frame()
    X, y, g = _sale_X(a), a["sold"].values, a["seller"].values
    oof_cb, oof_lr = np.zeros(len(a)), np.zeros(len(a))
    cv = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    folds = []
    oof_cal = np.zeros(len(a))
    for k, (tr, te) in enumerate(cv.split(X, y, g)):
        m = CatBoostClassifier(**SALE_PARAMS, cat_features=SALE_CAT)
        m.fit(X.iloc[tr], y[tr])
        oof_cb[te] = m.predict_proba(X.iloc[te])[:, 1]
        # Platt scaling fitted on inner out-of-fold predictions from the training folds only
        inner = np.zeros(len(tr))
        icv = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED + k)
        for itr, ite in icv.split(X.iloc[tr], y[tr], g[tr]):
            im = CatBoostClassifier(**SALE_PARAMS, cat_features=SALE_CAT).fit(X.iloc[tr].iloc[itr], y[tr][itr])
            inner[ite] = im.predict_proba(X.iloc[tr].iloc[ite])[:, 1]
        platt = LogisticRegression(C=1e6).fit(_logit(inner)[:, None], y[tr])
        oof_cal[te] = platt.predict_proba(_logit(oof_cb[te])[:, None])[:, 1]
        lr = _logit_baseline().fit(X.iloc[tr], y[tr])
        oof_lr[te] = lr.predict_proba(X.iloc[te])[:, 1]
        folds.append(roc_auc_score(y[te], oof_cb[te]))
    base = np.full(len(a), y.mean())
    metrics = dict(
        n=len(a), events=int(y.sum()), base_rate=float(y.mean()), sellers=int(pd.Series(g).nunique()),
        auc=float(roc_auc_score(y, oof_cb)), auc_ci=boot_auc(y, oof_cb), auc_folds=[float(f) for f in folds],
        auc_logit=float(roc_auc_score(y, oof_lr)), auc_logit_ci=boot_auc(y, oof_lr),
        brier=float(brier_score_loss(y, oof_cb)), brier_cal=float(brier_score_loss(y, oof_cal)),
        calibration_cal=calibration_fit(y, oof_cal), auc_cal=float(roc_auc_score(y, oof_cal)), brier_logit=float(brier_score_loss(y, oof_lr)),
        brier_base=float(brier_score_loss(y, base)), logloss=float(log_loss(y, oof_cb)),
        calibration=calibration_fit(y, oof_cb))
    final = CatBoostClassifier(**SALE_PARAMS, cat_features=SALE_CAT).fit(X, y)
    platt = LogisticRegression(C=1e6).fit(_logit(oof_cb)[:, None], y)
    platt_ab = (float(platt.coef_[0, 0]), float(platt.intercept_[0]))
    shap = final.get_feature_importance(Pool(X, y, cat_features=SALE_CAT), type="ShapValues")
    sv = pd.DataFrame(shap[:, :-1], columns=X.columns)
    importance = sv.abs().mean().sort_values(ascending=False)
    # partial dependence of the opening-price ratio, holding every other feature at its observed values
    grid = np.array([0.25, 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0, 3.0])
    pd_rows = []
    for r in grid:
        Xg = X.copy()
        Xg["start_vs_market"] = r
        pd_rows.append(dict(ratio=float(r), prob=float(final.predict_proba(Xg)[:, 1].mean())))
    return dict(platt=platt_ab, frame=a, X=X, oof=oof_cb, oof_cal=oof_cal, oof_logit=oof_lr, reliability_cal=reliability(y, oof_cal), metrics=metrics, model=final, shap=sv,
                expected=float(shap[0, -1]), importance=importance, reliability=reliability(y, oof_cb),
                reliability_logit=reliability(y, oof_lr), partial=pd.DataFrame(pd_rows))


# ------------------------------------------------------------------ sold price

PRICE_CAT = ["model", "condition_group", "format", "material", "free_shipping"]
PRICE_NUM = ["case_size", "cellular", "hermes", "premium_band", "titanium", "shipping_cost", "seller_feedback_score",
             "top_rated_buying", "returns_accepted", "image_count", "seller_listings", "us_location", "detail"]


def price_frame() -> pd.DataFrame:
    s = D.sold_watches().copy()
    s["free_shipping"] = s["free_shipping"].map({True: "yes", False: "no"})
    return s.reset_index(drop=True)


def _price_X(s):
    X = s[PRICE_CAT + PRICE_NUM].copy()
    return _cat(X, PRICE_CAT)


def fit_price_model() -> dict:
    s = price_frame()
    X, y, g = _price_X(s), s["final_price"].values, s["seller"].values
    oof, oof_base = np.zeros(len(s)), np.zeros(len(s))
    cv = GroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    for tr, te in cv.split(X, y, g):
        m = CatBoostRegressor(**CB_PARAMS, cat_features=PRICE_CAT, loss_function="RMSE")
        m.fit(X.iloc[tr], y[tr])
        oof[te] = m.predict(X.iloc[te])
        train = s.iloc[tr]
        mc = train.groupby(["model", "condition_group"])["final_price"].median()
        mm = train.groupby("model")["final_price"].median()
        oof_base[te] = [mc.get((a, b), mm.get(a, np.median(y[tr]))) for a, b in
                        zip(s["model"].iloc[te], s["condition_group"].iloc[te])]
    metrics = dict(n=len(s), sellers=int(pd.Series(g).nunique()), r2=float(r2_score(y, oof)),
                   mae=float(mean_absolute_error(y, oof)), median_ae=float(np.median(np.abs(y - oof))),
                   r2_base=float(r2_score(y, oof_base)), mae_base=float(mean_absolute_error(y, oof_base)),
                   mape_median=float(np.median(np.abs(y - oof) / y)))
    final = CatBoostRegressor(**CB_PARAMS, cat_features=PRICE_CAT, loss_function="RMSE").fit(X, y)
    shap = final.get_feature_importance(Pool(X, y, cat_features=PRICE_CAT), type="ShapValues")
    sv = pd.DataFrame(shap[:, :-1], columns=X.columns)
    importance = sv.abs().mean().sort_values(ascending=False)
    fmt = pd.DataFrame({"format": s["format"], "shap": sv["format"]}).groupby("format")["shap"].agg(["mean", "size"])
    return dict(frame=s, X=X, oof=oof, metrics=metrics, model=final, shap=sv, expected=float(shap[0, -1]),
                importance=importance, format_shap=fmt)


def price_grid(fit: dict) -> pd.DataFrame:
    """Predicted sale price for each model x condition x format x shipping, other features at typical values."""
    s, X, m = fit["frame"], fit["X"], fit["model"]
    typical = {c: X[c].median() for c in PRICE_NUM}
    typical["material"] = X["material"].mode().iloc[0]
    rows = []
    for model in sorted(s["model"].unique(), key=D.model_sort_key):
        sub = X[X["model"] == model]
        size = sub["case_size"].median()
        mat = sub["material"].mode().iloc[0]
        for cond in D.COND_ORDER:
            for fmt in D.FORMAT_ORDER:
                for ship in ["yes", "no"]:
                    r = dict(typical, model=model, condition_group=cond, format=fmt, free_shipping=ship,
                             case_size=size, material=mat, cellular=float(sub["cellular"].mean() >= 0.5),
                             titanium=float(sub["titanium"].mean() >= 0.5))
                    rows.append(r)
    G = pd.DataFrame(rows)[X.columns]
    G["pred"] = m.predict(G)
    sv = m.get_feature_importance(Pool(G[X.columns], cat_features=PRICE_CAT), type="ShapValues")[:, :-1]
    counts = s.groupby(["model", "condition_group"]).size()
    G["n_sold"] = [int(counts.get((a, b), 0)) for a, b in zip(G["model"], G["condition_group"])]
    out = G[["model", "condition_group", "format", "free_shipping", "material", "case_size", "cellular", "titanium", "pred",
             "n_sold"]]
    shap = pd.DataFrame(sv, columns=[f"shap_{c}" for c in X.columns])
    return pd.concat([out.reset_index(drop=True), shap], axis=1)


def sale_grid(fit: dict) -> pd.DataFrame:
    """Predicted auction sale probability across models, conditions, opening-price ratios and options."""
    X, m = fit["X"], fit["model"]
    typical = {c: X[c].median() for c in SALE_NUM}
    rows = []
    for model in sorted(X["model"].unique(), key=D.model_sort_key):
        sub = X[X["model"] == model]
        for cond in [c for c in D.COND_ORDER if c != "Refurbished"]:
            for ratio in [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
                for ship in ["yes", "no"]:
                    for fb in [5, 50, 500, 5000, 50000]:
                        rows.append(dict(typical, model=model, condition_group=cond, start_vs_market=ratio,
                                         free_shipping=ship, seller_feedback_score=fb, end_weekend="no",
                                         case_size=sub["case_size"].median()))
    G = pd.DataFrame(rows)[X.columns]
    G["prob"] = m.predict_proba(G)[:, 1]
    return G[["model", "condition_group", "start_vs_market", "free_shipping", "seller_feedback_score", "prob"]]
