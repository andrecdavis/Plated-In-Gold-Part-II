"""Generate notebooks/01_from_asking_to_selling.ipynb from the public data; `make notebook` also executes it.

    python scripts/make_notebook.py [--execute]
"""
import argparse
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "01_from_asking_to_selling.ipynb"

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))  # noqa: E731
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))  # noqa: E731

md("""
# Plated in Gold, Part II: from asking to selling

Part I studied asking prices in a one-time snapshot of web-scraped Apple Watch listings. This notebook works through
Part II: a week of eBay listings tracked through the eBay Browse API until they ended, so that what sold, for how much
and how fast can be measured directly. It runs on the de-identified tables in `data/public/` and reproduces every
number in the README.
""")
md("## 1. Setup")
code("""
import sys, pathlib, warnings
ROOT = pathlib.Path.cwd().resolve()
ROOT = ROOT.parent if ROOT.name == "notebooks" else ROOT
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from IPython.display import display
from src import data as D, analysis as A, models as M, visualization as V, story
pd.set_option("display.width", 140); pd.set_option("display.max_columns", 30)
import io, matplotlib.figure
def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white", dpi=90)
    return buf.getvalue()
get_ipython().display_formatter.formatters["image/png"].for_type(matplotlib.figure.Figure, _png)
r = story.load(refresh=True)
""")
md("""
## 2. The data

The collector ran from October 19 to October 26, 2026, with three gaps. `data/public/listings.csv.gz` has one row
per listing with its last observed state, the first observed price, the outcome and title-derived features.
Seller names are replaced by salted hashes and listing IDs by random keys.
""")
code("""
ov = r["overview"]
pd.Series({k: v for k, v in ov.items() if not isinstance(v, (dict, list))})
""")
code("""
display(D.gaps())
display(pd.Series(ov["outcome_counts"], name="listings"))
V.fig_collection_timeline()
""")
code("""
V.fig_pipeline(ov)
""")
md("""
Outcome inference: an ended auction with bids is sold, one without bids is unsold; a fixed-price listing whose
`sold_quantity` counter rose is sold (medium confidence when Best Offer was on, because the accepted price is not
public); anything else that ended is `ended_unknown` and is never counted as a sale. Two auctions that ended with
no bids but a higher sold counter sold through Buy It Now or an offer, and are reclassified as sold.
""")
code("""
d = D.listings()
d[["model", "condition_group", "format", "price", "outcome", "final_price", "gold", "age_years"]].sample(6, random_state=1)
""")
md("## 3. Asking is not selling")
code("""
display(r["ask_used"].round(2))
V.fig_ask_vs_sold(r["ask_used"], "Used watches: asking vs selling")
""")
code("""
display(r["ask_new"].round(2))
""")
md("### Back to Part I")
code("""
display(r["bridge"].round(2))
V.fig_part1_bridge(r["bridge"])
""")
md("## 4. Priced right, sold fast (Kaplan–Meier)")
code("""
s = r["survival"]
print(f"{s['n']:,} new fixed-price listings, {s['events']} sales, log-rank p = {s['logrank_p']:.2g}, "
      f"overall sold by 72 h {s['sold_72h']:.1%}, ended without a known outcome (censored) {s['ended_unknown']}")
display(s["table"].round(3))
V.fig_time_to_sale(s["curves"], s["table"])
""")
md("## 5. The gold-plating pitfall, revisited")
code("""
g = r["gold"]
keys = ["n", "kinds", "ended", "sold", "n_sellers", "top_seller_share", "top3_share", "formats", "gtc_share", "conditions",
        "median_ask", "ask_q1", "ask_q3", "median_age_years", "share_older_2y", "plated_n", "median_ask_ratio",
        "median_sold_ratio", "lifetime_n", "lifetime_never", "lifetime_total", "lifetime_per_year_median",
        "comp_n", "comp_never", "comp_per_year_median", "multi_qty_share"]
pd.Series({k: g[k] for k in keys})
""")
code("""
display(g["by_model"].round(1))
V.fig_gold_price_gap(g["by_model"])
""")
code("""
comp = d[(d["gold"] == 0) & (d["is_auction"] == 0) & (d["outcome"] == "active") & d["is_single_watch"]]
V.fig_gold_age(g, d[d["gold"] == 1], comp["age_years"].dropna())
""")
md("""
Is zero sales in a week surprising? Compare with standard listings that look like the gold ones: fixed price,
New or Open box, the same models, and up for at least a year.
""")
code("""
print(f"comparable listings: {g['window_comp_n']:,}, sold in the window: {g['window_comp_rate']:.2%}")
print(f"expected sales among {g['plated_n']} plated watches: {g['window_expected']:.1f}; P(0 sales) = {g['window_p_zero']:.3f}")
print(f"comparable listings priced at $500+: {g['window_pricey_k']} of {g['window_pricey_n']} sold")
""")
md("## 6. What makes an auction sell")
code("""
au = r["auctions"]
print(f"{au['k']} of {au['n']} ended auctions sold ({au['rate']:.1%}, 95% CI {au['ci'][0]:.1%}–{au['ci'][1]:.1%})")
print("Series 9/10 vs Series 3:", {k: round(float(v), 4) for k, v in au["new_vs_s3"].items()})
print("free vs paid shipping (raw):", {k: round(float(v), 4) for k, v in au["free_shipping"].items()})
print("feedback trend:", au["feedback_trend"])
display(pd.DataFrame(au["adjusted"]).T.round(3))
V.fig_rate_by_model(au["by_model"], au["rate"])
""")
code("""
V.fig_sale_drivers(au)
""")
md("""
Two listing fields leak the outcome and are kept out of the auction analysis. The database keeps the latest
value of each field, and eBay removes Best Offer and Buy It Now from an auction once it receives a bid, so
auctions still showing those options are mostly ones that never got a bid. The seller's listing count leaks
through relisting: unsold auctions are often relisted, which raises the count.
""")
code("""
print("Best Offer still on:", {k: round(float(v), 3) for k, v in au["leak_best_offer"].items()},
      "mean final bids", round(au["leak_best_offer_mean_bids"], 2))
print("Buy It Now still on:", {k: round(float(v), 3) for k, v in au["leak_bin"].items()})
au["by_seller_listings"].round(3)
""")
md("### Auction prices are set late")
code("""
tr = r["trajectories"]
print(f"{tr['n_auctions']} sold auctions; final vs last bid seen in the final 15 minutes: median +{tr['late_median_jump']:.1%} "
      f"(95% CI {tr['late_jump_ci'][0]:.1%}–{tr['late_jump_ci'][1]:.1%}, n={tr['late_n']}); still rose: {tr['late_rose_share']:.0%}")
display(tr["table"].round(3))
V.fig_trajectory(tr["table"], tr)
""")
md("### Fixed-price endings, repricing and sellers")
code("""
fx = r["fixed"]
print(f"fixed-price endings: {fx['k']:,} of {fx['n']:,} recorded a sale ({fx['rate']:.1%}); free vs paid shipping "
      f"{fx['free_shipping']['p1']:.1%} vs {fx['free_shipping']['p2']:.1%} (p = {fx['free_shipping']['p']:.2f})")
display(fx["by_format"].round(3))
print("repricing:", r["repricing"])
print("seller concentration:", r["sellers"])
""")
md("""
## 7. Will this auction sell? CatBoost classifier

Sample: ended single-watch auctions first observed before their first bid, so the opening bid is known.
Features are what a seller sets at listing time. `start_vs_market` is the opening bid divided by the median
fixed-price sale for the same model and condition. Validation is 5-fold `StratifiedGroupKFold` by seller, against
a logistic regression on the same inputs. A nested Platt scaling step is recorded but not used, because it did
not improve the Brier score.
""")
code("""
sm = r["sale_model"]
pd.Series({k: v for k, v in sm["metrics"].items() if not isinstance(v, dict)})
""")
code("""
display(pd.DataFrame(sm["reliability"]).round(3))
V.fig_sale_validation(sm)
""")
code("""
display(sm["importance"].round(3))
V.fig_importance(sm["importance"], "What drives the auction sale model", "{:.2f}", xlabel="mean |SHAP value| (log-odds of selling)")
""")
code("""
display(pd.DataFrame(sm["partial"]).round(3))
V.fig_opening_price(sm["partial"])
""")
md("""
## 8. What does a watch sell for? CatBoost regressor with SHAP

Sample: sold single watches (non-gold, final price not a robust outlier). Validation is 5-fold `GroupKFold` by seller,
against a model-and-condition median baseline computed inside each training fold.
""")
code("""
pm = r["price_model"]
pd.Series(pm["metrics"])
""")
code("""
display(pm["importance"].round(2))
V.fig_importance(pm["importance"], "What drives the sold-price model", "${:,.2f}", color=V.SOLD, xlabel="mean |SHAP value| (USD)")
""")
code("""
display(pm["format_shap"].round(2))
V.fig_format_effect(pm["format_shap"])
""")
code("""
sys.path.insert(0, str(ROOT / "scripts"))
from make_figures import example_index, row_values
i = example_index(pm["frame"], pm["X"], "Series 9", "Used")
V.fig_waterfall(pm["expected"], pm["shap"].loc[i], row_values(pm["X"], i), "A typical used Series 9 sale, explained")
""")
md("""
## 9. Summary

1. Asking prices overstate what old watches sell for: a used Series 3 asks 2.1× its median sale price; an Ultra 3, 1.07×.
2. Price relative to the going rate drives how fast a fixed-price listing sells.
3. None of the 299 gold listings sold in the week; they ask several times what the same model sells for. A week is
   short for listings this slow, so this suggests rather than proves that the prices do not clear.
4. Newer models and sellers with more feedback sell more of their auctions; free shipping has no effect after
   adjustment.
5. Most of an auction's price arrives in its last day.
6. Model and condition set the sale price; auctions sell for about $14 less than the same watch at a fixed price.
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nb.metadata["language_info"] = {"name": "python"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    OUT.parent.mkdir(exist_ok=True)
    if a.execute:
        from nbconvert.preprocessors import ExecutePreprocessor
        ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(ROOT)}})
    nbf.write(nb, OUT)
    print(f"wrote {OUT.relative_to(ROOT)}")
