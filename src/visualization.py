"""Static figures for the README, notebook and PDF report.

Palette: Okabe-Ito colours for categories, blue for the main series, gold (#B8860B)
only for gold-plated listings, gray for context and shaded collection gaps.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from sklearn.metrics import roc_curve

from . import TZ
from . import data as D
from .models import LABELS

INK, MUTED, GRID = "#222222", "#555555", "#E6E6E6"
BLUE, GRAY, ACCENT, GOLD = "#3A6EA5", "#A0A4A8", "#E69F00", "#B8860B"
SOLD, ASK = "#009E73", "#3A6EA5"
POS, NEG = "#D55E00", "#0072B2"
OKABE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442"]
GAP_COLOR = "#D9D9D9"


def _style():
    plt.rcdefaults()
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 160, "figure.facecolor": "white", "axes.facecolor": "white",
        "font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 14, "axes.titleweight": "bold",
        "axes.titlepad": 12, "axes.titlelocation": "left", "axes.labelsize": 11, "axes.labelcolor": INK,
        "text.color": INK, "xtick.color": INK, "ytick.color": INK, "xtick.labelsize": 10, "ytick.labelsize": 10,
        "axes.edgecolor": "#BDBDBD", "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False})


def _save(fig, path):
    fig.tight_layout()
    if path:
        fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return fig


def _grid(ax, axis):
    ax.grid(False)
    ax.grid(True, axis=axis)


def _subtitle(ax, text, y=1.0):
    """Gray line under the title; the title is moved up to make room."""
    ax.set_title(ax.get_title(loc="left"), loc="left", pad=26)
    ax.text(0, 1.015, text, transform=ax.transAxes, fontsize=10, color=MUTED, va="bottom")


def _money(v):
    return f"${v:,.0f}"


def _pct(v, d=0):
    return f"{100 * v:.{d}f}%"


# ------------------------------------------------------------------ data collection

def fig_pipeline(ov: dict, path=None):
    _style()
    fig, ax = plt.subplots(figsize=(12, 8.2))
    ax.set_axis_off()
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8.2)

    def box(x, y, w, h, title, body, color=BLUE, fill="#F3F6FA"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fill, ec=color, lw=1.6))
        ax.text(x + 0.15, y + h - 0.2, title, fontsize=11, fontweight="bold", va="top", color=INK)
        ax.text(x + 0.15, y + h - 0.55, body, fontsize=9, va="top", color=MUTED, linespacing=1.45)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.4))

    box(0.1, 5.6, 3.1, 1.9, "eBay Browse API", "EBAY_US · Smart Watches\n(category 178893) · Brand = Apple\n"
        "OAuth client credentials\nshipping quoted to ZIP 80202")
    tasks = [("full sweep", "daily · 17 price bands"), ("new listings", "every 30 min · newest first"),
             ("ending soon", "every 20 min · auctions < 45 min"), ("final look", "every minute · last 4 min"),
             ("item details", "every 5 min · up to 60 items"), ("end checks", "+10 min, +3 h, +24 h after end")]
    ax.text(3.75, 8.0, "Collector tasks (polling cadence)", fontsize=11, fontweight="bold", va="top")
    for i, (t, c) in enumerate(tasks):
        y = 7.45 - i * 0.5
        ax.add_patch(FancyBboxPatch((3.75, y - 0.21), 3.85, 0.44, boxstyle="round,pad=0.01,rounding_size=0.08",
                                    fc="white", ec=OKABE[i % 6], lw=1.4))
        ax.text(3.87, y, t, fontsize=9.5, fontweight="bold", va="center")
        ax.text(5.15, y, c, fontsize=8.6, color=MUTED, va="center")
    arrow(3.2, 6.55, 3.7, 6.55)
    box(8.2, 5.6, 3.65, 1.9, "SQLite database", f"listings {ov['listings']:,}\nsnapshots {ov['snapshots']:,}\n"
        f"outcomes {ov['outcomes']:,}\nAPI calls {ov['api_calls']:,}")
    arrow(7.65, 6.55, 8.15, 6.55)
    box(0.1, 2.45, 3.6, 2.0, "Coverage", f"{ov['start'][:10]} to {ov['end'][:10]}\n{ov['window_hours']:.0f} h window, "
        f"{ov['gap_hours']:.0f} h in three gaps\n{_pct(ov['covered_share'])} of hours covered\n"
        f"full item details for {_pct(ov['detail_share'])}\nof listings", color=GRAY, fill="#F6F6F6")
    box(4.0, 2.45, 3.6, 2.0, "Call budget", "5,000 calls per day\n5% safety margin → 4,750\n"
        "1,200 held back for end checks\nretries with exponential backoff\non 429 and 5xx responses",
        color=ACCENT, fill="#FDF6EA")
    box(8.2, 2.45, 3.65, 2.0, "Outcome inference", "auction, read after it ends:\n  bids → sold (high)\n"
        "  no bids → unsold (high)\nfixed price, sold counter rose:\n  sold (high; medium with Best Offer)\n"
        "otherwise: ended, outcome unknown (low)", color=OKABE[2], fill="#F1F8F5")
    arrow(10.0, 5.58, 10.0, 4.5)
    box(6.3, 0.15, 5.55, 1.95, "Private → public", "src/prepare.py keeps the raw database private and\n"
        "writes de-identified tables: no seller names, item IDs,\nURLs, titles or descriptions; "
        "sellers become\nsalted hashes, feedback scores are rounded", color=INK, fill="#FAFAFA")
    arrow(10.0, 2.43, 10.0, 2.15)
    box(0.1, 0.15, 5.75, 1.95, "Analysis", "cleaning (model, condition, lots, outliers)\nstatistics with 95% intervals\n"
        "CatBoost + SHAP, cross-validated by seller\nfigures, notebook, interactive app, PDF report", color=BLUE)
    arrow(6.25, 1.1, 5.9, 1.1)
    ax.set_title("How the data was collected", loc="left", pad=6)
    return _save(fig, path)


def _shade_gaps(ax, local=True):
    for g in D.gaps().itertuples():
        s, e = (g.start.tz_convert(TZ), g.end.tz_convert(TZ)) if local else (g.start, g.end)
        ax.axvspan(s.tz_localize(None), e.tz_localize(None), color=GAP_COLOR, alpha=0.8, lw=0, zorder=0)


def fig_collection_timeline(path=None):
    _style()
    a = D.activity().set_index("hour")
    full = pd.date_range(a.index.min(), a.index.max(), freq="h")
    a = a.reindex(full)
    a.index.name = "hour"
    a = a.reset_index()
    a["t"] = a["hour"].dt.tz_convert(TZ).dt.tz_localize(None)
    fig, ax = plt.subplots(figsize=(11, 4.4))
    _shade_gaps(ax)
    in_gap = np.zeros(len(a), bool)
    for g in D.gaps().itertuples():
        in_gap |= ((a["hour"] > g.start.floor("h")) & (a["hour"] < g.end.floor("h"))).values
    calls = a.filter(like="calls_").sum(axis=1).where(~in_gap)
    obs = a.filter(like="obs_").sum(axis=1).where(~in_gap)
    ax.bar(a["t"], calls, width=1 / 24, color=BLUE, label="API calls per hour", align="edge")
    ax2 = ax.twinx()
    ax2.plot(a["t"] + pd.Timedelta(minutes=30), obs, color=ACCENT, lw=1.2, label="observations per hour")
    ax2.spines["right"].set_visible(True)
    ax2.grid(False)
    ax.set_ylabel("API calls per hour")
    ax2.set_ylabel("observations per hour", color=ACCENT)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(tz=None))
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    from matplotlib.patches import Patch
    ax.legend(h1 + h2 + [Patch(color=GAP_COLOR)], l1 + l2 + ["collection gap"], loc="upper left", ncol=3, fontsize=9,
              bbox_to_anchor=(0, 1.0))
    ax.set_ylim(0, calls.max() * 1.35)
    ax2.set_ylim(0, obs.max() * 1.35)
    ax.set_title("Collection activity, Mountain Time")
    return _save(fig, path)


# ------------------------------------------------------------------ asking vs selling

def fig_ask_vs_sold(t: pd.DataFrame, title, path=None):
    _style()
    t = t.copy()
    t["order"] = t["model"].map(D.model_sort_key)
    t = t.sort_values("order", ascending=False).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(t) + 1.6))
    y = np.arange(len(t))
    ax.hlines(y, t["sold"], t["ask"], color="#C9CED6", lw=3, zorder=1)
    ax.errorbar(t["sold"], y, xerr=[t["sold"] - t["sold_lo"], t["sold_hi"] - t["sold"]], fmt="none", ecolor=SOLD,
                elinewidth=1, capsize=2, zorder=2)
    ax.scatter(t["sold"], y, color=SOLD, s=55, zorder=3, label="median sold price (95% CI)")
    ax.scatter(t["ask"], y, color=ASK, s=55, zorder=3, label="median asking price, active listings")
    for i, r in t.iterrows():
        ax.text(r["ask"] * 1.04 + 6, i, f"{r['ratio']:.2f}×", va="center", fontsize=9.5, color=INK, fontweight="bold")
    ax.set_yticks(y, [f"{m}  (n={n})" for m, n in zip(t["model"], t["n_sold"])])
    ax.set_xlabel("price (USD)")
    ax.set_xlim(0, t["ask"].max() * 1.22)
    _grid(ax, "x")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title(title)
    return _save(fig, path)


def fig_part1_bridge(b: pd.DataFrame, path=None):
    _style()
    b = b.dropna(subset=["part2_median_sold"]).copy()
    b = b.sort_values("part1_mean_ask", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(b) + 1.8))
    y = np.arange(len(b))
    h = 0.38
    ax.barh(y + h / 2, b["part1_mean_ask"], height=h, color=[GOLD if g >= 0.4 else GRAY for g in b["part1_gold_share"]],
            label="Part I: mean asking price (web-scraped)")
    ax.barh(y - h / 2, b["part2_median_sold"], height=h, color=SOLD, label="Part II: median eBay sold price")
    for i, r in b.iterrows():
        ax.text(r["part1_mean_ask"] + 8, i + h / 2, _money(r["part1_mean_ask"]) +
                (f"  · {r['part1_gold_share']:.0%} gold-plated" if r["part1_gold_share"] >= 0.1 else ""),
                va="center", fontsize=8.5, color=MUTED)
        ax.text(r["part2_median_sold"] + 8, i - h / 2, _money(r["part2_median_sold"]), va="center", fontsize=8.5,
                color=INK)
    ax.set_yticks(y, b["model"])
    ax.set_xlim(0, b["part1_mean_ask"].max() * 1.4)
    ax.set_xlabel("USD")
    _grid(ax, "x")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=GOLD, label="Part I mean ask, 40%+ gold-plated"),
                       Patch(color=GRAY, label="Part I mean ask"),
                       Patch(color=SOLD, label="Part II median sold price, all conditions")],
              loc="lower right", fontsize=9)
    ax.set_title("Part I's priciest models were its cheapest sellers")
    return _save(fig, path)


def fig_time_to_sale(curves: pd.DataFrame, table: pd.DataFrame, path=None):
    _style()
    fig, ax = plt.subplots(figsize=(10, 5.4))
    cols = dict(zip(["Below 90%", "90–110%", "110–150%", "Above 150%"], [SOLD, BLUE, ACCENT, POS]))
    for pos, c in curves.groupby("position", sort=False):
        n = int(table.loc[table["position"] == pos, "n"].iloc[0])
        ax.step(c["hours"], c["sold"], where="post", color=cols[pos], lw=2.2, label=f"{pos} of market (n={n:,})")
        ax.fill_between(c["hours"], c["lo"], c["hi"], step="post", color=cols[pos], alpha=0.12, lw=0)
        last = c[c["hours"] <= 120].iloc[-1]
        ax.text(123, last["sold"], _pct(last["sold"]), color=cols[pos], va="center", fontsize=10, fontweight="bold")
    ax.set_xlim(0, 135)
    ax.set_xticks([0, 24, 48, 72, 96, 120])
    ax.set_xlabel("hours since the listing started")
    ax.set_ylabel("share sold (Kaplan–Meier)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.legend(loc="upper left", fontsize=9.5, title="asking price vs median sale price\nof the same model and condition",
              title_fontsize=9)
    ax.set_title("Fixed-price listings priced near the market sell; overpriced ones wait")
    return _save(fig, path)


# ------------------------------------------------------------------ gold

def fig_gold_price_gap(by_model: pd.DataFrame, path=None):
    _style()
    t = by_model.copy().reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.42 * len(t) + 1.8))
    y = np.arange(len(t))[::-1]
    ax.hlines(y, t["plain_sold"], t["median_ask"], color="#E8DDC0", lw=3, zorder=1)
    ax.scatter(t["plain_sold"], y, color=SOLD, s=50, zorder=3, label="standard watch: median sold")
    ax.scatter(t["plain_ask"], y, color=ASK, s=50, zorder=3, label="standard watch: median ask")
    ax.scatter(t["median_ask"], y, color=GOLD, s=70, marker="D", zorder=3, label="24k gold-plated: median ask")
    ax.set_xscale("log")
    ax.set_xticks([25, 50, 100, 250, 500, 1000, 2500, 5000], ["$25", "$50", "$100", "$250", "$500", "$1k", "$2.5k", "$5k"])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_yticks(y, [f"{m}  ({n})" for m, n in zip(t["model"], t["n"])])
    for yy, r in zip(y, t.itertuples()):
        ax.text(r.median_ask * 1.12, yy, f"{r.median_ask / r.plain_sold:.0f}×", va="center", fontsize=9, color=GOLD,
                fontweight="bold")
    ax.set_xlim(20, 9000)
    _grid(ax, "x")
    ax.legend(loc="upper right", fontsize=9)
    mult = t["median_ask"] / t["plain_sold"]
    ax.set_title(f"Gold-plated listings ask {mult.min():.0f}–{mult.max():.0f}× what the same model sells for")
    ax.set_xlabel("price, log scale (multiple = gold ask ÷ standard sold)")
    return _save(fig, path)


def fig_gold_age(g: dict, gold_df: pd.DataFrame, comp_age: pd.Series, path=None):
    _style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw=dict(width_ratios=[1.35, 1]))
    ax = axes[0]
    bins = np.arange(0, 10.5, 0.5)
    ax.hist(comp_age.clip(upper=10), bins=bins, density=True, color=GRAY, alpha=0.6,
            label=f"other active fixed-price watches (n={len(comp_age):,})")
    ax.hist(gold_df["age_years"].clip(upper=10), bins=bins, density=True, color=GOLD, alpha=0.85, histtype="stepfilled",
            label=f"24k gold listings (n={len(gold_df)})")
    ax.axvline(g["median_age_years"], color=GOLD, ls="--", lw=1.4)
    ax.text(g["median_age_years"] + 0.15, ax.get_ylim()[1] * 0.55, f"gold median\n{g['median_age_years']:.1f} years",
            color=GOLD, fontsize=9.5, fontweight="bold")
    cm = comp_age.median()
    ax.axvline(cm, color=MUTED, ls=":", lw=1.2)
    ax.text(cm + 0.15, ax.get_ylim()[1] * 0.7, f"others' median\n{cm * 12:.0f} months", color=MUTED, fontsize=9)
    ax.set_xlabel("listing age at the end of collection (years)")
    ax.set_ylabel("density")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title("Gold listings have been up for years")
    ax = axes[1]
    counts = g["seller_counts"]
    labels = ["Seller A", "Seller B", "Seller C", "7 others"]
    vals = counts[:3] + [sum(counts[3:])]
    ax.barh(labels[::-1], vals[::-1], color=[GRAY, GOLD, GOLD, GOLD])
    for i, v in enumerate(vals[::-1]):
        ax.text(v + 3, i, f"{v} ({v / sum(counts):.0%})", va="center", fontsize=10)
    ax.set_xlim(0, max(vals) * 1.35)
    _grid(ax, "x")
    ax.set_xlabel("gold listings")
    ax.set_title("Three sellers list 95%")
    return _save(fig, path)


# ------------------------------------------------------------------ auctions

def fig_rate_by_model(t: pd.DataFrame, overall: float, path=None, min_n=10):
    _style()
    t = t[t["n"] >= min_n].copy().reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 0.4 * len(t) + 1.6))
    y = np.arange(len(t))[::-1]
    ax.errorbar(t["rate"], y, xerr=[t["rate"] - t["lo"], t["hi"] - t["rate"]], fmt="o", color=BLUE, ecolor="#9DB4D3",
                elinewidth=2, capsize=0, ms=7)
    ax.axvline(overall, color=GRAY, ls="--", lw=1)
    ax.text(overall + 0.01, y.max() + 0.6, f"all auctions {overall:.0%}", color=MUTED, fontsize=9)
    for yy, r in zip(y, t.itertuples()):
        ax.text(1.02, yy, f"{r.k}/{r.n}", va="center", fontsize=9, color=MUTED)
    ax.set_yticks(y, t["model"])
    ax.set_xlim(0, 1.1)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}" if v <= 1 else ""))
    ax.set_xlabel("auctions that sold (95% Wilson interval)")
    _grid(ax, "x")
    ax.set_title("The oldest models are the hardest to sell at auction")
    _subtitle(ax, f"Models with at least {min_n} ended auctions", 1.01)
    return _save(fig, path)


def fig_sale_drivers(au: dict, path=None):
    _style()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), gridspec_kw=dict(width_ratios=[1.6, 1.1, 1.2]))

    def bars(ax, labels, rows, color, title):
        x = np.arange(len(rows))
        rates = [r[0] for r in rows]
        ax.bar(x, rates, color=color, width=0.65)
        ax.errorbar(x, rates, yerr=[[r[0] - r[1] for r in rows], [r[2] - r[0] for r in rows]], fmt="none",
                    ecolor=INK, elinewidth=1, capsize=3)
        for i, r in enumerate(rows):
            ax.text(i, r[2] + 0.03, f"{r[0]:.0%}\n{r[3]}/{r[4]}", ha="center", fontsize=8.5, color=MUTED)
        ax.set_xticks(x, labels)
        ax.set_ylim(0, 1.12)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}" if v <= 1 else ""))
        _grid(ax, "y")
        ax.set_title(title, fontsize=12)

    fb = au["by_feedback"]
    bars(axes[0], fb["feedback"].tolist(), list(zip(fb["rate"], fb["lo"], fb["hi"], fb["k"], fb["n"])), BLUE,
         "Seller feedback score")
    axes[0].set_ylabel("auctions that sold")
    fs = au["free_shipping"]
    from .stats import wilson
    rows = [(fs["p1"], *wilson(fs["k1"], fs["n1"]), fs["k1"], fs["n1"]), (fs["p2"], *wilson(fs["k2"], fs["n2"]), fs["k2"], fs["n2"])]
    bars(axes[1], ["free", "paid"], rows, OKABE[2], "Shipping")
    c = au["by_condition"].set_index("condition").reindex(["New", "Open box", "Used", "For parts"]).dropna().reset_index()
    bars(axes[2], c["condition"].tolist(), list(zip(c["rate"], c["lo"], c["hi"], c["k"].astype(int), c["n"].astype(int))),
         OKABE[3], "Condition")
    fig.suptitle("What goes with an auction selling (raw rates, 95% intervals)", x=0.01, ha="left", fontweight="bold",
                 fontsize=14)
    return _save(fig, path)


def fig_trajectory(t: pd.DataFrame, tr: dict, path=None):
    _style()
    t = t.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(t))
    ax.fill_between(x, t["q1"], t["q3"], color=BLUE, alpha=0.15, lw=0, label="middle 50% of auctions")
    ax.plot(x, t["median"], color=BLUE, lw=2.4, marker="o", label="median")
    for i, r in t.iterrows():
        ax.text(i, r["median"] + 0.035, f"{r['median']:.0%}", ha="center", fontsize=9.5, color=INK)
    ax.axhline(1, color=SOLD, ls="--", lw=1)
    ax.text(0, 1.015, "final price", color=SOLD, ha="left", fontsize=9)
    ax.set_xticks(x, t["bin"], rotation=0, fontsize=9)
    ax.set_xlabel("time before the auction ended")
    ax.set_ylabel("current bid as a share of the final price")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(0.3, 1.12)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title("Auction prices are set late")
    _subtitle(ax, f"{tr['n_auctions']} sold auctions; latest bid seen in each window", 1.01)
    return _save(fig, path)


# ------------------------------------------------------------------ models

def fig_importance(imp: pd.Series, title, unit, path=None, color=BLUE, top=12, xlabel="mean |SHAP value|"):
    _style()
    s = imp.head(top)[::-1]
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(s) + 1.4))
    ax.barh([LABELS.get(k, k) for k in s.index], s.values, color=color)
    for i, v in enumerate(s.values):
        ax.text(v + s.max() * 0.01, i, unit.format(v), va="center", fontsize=9.5)
    ax.set_xlim(0, s.max() * 1.18)
    _grid(ax, "x")
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    return _save(fig, path)


def fig_sale_validation(sm: dict, path=None):
    _style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    y = sm["frame"]["sold"].values
    ax = axes[0]
    for p, lab, c in [(sm["oof"], f"CatBoost (AUC {sm['metrics']['auc']:.2f})", BLUE),
                      (sm["oof_logit"], f"logistic regression (AUC {sm['metrics']['auc_logit']:.2f})", ACCENT)]:
        fpr, tpr, _ = roc_curve(y, p)
        ax.plot(fpr, tpr, color=c, lw=2, label=lab)
    ax.plot([0, 1], [0, 1], color=GRAY, ls="--", lw=1, label="chance (AUC 0.50)")
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title("Out-of-fold ROC, grouped by seller", fontsize=12)
    ax = axes[1]
    r = sm["reliability"]
    ax.plot([0, 1], [0, 1], color=GRAY, ls="--", lw=1)
    ax.errorbar(r["predicted"], r["observed"], yerr=[r["observed"] - r["lo"], r["hi"] - r["observed"]], fmt="o-",
                color=BLUE, ecolor="#9DB4D3", elinewidth=2, ms=7, label="CatBoost, out-of-fold")
    for _, q in r.iterrows():
        ax.text(q["predicted"] + 0.015, q["observed"] - 0.05, f"n={int(q['n'])}", fontsize=8, color=MUTED)
    ax.set_xlim(0, 0.85)
    ax.set_ylim(0, 0.85)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_xlabel("predicted chance of selling (quintiles)")
    ax.set_ylabel("share that sold")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title("Calibration", fontsize=12)
    return _save(fig, path)


def fig_opening_price(partial: pd.DataFrame, path=None):
    _style()
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(partial["ratio"], partial["prob"], color=BLUE, lw=2.4, marker="o")
    for _, r in partial.iterrows():
        if r["ratio"] in (0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
            ax.text(r["ratio"], r["prob"] + 0.012, f"{r['prob']:.0%}", ha="center", fontsize=9.5)
    ax.axvline(1, color=GRAY, ls="--", lw=1)
    ax.text(1.03, partial["prob"].max(), "opening bid =\nmarket value", fontsize=9, color=MUTED, va="top")
    ax.set_xscale("log")
    ax.set_xticks([0.25, 0.5, 1, 1.5, 2, 3], ["25%", "50%", "100%", "150%", "200%", "300%"])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("opening bid as a share of the median sale price (log scale)")
    ax.set_ylabel("average predicted chance of selling")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(0, max(0.6, partial["prob"].max() + 0.08))
    ax.set_title("High opening bids lower the chance an auction sells")
    _subtitle(ax, "Partial dependence from the CatBoost sale model, other features at their observed values", 1.01)
    return _save(fig, path)


def fig_waterfall(base, contrib: pd.Series, values: dict, title, path=None, top=8, money=True):
    _style()
    c = contrib.reindex(contrib.abs().sort_values(ascending=False).index)
    head, rest = c.iloc[:top], c.iloc[top:].sum()
    items = list(head.items()) + ([("other features", rest)] if len(c) > top else [])
    fig, ax = plt.subplots(figsize=(10, 0.5 * len(items) + 1.8))
    cur = base
    for i, (k, v) in enumerate(items):
        y = len(items) - i
        ax.barh(y, v, left=cur, color=POS if v > 0 else NEG, height=0.6)
        lab = LABELS.get(k, k)
        if k in values:
            val = values[k]
            lab = f"{lab} = {val}"
        ax.text(-0.01, y, lab, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=9.5)
        ax.text(max(cur, cur + v) + abs(c).max() * 0.03, y, (f"{'+' if v >= 0 else '−'}${abs(v):,.0f}" if money
                else f"{v:+.2f}"), va="center", fontsize=9.5)
        cur += v
    ax.axvline(base, color=GRAY, ls=":", lw=1)
    ax.set_yticks([])
    ax.set_xlabel("predicted sale price (USD)" if money else "log-odds")
    ax.text(base, len(items) + 0.75, f"average prediction {_money(base)}", fontsize=9.5, color=MUTED, ha="center")
    ax.text(cur, 0.25, f"this listing {_money(cur)}", fontsize=10, fontweight="bold", ha="center")
    ax.axvline(cur, color=INK, ls="--", lw=0.8)
    lo, hi = min(base, cur, *(base + np.cumsum([v for _, v in items]))), max(base, cur, *(base + np.cumsum([v for _, v in items])))
    pad = (hi - lo) * 0.25
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_ylim(-0.2, len(items) + 1.3)
    _grid(ax, "x")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=POS, label="raises prediction"), Patch(color=NEG, label="lowers prediction")],
              loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=9)
    ax.set_title(title)
    return _save(fig, path)


def fig_format_effect(fs: pd.DataFrame, path=None):
    _style()
    t = fs.reindex(D.FORMAT_ORDER)
    fig, ax = plt.subplots(figsize=(8, 3.4))
    cols = [POS if v > 0 else NEG for v in t["mean"]]
    ax.barh(t.index[::-1], t["mean"][::-1], color=cols[::-1])
    for i, (v, n) in enumerate(zip(t["mean"][::-1], t["size"][::-1])):
        ax.text(v + (1 if v >= 0 else -1), i, f"{'+' if v >= 0 else '−'}${abs(v):.0f}  (n={n})", va="center",
                ha="left" if v >= 0 else "right", fontsize=9.5)
    ax.axvline(0, color=INK, lw=0.8)
    lim = t["mean"].abs().max() * 1.9
    ax.set_xlim(-lim, lim)
    _grid(ax, "x")
    ax.set_xlabel("mean SHAP value of format (USD)")
    ax.set_title("Auctions sell for less, holding the watch fixed")
    return _save(fig, path)


def fig_cover(stats: dict, path=None):
    _style()
    fig = plt.figure(figsize=(8.5, 11))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, 8.5)
    ax.set_ylim(0, 11)
    ax.add_patch(plt.Rectangle((0, 9.25), 8.5, 0.08, color=GOLD))
    ax.text(0.7, 9.9, "PART II", fontsize=13, color=GOLD, fontweight="bold")
    ax.text(0.7, 8.55, "Plated in Gold", fontsize=40, fontweight="bold", color=INK)
    ax.text(0.7, 7.95, "From Asking to Selling", fontsize=24, color=MUTED)
    ax.text(0.7, 7.3, "What a week of tracked eBay listings says about\nwhich Apple Watches sell, and for how much",
            fontsize=13, color=INK, linespacing=1.5)
    sub = fig.add_axes([0.08, 0.27, 0.84, 0.33])
    t = stats["ask"].copy()
    t["order"] = t["model"].map(D.model_sort_key)
    t = t.sort_values("order")
    x = np.arange(len(t))
    sub.vlines(x, t["sold"], t["ask"], color="#D7DCE3", lw=4)
    sub.scatter(x, t["ask"], color=ASK, s=50, zorder=3, label="median asking price")
    sub.scatter(x, t["sold"], color=SOLD, s=50, zorder=3, label="median sold price")
    sub.set_xticks(x, t["model"], rotation=60, fontsize=9)
    sub.set_ylabel("USD, used condition")
    sub.legend(loc="upper left", fontsize=10)
    _grid(sub, "y")
    for k, (v, lab) in enumerate(stats["tiles"]):
        xx = 0.7 + k * 2.45
        ax.text(xx, 1.75, v, fontsize=22, fontweight="bold", color=BLUE if k != 2 else GOLD)
        ax.text(xx, 1.25, lab, fontsize=10, color=MUTED, linespacing=1.4, va="top")
    ax.text(0.7, 0.35, "André Davis", fontsize=12, fontweight="bold")
    ax.text(7.8, 0.35, "2026", fontsize=12, color=MUTED, ha="right")
    if path:
        fig.savefig(path, facecolor="white", dpi=220)
    plt.close(fig)
    return fig
