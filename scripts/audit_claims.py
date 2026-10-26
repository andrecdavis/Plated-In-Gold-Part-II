"""Check every number in README.md against docs/results.json and write docs/claims_audit.md.

    python scripts/audit_claims.py

Each claim is a phrase that must appear verbatim in the README, the result it
comes from, and the value recomputed from docs/results.json. The script fails
if a phrase is missing or its number does not match the result.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "docs" / "results.json").read_text())
SUMMARY = json.loads((ROOT / "data" / "public" / "collection_summary.json").read_text())


def get(path):
    x = R
    for k in path.split("."):
        x = x[int(k)] if isinstance(x, list) else x[k]
    return x


def row(table, key, value, col):
    return next(r for r in get(table) if r[key] == value)[col]


c = lambda v: f"{v:,.0f}"                      # count  # noqa: E731
pc = lambda v, d=0: f"{100 * v:.{d}f}%"         # percent  # noqa: E731
pn = lambda v, d=0: f"{100 * v:.{d}f}"          # percent without sign  # noqa: E731
usd = lambda v, d=0: f"${v:,.{d}f}"             # noqa: E731
x2 = lambda v: f"{v:.2f}"                       # noqa: E731
pv = lambda v: f"{v:.2g}".replace("e-", "e-")   # noqa: E731
ci_pc = lambda lo, hi, d=0: f"{100 * lo:.{d}f}–{100 * hi:.{d}f}"  # noqa: E731

sv = {r["position"]: r for r in get("survival.table")}
au = R["auctions"]
g = R["gold"]
sm = R["sale_model"]["metrics"]
pm = R["price_model"]
ov = R["overview"]
tr = R["trajectories"]
fx = R["fixed"]
part = {p["ratio"]: p["prob"] for p in R["sale_model"]["partial"]}
used = {r["model"]: r for r in get("ask_used")}
new = {r["model"]: r for r in get("ask_new")}
br = {r["model"]: r for r in get("bridge")}
tb = {r["bin"]: r["median"] for r in tr["table"]}
fs = {i: r for i, r in enumerate(pm["format_shap"])}
gold_sold_ratio = [r["median_ask"] / r["plain_sold"] for r in g["by_model"]]
outc = {(o["outcome"], o["confidence"]): o["n"] for o in ov["outcomes_by"]}
p1 = pd.read_csv(ROOT / "data" / "public" / "part1_model_prices.csv").set_index("model")
sys.path.insert(0, str(ROOT))
from collector.config import DEFAULT_PRICE_BANDS, Settings  # noqa: E402
from src import data as D  # noqa: E402

cfg = Settings()
_gaps = pd.read_csv(ROOT / "data" / "public" / "collection_gaps.csv")
_mt = lambda t: pd.Timestamp(t).tz_convert("America/Denver")  # noqa: E731
_clock = lambda t: t.strftime("%I:%M %p").lstrip("0")  # noqa: E731
GAP_CLAIMS = []
for _g in _gaps.itertuples():
    a, b = _mt(_g.start), _mt(_g.end)
    day = lambda t: t.strftime("%a %b %d").replace(" 0", " ")  # noqa: E731
    span = f"{day(a)}, {_clock(a)} – {_clock(b)}" if a.date() == b.date() else f"{day(a)}, {_clock(a)} – {day(b)}, {_clock(b)}"
    GAP_CLAIMS.append(("Collection", f"| {span} | {_g.hours:.1f} |", "data/public/collection_gaps.csv (UTC → MT)", [span, f"{_g.hours:.1f}"]))
_a = D.ended_auctions()
_with_bids = _a[_a["first_bid_count"] > 0]
_d = D.listings()
_others_age = _d[(_d["gold"] == 0) & (_d["is_auction"] == 0) & (_d["outcome"] == "active") & _d["is_single_watch"]]["age_years"].median()


def money(v):
    s = f"{v:,.2f}"
    return "$" + (s[:-3] if s.endswith(".00") else s)


def used_row(m):
    u = used[m]
    return (f"| {m} | {money(u['ask'])} | {money(u['sold'])} | {u['ratio']:.2f} [{u['ratio_lo']:.2f}–{u['ratio_hi']:.2f}] "
            f"| {u['n_sold']} |")


CLAIMS = [
    # section, README phrase, source, values that must appear in the phrase
    ("Intro", "followed **31,498** US Apple Watch listings", "overview.listings", [c(ov["listings"])]),
    ("Intro", "It recorded **458,087** price snapshots and **3,843** listing outcomes, including **2,063 completed sales**",
     "overview.snapshots / outcomes / outcome_counts.sold", [c(ov["snapshots"]), c(ov["outcomes"]), c(ov["outcome_counts"]["sold"])]),
    ("Intro", "one week of data with 51 hours of collection gaps", "overview.gap_hours", [f"{ov['gap_hours']:.0f}"]),
    ("Intro", "the outdated Series 2 ($743), Series 4 ($676) and Series 3 ($664) averaged higher asking prices than the current Ultra 3 ($651)",
     "data/public/part1_model_prices.csv", [usd(p1.loc[m, "part1_mean_ask"]) for m in ("Series 2", "Series 4", "Series 3", "Ultra 3")]),
    ("Intro", "analyzed 2,328 web-scraped Apple Watch listings", "Part I README: 2,263 listings with a model (sum of part1_n) + 65 with none", [c(p1["part1_n"].sum() + 65)]),
    ("Headline", "| **31,498** | **458,087** | **2,063** | **724** | **20,109** |", "overview; auctions.n; sellers.n_sellers",
     [c(ov["listings"]), c(ov["snapshots"]), c(ov["outcome_counts"]["sold"]), c(au["n"]), c(ov["sellers"])]),
    ("Headline", "A used Series 3 is listed at a median of $75 but sells for $35, **2.14×** its sale price (95% CI 1.88–2.34)",
     "ask_used[Series 3]", [usd(used["Series 3"]["ask"]), usd(used["Series 3"]["sold"]), x2(used["Series 3"]["ratio"]),
                            f"{used['Series 3']['ratio_lo']:.2f}–{used['Series 3']['ratio_hi']:.2f}"]),
    ("Headline", "For a used Ultra 3 the gap is only 1.07× (1.01–1.10)", "ask_used[Ultra 3]",
     [x2(used["Ultra 3"]["ratio"]), f"{used['Ultra 3']['ratio_lo']:.2f}–{used['Ultra 3']['ratio_hi']:.2f}"]),
    ("Headline", "sell for a median of **$35–50** on eBay, against about $500 for the Ultra 3", "bridge.part2_median_sold",
     [usd(br["Series 3"]["part2_median_sold"]), f"{br['Series 4']['part2_median_sold']:.0f}", f"${br['Ultra 3']['part2_median_sold']:.0f}"]),
    ("Headline", "were **41%** sold within 72 hours; those priced above 150% were **7%** sold (log-rank p = 8.7e-49)",
     "survival.table / logrank_p", [pc(sv["Below 90%"]["sold_72h"]), pc(sv["Above 150%"]["sold_72h"]), pv(R["survival"]["logrank_p"])]),
    ("Headline", "None of the **299** 24k gold listings ended or sold during the week. They ask a median of **$1,199**, **13.5×** what the same model sells for, and have been up for a median of **4.1 years**. Three sellers account for 95% of them.",
     "gold.n / ended / sold / median_ask / median_sold_ratio / median_age_years / top3_share",
     [c(g["n"]), usd(g["median_ask"]), f"{g['median_sold_ratio']:.1f}", f"{g['median_age_years']:.1f}", pc(g["top3_share"])]),
    ("Headline", "51.5% of ended auctions sold. Series 9 and 10 auctions sold 63% of the time against 36% for the Series 3 (p = 0.0004). The median current bid 24–48 hours before the end is 76% of the final price.",
     "auctions.rate / new_vs_s3; trajectories.table", [pc(au["rate"], 1), pc(au["new_vs_s3"]["p1"]), pc(au["new_vs_s3"]["p2"]),
                                                       f"{au['new_vs_s3']['p']:.1g}", pc(tb["24–48 h"])]),
    ("Headline", "reaches R² = 0.90 (median error 14.7%)", "price_model.metrics", [x2(pm["metrics"]["r2"]), pc(pm["metrics"]["mape_median"], 1)]),
    ("Headline", "Auctions sell for about $14 less", "price_model.format_shap[Auction]", [f"${-fs[0]['mean']:.0f}"]),
    ("Asking vs sold", "Intervals are from 4,000 bootstrap resamples", "src/stats.py boot_ci n_boot", ["4,000"]),
    *[("Asking vs sold", used_row(m), f"ask_used[{m}]",
       [f"{used[m]['ratio']:.2f}", str(used[m]["n_sold"])]) for m in
      ["Series 3", "Series 4", "Series 6", "Series 9", "Series 10", "Series 11", "Ultra 1", "Ultra 2", "Ultra 3"]],
    ("Asking vs sold", "| Series 9 | $200 | $130 |", "ask_used[Series 9]", [usd(used["Series 9"]["ask"]), usd(used["Series 9"]["sold"])]),
    ("Asking vs sold", "| Ultra 3 | $512.50 | $480.99 |", "ask_used[Ultra 3]", [usd(used["Ultra 3"]["ask"], 2), usd(used["Ultra 3"]["sold"], 2)]),
    ("Asking vs sold", "Every interval is above 1", "min(ask_used.ratio_lo)", [] if min(u["ratio_lo"] for u in used.values()) > 1 else ["FAIL"]),
    ("Asking vs sold", "(Series 9 1.51×, Ultra 3 1.16×)", "ask_new", [x2(new["Series 9"]["ratio"]), x2(new["Ultra 3"]["ratio"])]),
    ("Part I bridge", "The Series 2, 4 and 3 averaged $664–743 in Part I, with 42–88% of their listings gold-plated",
     "bridge.part1_mean_ask / part1_gold_share", [f"{br['Series 3']['part1_mean_ask']:.0f}", f"{br['Series 2']['part1_mean_ask']:.0f}",
                                                  pn(br["Series 3"]["part1_gold_share"]), pc(br["Series 2"]["part1_gold_share"])]),
    ("Part I bridge", "On eBay they sell for a median of **$49.99, $49.99 and $35**", "bridge.part2_median_sold",
     [usd(br["Series 2"]["part2_median_sold"], 2), usd(br["Series 4"]["part2_median_sold"], 2), usd(br["Series 3"]["part2_median_sold"])]),
    ("Part I bridge", "The Ultra 3, Part I's 4th-ranked model at $651, sells for $499.99, the highest median sale of any model in the comparison",
     "bridge", [usd(br["Ultra 3"]["part1_mean_ask"]), usd(br["Ultra 3"]["part2_median_sold"], 2)]
     + ([] if max(b["part2_median_sold"] for b in br.values()) == br["Ultra 3"]["part2_median_sold"] else ["FAIL"])),
    ("Time to sale", "Listings that ended without a confirmed outcome (247)", "survival.ended_unknown", [str(R["survival"]["ended_unknown"])]),
    *[("Time to sale", f"| {k} | {sv[k]['n']} | {pc(sv[k]['sold_24h'])} | {pc(sv[k]['sold_72h'])} [{ci_pc(sv[k]['sold_72h_lo'], sv[k]['sold_72h_hi'])}] | {pc(sv[k]['sold_120h'])} |",
       f"survival.table[{k}]", []) for k in sv],
    ("Time to sale", "Across all 2,312 listings, 21% were sold by 72 hours", "survival.n / sold_72h", [c(R["survival"]["n"]), pc(R["survival"]["sold_72h"])]),
    ("Repricing", "among 26,571 fixed-price watch listings observed more than once, only **9.8%** changed price during the week, and 7.6% ended lower than they started (median cut −5.7%)",
     "repricing", [c(R["repricing"]["n"]), pc(R["repricing"]["changed"], 1), pc(R["repricing"]["cut"], 1), f"{100 * R['repricing']['median_cut']:.1f}".replace("-", "−")]),
    ("Gold", "The collector found **299** listings with 24k gold: 292 gold-plated watches, 5 anodized watches with 24k parts, 1 band and 1 plating service",
     "gold.kinds", [str(g["kinds"]["Gold-plated watch"]), str(g["kinds"]["Anodized watch, 24k parts"])]),
    ("Gold", "Their median ask is **$1,199** (IQR $881–1,699; range $199–4,749)", "gold.median_ask / ask_q1 / ask_q3 / min_ask / max_ask",
     [usd(g["ask_q1"]), f"{g['ask_q3']:,.0f}", usd(g["min_ask"]), f"{g['max_ask']:,.0f}"]),
    ("Gold", "For the 286 plated watches with an identified model, the median ask is **8.2×** the median ask for the same model and **13.5×** its median sale price, from 6× for an Ultra 4 to 22× for a Series 3",
     "gold.plated_n / median_ask_ratio / median_sold_ratio / by_model", [str(g["plated_n"]), f"{g['median_ask_ratio']:.1f}", f"{g['median_sold_ratio']:.1f}",
                                                                          f"{min(gold_sold_ratio):.0f}×", f"{max(gold_sold_ratio):.0f}×"]),
    ("Gold", "all 299 are fixed-price, good-'til-cancelled listings (290 with Best Offer)", "gold.gtc_share / formats",
     [str(g["formats"]["Fixed price + Best Offer"])] + ([] if g["gtc_share"] == 1 else ["FAIL"])),
    ("Gold", "the median listing has been up for **4.1 years** (IQR 2.5–6.1), and 82% for more than two years; other active fixed-price watches have been up for a median of 7 months",
     "gold.median_age_years / age_q1 / age_q3 / share_older_2y; images/07", [f"{g['age_q1']:.1f}", f"{g['age_q3']:.1f}", pc(g["share_older_2y"])]),
    ("Gold", "**10 sellers** list them, the largest 216 (72%), and the top three 95%", "gold.n_sellers / top_seller / top_seller_share / top3_share",
     [str(g["n_sellers"]), str(g["top_seller"]), pc(g["top_seller_share"]), pc(g["top3_share"])]),
    ("Gold", "most are New (163) or Open box (129)", "gold.conditions", [str(g["conditions"]["New"]), str(g["conditions"]["Open box"])]),
    ("Gold", "Those sold at **1.07%** during the week (n = 1,777). At that rate, the 286 plated watches would be expected to produce 3.1 sales, and the chance of seeing none is **0.046**. But comparable standard listings priced at $500 or more sold **0 of 566**",
     "gold.window_*", [pc(g["window_comp_rate"], 2), c(g["window_comp_n"]), f"{g['window_expected']:.1f}", f"{g['window_p_zero']:.3f}",
                       f"{g['window_pricey_k']} of {g['window_pricey_n']}"]),
    ("Gold", "Among the 297 gold listings with full details, 45% have never sold a unit; together they have sold 481 units, a median of **0.15 per listing per year**. A quarter (26%) offer more than one unit",
     "gold.lifetime_* / multi_qty_share", [str(g["lifetime_n"]), pc(g["lifetime_never"]), str(g["lifetime_total"]), f"{g['lifetime_per_year_median']:.2f}", pc(g["multi_qty_share"])]),
    ("Auctions", "Of **724** ended single-watch auctions, **373 sold (51.5%; 95% CI 47.9–55.1%)**", "auctions.n / k / rate / ci",
     [c(au["n"]), c(au["k"]), pc(au["rate"], 1), ci_pc(*au["ci"], d=1)]),
    ("Auctions", "Series 9 and 10 auctions sold 63% of the time (63/100) against 36% for the Series 3 (26/73), a difference of 27 points (95% CI 12–41; p = 0.0004)",
     "auctions.new_vs_s3", [f"{au['new_vs_s3']['k1']}/{au['new_vs_s3']['n1']}", f"{au['new_vs_s3']['k2']}/{au['new_vs_s3']['n2']}",
                            f"{pn(au['new_vs_s3']['diff'])} points", ci_pc(au["new_vs_s3"]["lo"], au["new_vs_s3"]["hi"]), f"{au['new_vs_s3']['p']:.1g}"]),
    ("Auctions", "Sellers with 10,000+ feedback sold 69% of their auctions; sellers with zero or negative feedback, 28% (trend p = 0.0002)",
     "auctions.by_feedback / feedback_trend", [pc(row("auctions.by_feedback", "feedback", "10k+", "rate")), pc(row("auctions.by_feedback", "feedback", "≤0", "rate")),
                                               f"{au['feedback_trend']['p']:.1g}"]),
    ("Auctions", "Free-shipping auctions sold more often (62% vs 50%, p = 0.023)", "auctions.free_shipping",
     [pc(au["free_shipping"]["p1"]), pc(au["free_shipping"]["p2"]), f"{au['free_shipping']['p']:.2g}"]),
    ("Auctions", "A logistic regression with condition and model family controls (n = 723)", "auctions.adjusted_n", [str(au["adjusted_n"])]),
    ("Auctions", "odds ratio **1.24 [1.10–1.40]** per tenfold increase in seller feedback (p = 0.0006)", "auctions.adjusted.log_fb",
     [f"{au['adjusted']['log_fb'][k]:.2f}" for k in ("or_", "lo", "hi")] + [f"{au['adjusted']['log_fb']['p']:.1g}"]),
    ("Auctions", "**1.76 [1.24–2.51]** for current-generation models (p = 0.002)", "auctions.adjusted.new_gen",
     [f"{au['adjusted']['new_gen'][k]:.2f}" for k in ("or_", "lo", "hi")] + [f"{au['adjusted']['new_gen']['p']:.1g}"]),
    ("Auctions", "**1.11 [0.69–1.78]** for free shipping (p = 0.68)", "auctions.adjusted.free",
     [f"{au['adjusted']['free'][k]:.2f}" for k in ("or_", "lo", "hi")] + [f"{au['adjusted']['free']['p']:.2f}"]),
    ("Auctions", "54.8% of free-shipping and 56.3% of paid-shipping listings that ended recorded a sale (p = 0.43)", "fixed.free_shipping",
     [pc(fx["free_shipping"]["p1"], 1), pc(fx["free_shipping"]["p2"], 1), f"{fx['free_shipping']['p']:.2f}"]),
    ("Auctions", "Auctions still showing Best Offer at the end sold 4.1% of the time, against 63.5% for the rest", "auctions.leak_best_offer",
     [pc(au["leak_best_offer"]["p1"], 1), pc(au["leak_best_offer"]["p2"], 1)]),
    ("Trajectories", "The median auction stood at 62% of its final price more than three days out, **76% at 24–48 hours**, 90% at 1–3 hours and 97% in the last 15 minutes",
     "trajectories.table", [pc(tb["72 h+"]), pc(tb["24–48 h"]), pc(tb["1–3 h"]), pc(tb["0–15 min"])]),
    ("Trajectories", "59% of auctions still rose, by a median of **3.3%** (95% CI 1.6–6.2%; n = 197). A sold auction received a median of 10 bids",
     "trajectories.late_*", [pc(tr["late_rose_share"]), pc(tr["late_median_jump"], 1), ci_pc(*tr["late_jump_ci"], d=1), str(tr["late_n"]), f"{tr['final_bids_median']:.0f}"]),
    ("Sale model", "**Sample:** 525 ended auctions first observed before their first bid, so the opening price is known. 185 of them sold (35%), from 387 sellers",
     "sale_model.metrics", [str(sm["n"]), str(sm["events"]), pc(sm["base_rate"]), str(sm["sellers"])]),
    ("Sale model", "the 199 auctions that already had bids when first seen, 94% of which sold", "data/public: ended auctions with first_bid_count > 0",
     [str(len(_with_bids)), pc(_with_bids["sold"].mean())]),
    ("Sale model", "the out-of-fold AUC is **0.69 [0.65–0.73]** (fold range 0.63–0.76), against 0.59 [0.54–0.64] for a logistic regression",
     "sale_model.metrics.auc*", [x2(sm["auc"]), f"{sm['auc_ci'][0]:.2f}–{sm['auc_ci'][1]:.2f}", f"{min(sm['auc_folds']):.2f}–{max(sm['auc_folds']):.2f}",
                                 x2(sm["auc_logit"]), f"{sm['auc_logit_ci'][0]:.2f}–{sm['auc_logit_ci'][1]:.2f}"]),
    ("Sale model", "the Brier score is 0.216, against 0.228 for always predicting the base rate", "sale_model.metrics.brier / brier_base",
     [f"{sm['brier']:.3f}", f"{sm['brier_base']:.3f}"]),
    ("Sale model", "the slope is 0.65", "sale_model.metrics.calibration.slope", [x2(sm["calibration"]["slope"])]),
    ("Sale model", "Its highest-probability fifth predicted 70% and sold 55%", "sale_model.reliability[4]",
     [pc(R["sale_model"]["reliability"][4]["predicted"]), pc(R["sale_model"]["reliability"][4]["observed"])]),
    ("Sale model", "(mean |SHAP| 0.41 log-odds), ahead of seller feedback (0.26), model (0.13) and auction length (0.10)", "sale_model.importance",
     [x2(R["sale_model"]["importance"][k]) for k in ("start_vs_market", "seller_feedback_score", "model", "duration_days")]),
    ("Sale model", "falls from **48%** for an opening bid at a quarter of the market price to **36%** at the market price, **27%** at 1.5× and **21%** at 3×",
     "sale_model.partial", [pc(part[0.25]), pc(part[1.0]), pc(part[1.5]), pc(part[3.0])]),
    ("Price model", "**Sample:** 1,873 sold single watches from 1,196 sellers", "price_model.metrics.n / sellers",
     [c(pm["metrics"]["n"]), c(pm["metrics"]["sellers"])]),
    ("Price model", "the out-of-fold **R² is 0.90**, with a mean absolute error of $28.18 and a median absolute percentage error of 14.7%",
     "price_model.metrics", [x2(pm["metrics"]["r2"]), usd(pm["metrics"]["mae"], 2), pc(pm["metrics"]["mape_median"], 1)]),
    ("Price model", "reaches R² = 0.87 and $28.99", "price_model.metrics.r2_base / mae_base", [x2(pm["metrics"]["r2_base"]), usd(pm["metrics"]["mae_base"], 2)]),
    ("Price model", "the model ($53.15), condition ($30.47), case material ($19.72), case size ($16.28) and titanium ($11.47) dominate",
     "price_model.importance", [usd(pm["importance"][k], 2) for k in ("model", "condition_group", "material", "case_size", "titanium")]),
    ("Price model", "Format comes next ($4.75). Seller feedback ($2.48), shipping cost ($1.16) and free shipping ($0.84)", "price_model.importance",
     [usd(pm["importance"][k], 2) for k in ("format", "seller_feedback_score", "shipping_cost", "free_shipping")]),
    ("Price model", "averages **−$13.79** (n = 307), against +$3.72 for fixed price (n = 886) and +$2.02 for fixed price with Best Offer (n = 680)",
     "price_model.format_shap", [f"{-fs[0]['mean']:.2f}", str(fs[0]["size"]), f"{fs[1]['mean']:.2f}", str(fs[1]["size"]), f"{fs[2]['mean']:.2f}", str(fs[2]["size"])]),
    ("Price model", "Each prediction starts from the average sale ($172.44)", "price_model.expected", [usd(pm["expected"], 2)]),
    ("Price model", "A typical used Series 9 sold for $130 and is predicted at $130.46. Used condition (−$16.64), aluminum case (−$11.62) and the 41 mm size (−$9.71)",
     "images/16 (scripts/make_figures.py example_index)", []),
    ("Price model", "A used Ultra 2 sold for $315 and is predicted at $311.46. Titanium shows up in material (+$48.72) and titanium (+$30.01), next to the model (+$45.17) and the 49 mm case (+$27.96)",
     "images/17 (scripts/make_figures.py example_index)", []),
    ("Collection", "pages through the whole category in 17 price bands", "collector/config.py DEFAULT_PRICE_BANDS", [str(len(DEFAULT_PRICE_BANDS))]),
    ("Collection", "auctions ending within 45 minutes", "collector/config.py ending_soon_window_minutes", [str(cfg.ending_soon_window_minutes)]),
    ("Collection", "up to 60 full item records per tick", "collector/config.py detail_batch_per_tick", [str(cfg.detail_batch_per_tick)]),
    ("Collection", "eBay allows 5,000 calls per day. The collector kept a 5% safety margin, held 1,200 calls in reserve for end checks",
     "collector/config.py", [c(cfg.daily_call_limit), pc(cfg.safety_margin), c(cfg.end_check_reserve)]),
    ("Gold", "other active fixed-price watches have been up for a median of 7 months", "data/public: active non-gold fixed-price watches, median age",
     [f"{12 * _others_age:.0f} months"]),
    ("Collection", "7 sweeps saw 24,992–26,637 items each", "overview.sweeps / sweep_items_min / max",
     [str(ov["sweeps"]), c(ov["sweep_items_min"]), c(ov["sweep_items_max"])]),
    ("Collection", "| Sold | auction ended with bids, or fixed-price `sold_quantity` rose without Best Offer | high | 1,327 |", "overview.outcomes_by", [c(outc[("sold", "high")])]),
    ("Collection", "| Sold | fixed-price sale while Best Offer was on (price paid unknown) | medium | 734 |", "overview.outcomes_by", [c(outc[("sold", "medium")])]),
    ("Collection", "(Buy It Now or offer) | medium | 2 |", "overview.bin_sales_reclassified", [str(ov["bin_sales_reclassified"])]),
    ("Collection", "| Unsold | auction ended with no bids | high | 385 |", "overview.outcome_counts.unsold", [c(ov["outcome_counts"]["unsold"])]),
    ("Collection", "| Reserve not met | auction ended with bids below the reserve | high | 9 |", "overview.outcome_counts.reserve_not_met", [c(ov["outcome_counts"]["reserve_not_met"])]),
    ("Collection", "| Ended, outcome unknown | ended or disappeared with no sale signal | low | 1,386 |", "overview.outcome_counts.ended_unknown", [c(ov["outcome_counts"]["ended_unknown"])]),
    ("Collection", "In total it made **20,399** calls (18,020 item reads, 2,375 searches): 20,205 succeeded and 130 returned 404",
     "overview.api_calls / api_calls_by_kind / api_status", [c(ov["api_calls"]), c(ov["api_calls_by_kind"]["getItem"]), c(ov["api_calls_by_kind"]["search"]),
                                                             c(ov["api_status"]["200"]), str(ov["api_status"]["404"])]),
    ("Collection", "for 51.1 of the 168.2 hours (69.6% coverage)", "overview.gap_hours / window_hours / covered_share",
     [f"{ov['gap_hours']:.1f}", f"{ov['window_hours']:.1f}", pc(ov["covered_share"], 1)]),
    ("Collection", "Full details were fetched for 30.6% of listings; 59.3% have no brand field", "overview.detail_share / brand_missing_share",
     [pc(ov["detail_share"], 1), pc(ov["brand_missing_share"], 1)]),
    ("Collection", "The analysis set keeps 28,214 single watches", "overview.analysis_listings", [c(ov["analysis_listings"])]),
    ("Collection", "632 multi-watch lots, 343 accessories and 116 other items", "overview.lots / accessories / other",
     [c(ov["lots"]), c(ov["accessories"]), c(ov["other"])]),
    ("Collection", "1,130 watches with no identifiable model", "overview.no_model", [c(ov["no_model"])]),
    ("Collection", "868 robust price outliers", "overview.price_outliers", [c(ov["price_outliers"])]),
    ("Collection", "Formats: 18,991 fixed price with Best Offer, 10,910 fixed price, 1,597 auctions", "overview.format_counts",
     [c(ov["format_counts"]["Fixed price + Best Offer"]), c(ov["format_counts"]["Fixed price"]), c(ov["format_counts"]["Auction"])]),
    *GAP_CLAIMS,
    ("Limitations", "734 sales were made while Best Offer was on", "overview.outcomes_by", [c(outc[("sold", "medium")])]),
    ("Limitations", "1,386 listings ended with no confirmed outcome", "overview.outcome_counts.ended_unknown", [c(ov["outcome_counts"]["ended_unknown"])]),
]


def main():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    flat = " ".join(readme.split())
    bad, lines = [], []
    for sec, phrase, src, vals in CLAIMS:
        p = " ".join(phrase.split())
        ok_phrase = p in flat
        ok_vals = all(v in p for v in vals) and "FAIL" not in vals
        if not (ok_phrase and ok_vals):
            bad.append((sec, phrase[:80], ok_phrase, [v for v in vals if v not in p]))
        shown = p.replace("|", "\\|")
        lines.append(f"| {sec} | {shown} | `{src}` | {', '.join(vals) if vals else 'see source'} | {'✓' if ok_phrase and ok_vals else '✗'} |")
    out = ["# Claims audit", "",
           "Every number in the README, the result it comes from and the value recomputed from `docs/results.json` "
           "(written by `scripts/make_figures.py --refresh` from `data/public/`). `python scripts/audit_claims.py` "
           "regenerates this file and fails if a phrase is missing from the README or its numbers differ from the results.",
           "", f"{len(CLAIMS)} claims checked, {len(CLAIMS) - len(bad)} verified.", "",
           "| Section | README text | Source | Recomputed values | OK |", "|:--|:--|:--|:--|:-:|", *lines, "",
           "Collection settings come from `collector/config.py`. The two SHAP examples are computed in `scripts/make_figures.py` "
           "and shown in images 16 and 17; `notebooks/01_from_asking_to_selling.ipynb` reproduces the Series 9 example."]
    (ROOT / "docs" / "claims_audit.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    for b in bad:
        print("MISMATCH", b)
    print(f"{len(CLAIMS) - len(bad)}/{len(CLAIMS)} claims verified")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
