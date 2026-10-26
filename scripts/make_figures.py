"""Regenerate every figure in images/ from data/public/.

    python scripts/make_figures.py [--refresh]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from src import IMAGES, story  # noqa: E402
from src import data as D  # noqa: E402
from src import visualization as V  # noqa: E402


def example_index(frame, X, model, cond, fmt=None):
    sub = frame[(frame["model"] == model) & (frame["condition_group"] == cond)]
    if fmt:
        sub = sub[sub["format"] == fmt]
    med = sub["final_price"].median()
    return (sub["final_price"] - med).abs().idxmin()


def row_values(X, i):
    out = {}
    for k, v in X.loc[i].items():
        if isinstance(v, float) and np.isnan(v):
            out[k] = "missing"
        elif k in ("seller_feedback_score", "shipping_cost"):
            out[k] = f"{v:,.0f}" if k == "seller_feedback_score" else f"${v:,.2f}"
        elif k in ("cellular", "hermes", "premium_band", "titanium", "top_rated_buying", "returns_accepted",
                   "us_location", "detail"):
            out[k] = "yes" if v == 1 else "no"
        elif isinstance(v, float) and v.is_integer():
            out[k] = f"{v:.0f}"
        else:
            out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="recompute the analysis instead of using the cache")
    a = ap.parse_args()
    r = story.load(refresh=a.refresh)
    IMAGES.mkdir(exist_ok=True)
    p = lambda name: IMAGES / name  # noqa: E731
    ov = r["overview"]
    V.fig_pipeline(ov, p("01_collection_pipeline.png"))
    V.fig_collection_timeline(p("02_collection_timeline.png"))
    V.fig_ask_vs_sold(r["ask_used"], "Used watches: asking vs selling", p("03_ask_vs_sold_used.png"))
    V.fig_part1_bridge(r["bridge"], p("04_part1_vs_part2.png"))
    V.fig_time_to_sale(r["survival"]["curves"], r["survival"]["table"], p("05_time_to_sale.png"))
    g = r["gold"]
    V.fig_gold_price_gap(g["by_model"], p("06_gold_price_gap.png"))
    d = D.listings()
    gold_df = d[d["gold"] == 1]
    comp = d[(d["gold"] == 0) & (d["is_auction"] == 0) & (d["outcome"] == "active") & d["is_single_watch"]]
    V.fig_gold_age(g, gold_df, comp["age_years"].dropna(), p("07_gold_age_sellers.png"))
    au = r["auctions"]
    V.fig_rate_by_model(au["by_model"], au["rate"], p("08_auction_sell_through_by_model.png"))
    V.fig_sale_drivers(au, p("09_auction_sale_drivers.png"))
    V.fig_trajectory(r["trajectories"]["table"], r["trajectories"], p("10_auction_trajectory.png"))
    sm, pm = r["sale_model"], r["price_model"]
    V.fig_sale_validation(sm, p("11_sale_model_validation.png"))
    V.fig_importance(sm["importance"], "What drives the auction sale model", "{:.2f}", p("12_sale_model_shap.png"),
                     xlabel="mean |SHAP value| (log-odds of selling)")
    V.fig_opening_price(sm["partial"], p("13_opening_price_effect.png"))
    V.fig_importance(pm["importance"], "What drives the sold-price model", "${:,.2f}", p("14_price_model_shap.png"),
                     color=V.SOLD, xlabel="mean |SHAP value| (USD)")
    V.fig_format_effect(pm["format_shap"], p("15_format_effect.png"))
    i = example_index(pm["frame"], pm["X"], "Series 9", "Used")
    V.fig_waterfall(pm["expected"], pm["shap"].loc[i], row_values(pm["X"], i),
                    "A typical used Series 9 sale, explained", p("16_shap_example_series9.png"))
    i = example_index(pm["frame"], pm["X"], "Ultra 2", "Used")
    V.fig_waterfall(pm["expected"], pm["shap"].loc[i], row_values(pm["X"], i),
                    "A typical used Ultra 2 sale, explained", p("17_shap_example_ultra2.png"))
    tiles = [(f"{ov['listings']:,}", "listings tracked\nfor a week"),
             (f"{r['ask_used'].query('model == \"Series 3\"')['ratio'].iloc[0]:.1f}×", "Series 3 asking price\nover its sale price"),
             (f"0 of {g['n']}", "24k gold listings\nrecorded a sale")]
    V.fig_cover(dict(ask=r["ask_used"], tiles=tiles), p("report_cover.png"))
    for f in sorted(IMAGES.glob("*.png")):
        print(f.relative_to(ROOT))


if __name__ == "__main__":
    main()
