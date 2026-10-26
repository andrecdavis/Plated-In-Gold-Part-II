"""Descriptive analysis and statistical tests behind every number in the README."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test

from . import PUBLIC_DIR
from . import data as D
from .stats import boot_ci, boot_ratio_ci, rate_table, trend_test, two_prop, wilson

TRAJ_BINS = [0, 0.25, 1, 3, 6, 12, 24, 48, 72, np.inf]
TRAJ_LABELS = ["0–15 min", "15 min–1 h", "1–3 h", "3–6 h", "6–12 h", "12–24 h", "24–48 h", "48–72 h", "72 h+"]
PRICE_POS_BINS = [0, 0.9, 1.1, 1.5, np.inf]
PRICE_POS_LABELS = ["Below 90%", "90–110%", "110–150%", "Above 150%"]


# ------------------------------------------------------------------ overview

def overview() -> dict:
    s = D.summary()
    d = D.listings()
    w = D.watches()
    start, end = D.window()
    gaps = D.gaps()
    hours = (end - start).total_seconds() / 3600
    return dict(
        listings=s["listings"], snapshots=s["snapshots"], outcomes=s["outcomes"], api_calls=s["api_calls"],
        api_calls_by_kind=s["api_calls_by_kind"], api_status=s["api_status"], sweeps=s["sweeps"],
        sweep_items_min=min(s["sweep_items"]), sweep_items_max=max(s["sweep_items"]),
        snapshots_by_source=s["snapshots_by_source"], outcomes_by=s["outcomes_by"],
        start=s["first_observation"], end=s["last_observation"], window_hours=hours,
        gap_hours=float(gaps["hours"].sum()), covered_share=1 - float(gaps["hours"].sum()) / hours,
        sellers=s["sellers"], detail_share=s["detail_share"], brand_missing_share=s["brand_missing_share"],
        outcome_counts=d["outcome"].value_counts().to_dict(),
        format_counts=d["format"].value_counts().to_dict(),
        single_watch=int(d["is_single_watch"].sum()), analysis_listings=int(len(w)),
        lots=int(d["is_lot"].sum()), accessories=int(d["is_accessory"].sum()), other=int(d["is_other"].sum()),
        no_model=int((d["is_single_watch"] & d["model"].isna()).sum()),
        price_outliers=int((d["is_single_watch"] & d["price_outlier"]).sum()),
        gold=int(d["gold"].sum()),
        bin_sales_reclassified=int(((d["is_auction"] == 1) & (d["outcome"] == "sold") & (d["final_bids"].fillna(0) == 0)).sum()),
    )


# ------------------------------------------------------------------ asking vs sold

def ask_vs_sold(condition: str | None = "Used", min_sold: int = 10) -> pd.DataFrame:
    w = D.watches()
    sold = D.sold_watches()
    act = w[w["outcome"] == "active"]
    if condition:
        act, sold = act[act["condition_group"] == condition], sold[sold["condition_group"] == condition]
    rows = []
    for m in D.MODEL_ORDER:
        a, s = act.loc[act["model"] == m, "price"], sold.loc[sold["model"] == m, "final_price"]
        if len(s) < min_sold or len(a) < min_sold:
            continue
        lo, hi = boot_ratio_ci(a, s)
        slo, shi = boot_ci(s)
        rows.append(dict(model=m, n_ask=len(a), n_sold=len(s), ask=a.median(), sold=s.median(), sold_lo=slo,
                         sold_hi=shi, ratio=a.median() / s.median(), ratio_lo=lo, ratio_hi=hi))
    return pd.DataFrame(rows)


def part1_bridge() -> pd.DataFrame:
    p1 = pd.read_csv(PUBLIC_DIR / "part1_model_prices.csv")
    sold = D.sold_watches()
    act = D.watches().query("outcome == 'active'")
    s = sold.groupby("model")["final_price"].agg(part2_median_sold="median", part2_n_sold="size")
    a = act.groupby("model")["price"].agg(part2_median_ask="median", part2_n_ask="size")
    out = p1.merge(s, on="model", how="left").merge(a, on="model", how="left")
    out["order"] = out["model"].map(D.model_sort_key)
    return out.sort_values("part1_mean_ask", ascending=False).drop(columns="order").reset_index(drop=True)


# ------------------------------------------------------------------ gold

def gold() -> dict:
    d = D.listings()
    g = d[d["gold"] == 1].copy()
    w = D.watches()
    sold = D.sold_watches()
    kinds = g["gold_kind"].value_counts().to_dict()
    sellers = g["seller"].value_counts()
    plated = g[(g["gold_kind"] == "Gold-plated watch") & g["model"].notna()].copy()
    base_ask = w[w["outcome"] == "active"].groupby("model")["price"].median()
    base_sold = sold.groupby("model")["final_price"].median()
    plated["ask_ratio"] = plated["price"] / plated["model"].map(base_ask)
    plated["sold_ratio"] = plated["price"] / plated["model"].map(base_sold)
    # comparison group: non-gold fixed-price single watches with full details, listed for a year or more
    fp = d[(d["is_auction"] == 0) & (d["detail"] == 1) & (d["outcome"] == "active") & d["is_single_watch"]]
    old = fp[(fp["gold"] == 0) & (fp["age_years"] >= 1)]
    gd = g[g["detail"] == 1]

    def per_year(x):
        r = x["sold_qty_lifetime"] / x["age_years"].clip(lower=1 / 12)
        return float(r.median())

    by_model = (plated.groupby("model").agg(n=("price", "size"), median_ask=("price", "median"))
                .join(base_ask.rename("plain_ask")).join(base_sold.rename("plain_sold")).reset_index())
    by_model["order"] = by_model["model"].map(D.model_sort_key)
    by_model = by_model.sort_values("order").drop(columns="order")
    # how many sales would comparable non-gold listings have produced in the window? Gold listings are old,
    # long-running fixed-price listings in New or Open box condition, so the comparison group matches on that
    comp = d[(d["gold"] == 0) & d["is_single_watch"] & (d["is_auction"] == 0) & d["model"].isin(plated["model"])
             & d["condition_group"].isin(["New", "Open box"]) & (d["age_years"] >= 1)]
    comp_rate = comp["sold"].mean()
    pricey = comp[comp["price"] >= 500]
    return dict(
        n=int(len(g)), kinds=kinds, ended=int(g["ended"].sum()), sold=int(g["sold"].sum()),
        n_sellers=int(sellers.size), top_seller=int(sellers.iloc[0]), top_seller_share=float(sellers.iloc[0] / len(g)),
        top3_share=float(sellers.iloc[:3].sum() / len(g)), seller_counts=[int(x) for x in sellers.values],
        formats=g["format"].value_counts().to_dict(), gtc_share=float(g["gtc"].mean()),
        conditions=g["condition_group"].value_counts().to_dict(),
        median_ask=float(g["price"].median()), ask_q1=float(g["price"].quantile(.25)), ask_q3=float(g["price"].quantile(.75)),
        min_ask=float(g["price"].min()), max_ask=float(g["price"].max()),
        median_age_years=float(g["age_years"].median()), age_q1=float(g["age_years"].quantile(.25)),
        age_q3=float(g["age_years"].quantile(.75)), share_older_2y=float((g["age_years"] >= 2).mean()),
        median_ask_ratio=float(plated["ask_ratio"].median()), median_sold_ratio=float(plated["sold_ratio"].median()),
        plated_n=int(len(plated)),
        lifetime_n=int(len(gd)), lifetime_never=float((gd["sold_qty_lifetime"] == 0).mean()),
        lifetime_median=float(gd["sold_qty_lifetime"].median()), lifetime_total=int(gd["sold_qty_lifetime"].sum()),
        lifetime_per_year_median=per_year(gd),
        comp_n=int(len(old)), comp_never=float((old["sold_qty_lifetime"] == 0).mean()),
        comp_per_year_median=per_year(old), comp_median_age=float(old["age_years"].median()),
        comp_median_ask=float(old["price"].median()),
        window_comp_rate=float(comp_rate), window_comp_n=int(len(comp)),
        window_expected=float(comp_rate * len(plated)),
        window_p_zero=float((1 - comp_rate) ** len(plated)),
        window_pricey_n=int(len(pricey)), window_pricey_k=int(pricey["sold"].sum()),
        models=plated["model"].value_counts().to_dict(),
        by_model=by_model, plated=plated,
        multi_qty_share=float((gd["available_qty"] > 1).mean()),
    )


# ------------------------------------------------------------------ what sells (auctions)

def auction_rates() -> dict:
    a = D.ended_auctions()
    k, n = int(a["sold"].sum()), len(a)
    by_model = rate_table(a, "model").reset_index().rename(columns={"by": "model"})
    by_model["order"] = by_model["model"].map(D.model_sort_key)
    by_model = by_model.sort_values("order").drop(columns="order")
    fam = rate_table(a, "family").reset_index().rename(columns={"by": "family"})
    new_gen = a[a["model"].isin(["Series 9", "Series 10"])]
    s3 = a[a["model"] == "Series 3"]
    ship = a.dropna(subset=["free_shipping"])
    fs = ship[ship["free_shipping"].astype(bool)]
    ps = ship[~ship["free_shipping"].astype(bool)]
    fb = rate_table(a.dropna(subset=["feedback_bin"]), "feedback_bin").reset_index().rename(columns={"by": "feedback"})
    a["fb_score"] = a["feedback_bin"].cat.codes.replace(-1, np.nan)
    sl = rate_table(a, pd.cut(a["seller_listings"], [0, 1, 3, 10, np.inf], labels=["1", "2–3", "4–10", "11+"])) \
        .reset_index().rename(columns={"by": "seller_listings"})
    bo = a[a["best_offer_enabled"] == 1]
    nbo = a[a["best_offer_enabled"] == 0]
    cond = rate_table(a, "condition_group").reset_index().rename(columns={"by": "condition"})
    # adjusted effects: logistic regression with model-family and condition controls
    m = a.dropna(subset=["free_shipping", "seller_feedback_score"]).copy()
    m["free"] = m["free_shipping"].astype(bool).astype(int)
    m["log_fb"] = np.log10(m["seller_feedback_score"].clip(lower=0) + 1)
    m["bo"] = m["best_offer_enabled"]
    m["new_gen"] = m["model"].isin(["Series 9", "Series 10", "Series 11", "Series 12", "SE 3", "Ultra 2", "Ultra 3", "Ultra 4"]).astype(int)
    fit = smf.logit("sold ~ free + log_fb + C(condition_group) + C(family) + new_gen", data=m).fit(disp=0, maxiter=200)
    ci = fit.conf_int()
    adj = {v: dict(or_=float(np.exp(fit.params[v])), lo=float(np.exp(ci.loc[v, 0])), hi=float(np.exp(ci.loc[v, 1])),
                   p=float(fit.pvalues[v])) for v in ["free", "log_fb", "new_gen"]}
    return dict(
        n=n, k=k, rate=k / n, ci=wilson(k, n), by_model=by_model, by_family=fam, by_feedback=fb, by_condition=cond,
        by_seller_listings=sl,
        new_gen=dict(k=int(new_gen["sold"].sum()), n=len(new_gen), ci=wilson(int(new_gen["sold"].sum()), len(new_gen))),
        series3=dict(k=int(s3["sold"].sum()), n=len(s3), ci=wilson(int(s3["sold"].sum()), len(s3))),
        new_vs_s3=two_prop(new_gen["sold"].sum(), len(new_gen), s3["sold"].sum(), len(s3)),
        free_shipping=two_prop(fs["sold"].sum(), len(fs), ps["sold"].sum(), len(ps)),
        feedback_trend=trend_test(a, "fb_score", "sold"),
        # eBay removes Best Offer and Buy It Now from an auction once it gets a bid, and the collector keeps the
        # latest buying options, so these flags mostly mark auctions that never received a bid
        leak_best_offer=two_prop(bo["sold"].sum(), len(bo), nbo["sold"].sum(), len(nbo)),
        leak_best_offer_mean_bids=float(bo["final_bids"].mean()),
        adjusted=adj, adjusted_n=int(fit.nobs),
        reserve=dict(n=int(a["has_reserve"].sum()), k=int(a.loc[a["has_reserve"], "sold"].sum())),
        leak_bin=two_prop(a.loc[a.auction_with_bin == 1, "sold"].sum(), int((a.auction_with_bin == 1).sum()),
                     a.loc[a.auction_with_bin == 0, "sold"].sum(), int((a.auction_with_bin == 0).sum())),
    )


def fixed_price_endings() -> dict:
    """Among fixed-price listings that ended in the window, the share with a recorded sale (a lower bound)."""
    w = D.watches()
    e = w[(w["is_auction"] == 0) & w["ended"]]
    by_fmt = rate_table(e, "format").reset_index().rename(columns={"by": "format"})
    ship = e.dropna(subset=["free_shipping"]).copy()
    ship["free_shipping"] = ship["free_shipping"].astype(bool)
    return dict(n=len(e), k=int(e["sold"].sum()), rate=float(e["sold"].mean()), by_format=by_fmt,
                free_shipping=two_prop(ship.loc[ship.free_shipping, "sold"].sum(), int(ship.free_shipping.sum()),
                                       ship.loc[~ship.free_shipping, "sold"].sum(), int((~ship.free_shipping).sum())),
                medium_conf=int(((e["sold"] == 1) & (e["outcome_confidence"] == "medium")).sum()))


# ------------------------------------------------------------------ auction dynamics

def auction_trajectories() -> dict:
    a = D.ended_auctions()
    s = a[(a["outcome"] == "sold") & (a["final_price"] > 0)]
    b = D.auction_bids().merge(s[["listing", "final_price", "model"]], on="listing")
    b["pct"] = b["current_bid"] / b["final_price"]
    b["bin"] = pd.cut(b["hours_before_end"], TRAJ_BINS, right=False, labels=TRAJ_LABELS)
    last = b.sort_values("hours_before_end").groupby(["listing", "bin"], observed=True).head(1)
    t = last.groupby("bin", observed=True)["pct"].agg(
        median="median", q1=lambda x: x.quantile(.25), q3=lambda x: x.quantile(.75), n="size").reset_index()
    late = b[b["hours_before_end"] < 0.25].sort_values("hours_before_end").groupby("listing").head(1)
    jump = late["final_price"] / late["current_bid"] - 1
    lo, hi = boot_ci(jump)
    # individual paths for the app: a sample of sold auctions with at least 8 observations
    counts = b.groupby("listing").size()
    keep = counts[counts >= 8].index
    rng = np.random.default_rng(3)
    sample = rng.choice(np.array(keep), size=min(60, len(keep)), replace=False)
    paths = b[b["listing"].isin(sample)][["listing", "model", "hours_before_end", "pct", "current_bid", "bid_count",
                                          "final_price"]]
    early = last[last["bin"] == "48–72 h"]["pct"]
    return dict(table=t, n_auctions=int(b["listing"].nunique()), late_n=int(len(late)),
                late_median_jump=float(jump.median()), late_jump_ci=(lo, hi), late_rose_share=float((jump > 0).mean()),
                at_48_72=float(early.median()), at_1_3=float(t.loc[t["bin"] == "1–3 h", "median"].iloc[0]),
                paths=paths, final_bids_median=float(s["final_bids"].median()))


# ------------------------------------------------------------------ repricing

def repricing() -> dict:
    w = D.watches()
    fp = w[(w["is_auction"] == 0) & (w["n_price_obs"] > 1)]
    changed = fp["price_max_obs"] > fp["price_min_obs"]
    cut = fp["price"] < fp["price_first_obs"]
    raised = fp["price"] > fp["price_first_obs"]
    pct = (fp.loc[cut, "price"] / fp.loc[cut, "price_first_obs"] - 1)
    return dict(n=len(fp), changed=float(changed.mean()), cut=float(cut.mean()), raised=float(raised.mean()),
                median_cut=float(pct.median()))


# ------------------------------------------------------------------ time to sale

def time_to_sale() -> dict:
    w = D.watches()
    start, end = D.window()
    ref = D.sold_watches().groupby(["model", "condition_group"])["final_price"].median()
    fp = w[(w["is_auction"] == 0) & (w["start_time"] >= start)].copy()
    fp["ref"] = [ref.get((m, c), np.nan) for m, c in zip(fp["model"], fp["condition_group"])]
    fp["rel"] = fp["price_first_obs"] / fp["ref"]
    fp["position"] = pd.cut(fp["rel"], PRICE_POS_BINS, labels=PRICE_POS_LABELS)
    stop = fp["ended_at"].where(fp["ended"], end)
    fp["T"] = (stop - fp["start_time"]).dt.total_seconds() / 3600
    fp["E"] = fp["sold"]
    fp = fp[(fp["T"] > 0)].dropna(subset=["position"])
    curves, rows = [], []
    grid = np.arange(0, 169, 2)
    for pos, x in fp.groupby("position", observed=True):
        km = KaplanMeierFitter().fit(x["T"], x["E"], label=str(pos))
        sf = km.survival_function_at_times(grid).values
        ci = km.confidence_interval_
        lo_s = np.interp(grid, ci.index.values, ci.iloc[:, 0].values)
        hi_s = np.interp(grid, ci.index.values, ci.iloc[:, 1].values)
        curves.append(pd.DataFrame(dict(position=str(pos), hours=grid, sold=1 - sf, lo=1 - hi_s, hi=1 - lo_s)))
        r = dict(position=str(pos), n=len(x), events=int(x["E"].sum()))
        for h in (24, 72, 120):
            r[f"sold_{h}h"] = float(1 - km.predict(h))
            r[f"sold_{h}h_lo"] = float(1 - np.interp(h, ci.index.values, ci.iloc[:, 1].values))
            r[f"sold_{h}h_hi"] = float(1 - np.interp(h, ci.index.values, ci.iloc[:, 0].values))
        rows.append(r)
    lr = multivariate_logrank_test(fp["T"], fp["position"].astype(str), fp["E"])
    allkm = KaplanMeierFitter().fit(fp["T"], fp["E"])
    return dict(n=len(fp), events=int(fp["E"].sum()), table=pd.DataFrame(rows), curves=pd.concat(curves),
                logrank_p=float(lr.p_value), sold_72h=float(1 - allkm.predict(72)),
                ended_unknown=int((fp["outcome"] == "ended_unknown").sum()))


# ------------------------------------------------------------------ sellers

def seller_concentration() -> dict:
    d = D.listings()
    counts = d["seller"].value_counts()
    top10 = counts.index[:10]
    sold = d[d["sold"] == 1]
    one = (counts == 1).sum()
    return dict(n_sellers=int(counts.size), top10_listing_share=float(d["seller"].isin(top10).mean()),
                top10_sales_share=float(sold["seller"].isin(top10).mean()), single_listing_sellers=int(one),
                largest=int(counts.iloc[0]))


def run_all() -> dict:
    return dict(overview=overview(), ask_used=ask_vs_sold("Used"), ask_new=ask_vs_sold("New"),
                ask_all=ask_vs_sold(None), bridge=part1_bridge(), gold=gold(), auctions=auction_rates(),
                fixed=fixed_price_endings(), trajectories=auction_trajectories(), repricing=repricing(),
                survival=time_to_sale(), sellers=seller_concentration())
