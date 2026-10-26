"""Write app/data.js: aggregated tables and model grids for the interactive app (no listing-level records).

    python app/build_data.py [--refresh]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import TZ, story  # noqa: E402
from src import data as D  # noqa: E402
from src.models import LABELS  # noqa: E402
from src.stats import boot_ci, wilson  # noqa: E402

OUT = ROOT / "app" / "data.js"


def r(x, d=2):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), d)


def ask_sold_cube(min_sold=5):
    """Median ask (active listings) and median sale price by model, for every condition x format filter."""
    w = D.watches()
    s = D.sold_watches()
    act = w[w["outcome"] == "active"]
    conds = ["All"] + [c for c in D.COND_ORDER]
    fmts = ["All"] + D.FORMAT_ORDER
    out = []
    for c in conds:
        for f in fmts:
            a = act if c == "All" else act[act["condition_group"] == c]
            b = s if c == "All" else s[s["condition_group"] == c]
            if f != "All":
                a, b = a[a["format"] == f], b[b["format"] == f]
            for m in sorted(set(b["model"].dropna()), key=D.model_sort_key):
                bs, as_ = b.loc[b["model"] == m, "final_price"], a.loc[a["model"] == m, "price"]
                if len(bs) < min_sold or len(as_) < min_sold:
                    continue
                lo, hi = boot_ci(bs, n_boot=400)
                out.append(dict(c=c, f=f, m=m, na=int(len(as_)), ns=int(len(bs)), ask=r(as_.median()),
                                aq1=r(as_.quantile(.25)), aq3=r(as_.quantile(.75)), sold=r(bs.median()),
                                sq1=r(bs.quantile(.25)), sq3=r(bs.quantile(.75)), slo=r(lo), shi=r(hi)))
    return out


def auction_cube():
    """Auction sell-through by model and by driver, for every condition filter."""
    a = D.ended_auctions()
    out = []
    for c in ["All"] + [x for x in D.COND_ORDER if x != "Refurbished"]:
        x = a if c == "All" else a[a["condition_group"] == c]
        for m in ["All"] + sorted(set(x["model"].dropna()), key=D.model_sort_key):
            y = x if m == "All" else x[x["model"] == m]
            if len(y) < 5:
                continue
            row = dict(c=c, m=m, n=int(len(y)), k=int(y["sold"].sum()))
            fb = []
            for lab in D.FEEDBACK_LABELS:
                z = y[y["feedback_bin"] == lab]
                fb.append([int(z["sold"].sum()), int(len(z))])
            row["fb"] = fb
            sh = y.dropna(subset=["free_shipping"])
            fs = sh["free_shipping"].astype(bool)
            row["ship"] = [[int(sh.loc[fs, "sold"].sum()), int(fs.sum())], [int(sh.loc[~fs, "sold"].sum()), int((~fs).sum())]]
            out.append(row)
    return out


def main(refresh=False):
    st = story.load(refresh)
    ov, g, au, tr, sv = st["overview"], st["gold"], st["auctions"], st["trajectories"], st["survival"]
    sm, pm = st["sale_model"], st["price_model"]
    gaps = D.gaps()
    to_mt = lambda t: t.tz_convert(TZ).strftime("%a %b %-d, %-I:%M %p")
    act = D.activity()
    act = act.set_index("hour").reindex(pd.date_range(act["hour"].min(), act["hour"].max(), freq="h"))
    in_gap = np.zeros(len(act), bool)
    for gp in gaps.itertuples():
        in_gap |= ((act.index > gp.start.floor("h")) & (act.index < gp.end.floor("h")))
    calls = act.filter(like="calls_").sum(axis=1).where(~in_gap)
    obs = act.filter(like="obs_").sum(axis=1).where(~in_gap)

    # trajectories: re-number the sampled auctions so no listing key is published
    paths = tr["paths"].sort_values(["listing", "hours_before_end"], ascending=[True, False]).copy()
    keep = paths["listing"].drop_duplicates().iloc[:40]
    paths = paths[paths["listing"].isin(keep)]
    # keep only points where the bid changed, plus each auction's first and last observation
    chg = paths.groupby("listing")["pct"].transform(lambda x: x.ne(x.shift()))
    last = paths.groupby("listing").cumcount(ascending=False) == 0
    paths = paths[chg | last]
    ids = {k: i + 1 for i, k in enumerate(paths["listing"].unique())}
    paths["id"] = paths["listing"].map(ids)
    path_rows = [[int(p.id), p.model, r(p.hours_before_end, 3), r(p.pct, 3), None if pd.isna(p.bid_count) else int(p.bid_count)]
                 for p in paths.sort_values(["id", "hours_before_end"], ascending=[True, False]).itertuples()]

    # gold: age histogram (years) for gold and other active fixed-price watches
    d = D.listings()
    gold_age = d.loc[d["gold"] == 1, "age_years"]
    other = d[(d["gold"] == 0) & d["is_single_watch"] & (d["is_auction"] == 0) & (d["outcome"] == "active")]["age_years"]
    bins = np.arange(0, 10.5, 0.5)
    gh = np.histogram(gold_age.clip(upper=10), bins)[0] / len(gold_age)
    oh = np.histogram(other.clip(upper=10), bins)[0] / len(other)

    pg = st["price_grid"].copy()
    shap_cols = [c for c in pg.columns if c.startswith("shap_")]
    price_grid = dict(cols=["model", "condition_group", "format", "free_shipping", "material", "case_size", "cellular", "titanium",
                            "pred", "n_sold"],
                      shap=[c[5:] for c in shap_cols],
                      rows=[[x.model, x.condition_group, x.format, x.free_shipping, x.material, r(x.case_size, 0),
                             int(x.cellular), int(x.titanium), r(x.pred), int(x.n_sold)] + [r(v) for v in x[shap_cols]] for _, x in pg.iterrows()])
    sg = st["sale_grid"]
    dims = dict(model=list(dict.fromkeys(sg["model"])), condition=list(dict.fromkeys(sg["condition_group"])),
                ratio=list(dict.fromkeys(sg["start_vs_market"])), ship=list(dict.fromkeys(sg["free_shipping"])),
                feedback=[int(v) for v in dict.fromkeys(sg["seller_feedback_score"])])
    # probabilities in per-mille, flattened in the order model, condition, ratio, shipping, feedback
    sale_grid = dict(dims=dims, prob=[int(round(v * 1000)) for v in sg["prob"]])
    surv_curves = [dict(position=p, hours=c["hours"].tolist(), sold=[r(v, 4) for v in c["sold"]],
                        lo=[r(v, 4) for v in c["lo"]], hi=[r(v, 4) for v in c["hi"]])
                   for p, c in sv["curves"].groupby("position", sort=False)]
    fmt_shap = pm["format_shap"].reset_index()
    out = dict(
        overview={k: v for k, v in ov.items() if k not in ("outcomes_by",)},
        gaps=[dict(start=gp.start.tz_convert(TZ).strftime("%Y-%m-%d %H:%M"), end=gp.end.tz_convert(TZ).strftime("%Y-%m-%d %H:%M"),
                   hours=r(gp.hours, 1),
                   label=f"{to_mt(gp.start)} to {to_mt(gp.end)} MT") for gp in gaps.itertuples()],
        activity=dict(hours=[t.tz_convert(TZ).strftime("%Y-%m-%d %H:%M") for t in act.index], calls=[None if np.isnan(v) else int(v) for v in calls],
                      obs=[None if np.isnan(v) else int(v) for v in obs]),
        ask_sold=ask_sold_cube(),
        ask_used=st["ask_used"].round(3).to_dict(orient="records"),
        bridge=st["bridge"].round(3).to_dict(orient="records"),
        survival=dict(table=sv["table"].round(4).to_dict(orient="records"), curves=surv_curves, n=sv["n"],
                      events=sv["events"], logrank_p=sv["logrank_p"], sold_72h=sv["sold_72h"]),
        gold={k: v for k, v in g.items() if k not in ("plated", "by_model")} | dict(
            by_model=g["by_model"].round(2).to_dict(orient="records"),
            age_bins=bins.tolist(), age_gold=[r(v, 4) for v in gh], age_other=[r(v, 4) for v in oh],
            n_other=int(len(other)), other_median_age_years=r(other.median(), 3)),
        auctions=dict(n=au["n"], k=au["k"], ci=list(au["ci"]), cube=auction_cube(), feedback_labels=D.FEEDBACK_LABELS,
                      new_gen=au["new_gen"], series3=au["series3"], new_vs_s3=au["new_vs_s3"],
                      free_shipping=au["free_shipping"], adjusted=au["adjusted"], leak_best_offer=au["leak_best_offer"]),
        trajectories=dict(table=tr["table"].astype({"bin": str}).round(4).to_dict(orient="records"),
                          n=tr["n_auctions"], late_n=tr["late_n"], late_median_jump=tr["late_median_jump"],
                          late_jump_ci=list(tr["late_jump_ci"]), late_rose_share=tr["late_rose_share"],
                          final_bids_median=tr["final_bids_median"], paths=path_rows),
        repricing=st["repricing"], fixed={k: v for k, v in st["fixed"].items() if k != "by_format"},
        sellers=st["sellers"],
        sale_model=dict(metrics=sm["metrics"], importance=[[LABELS.get(k, k), r(v, 4)] for k, v in sm["importance"].items()],
                        reliability=pd.DataFrame(sm["reliability"]).round(4).to_dict(orient="records"),
                        partial=pd.DataFrame(sm["partial"]).round(4).to_dict(orient="records"),
                        grid=sale_grid),
        price_model=dict(metrics=pm["metrics"], expected=pm["expected"],
                         importance=[[LABELS.get(k, k), r(v, 3)] for k, v in pm["importance"].items()],
                         format_shap=[dict(format=x["format"], mean=r(x["mean"]), n=int(x["size"])) for _, x in fmt_shap.iterrows()],
                         grid=price_grid),
        labels=LABELS, model_order=[m for m in D.MODEL_ORDER], cond_order=D.COND_ORDER, format_order=D.FORMAT_ORDER,
    )

    def default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(f"{float(o):.6g}")
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, (pd.Timestamp,)):
            return o.isoformat()
        raise TypeError(type(o))

    def clean(o):
        if isinstance(o, float):
            return None if np.isnan(o) else float(f"{o:.6g}")
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        return o

    OUT.write_text("window.STORY_DATA=" + json.dumps(clean(out), default=default, ensure_ascii=False,
                                                     separators=(",", ":")) + ";\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    main(ap.parse_args().refresh)
