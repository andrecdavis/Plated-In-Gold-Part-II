"""Stage 1 (private): SQLite collection -> cleaned, de-identified public tables.

Reads the raw collection database (not published) and writes the files in
data/public/ that every later step uses:

  listings.csv.gz            one row per listing: cleaned attributes, prices and outcome
  auction_bids.csv.gz        bid observations for ended auctions (hours before end, bid, bids)
  collection_activity.csv    hourly API calls and observations by task
  collection_gaps.csv        periods of two hours or more with no observation
  collection_summary.json    totals from the collection database

Published files contain no seller usernames, item IDs, listing URLs, titles,
descriptions, images or raw API responses. Sellers are represented by a salted
HMAC key (the salt is never written to disk) and listings by a random integer.
Feedback scores are rounded to two significant figures.

    python -m src.prepare [--db data/raw/ebay_apple_watch.db]
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from collector.features import add_features
from . import PUBLIC_DIR, RAW_DB, TZ

VALID_MODELS = ({f"Series {i}" for i in range(13)} | {f"SE {i}" for i in range(1, 4)}
                | {f"Ultra {i}" for i in range(1, 5)})
VALID_SIZES = {38, 40, 41, 42, 44, 45, 46, 49}
COND_GROUP = {
    "New": "New", "Open box": "Open box", "Used": "Used",
    "Certified - Refurbished": "Refurbished", "Excellent - Refurbished": "Refurbished",
    "Very Good - Refurbished": "Refurbished", "Good - Refurbished": "Refurbished",
    "Seller refurbished": "Refurbished", "For parts or not working": "For parts", "Unknown": "Unknown",
}
GOLD = r"24k|24ct|24\s?karat"
LOT = r"\blots?\b|\bbundle\b|\bbulk\b|\bwholesale\b|\(\s*\d+\s*\)\s*apple|\b\d+\s*(?:x|pcs|pieces|units)\b"
ACCESSORY = (r"\b(?:band|strap|loop|bracelet)s?\s+only\b|\bonly\s+(?:the\s+)?(?:band|strap)\b|charg(?:er|ing)\b"
             r"|screen protector|\bbox only\b|empty box|\bbox and\b.*\bno watch\b|replacement (?:band|strap|screen|glass|battery|lcd)"
             r"|\bfor apple watch\b|compatible with apple watch|\bcable\b|\bdock\b|\bstand\b|\bskin\b|\bcover\b|bumper"
             r"|watch bands?\b(?!.*\bwatch\s+(?:series|ultra|se)\b)")
SERVICE = r"\bservice\b|no watch for sale|\bwatch not included\b"
GAP_HOURS = 2.0

LISTING_COLS = [
    "item_id", "legacy_item_id", "title", "is_auction", "is_fixed_price", "best_offer_enabled", "start_time",
    "end_time", "first_seen_at", "last_seen_at", "status", "first_price", "condition", "condition_id",
    "seller_username", "seller_feedback_score", "seller_feedback_pct", "top_rated_buying", "shipping_cost",
    "ship_to_worldwide", "location_country", "image_count", "returns_accepted", "return_period_days",
    "brand", "lot_size", "detail_fetched_at", "aspects_json",
]


def to_utc(s):
    return pd.to_datetime(s, utc=True, errors="coerce", format="ISO8601")


def round_sig(x, sig=2):
    x = pd.to_numeric(x, errors="coerce")
    out = x.copy().astype(float)
    pos = x.notna() & (x.abs() >= 1)
    mag = np.floor(np.log10(x[pos].abs())) - (sig - 1)
    out[pos] = np.round(x[pos] / 10 ** mag) * 10 ** mag
    return out


def seller_key(names: pd.Series, salt: bytes) -> pd.Series:
    """Non-reversible seller key: HMAC-SHA256 with a salt that is never stored."""
    return names.map(lambda s: None if pd.isna(s) else
                     hmac.new(salt, str(s).encode(), hashlib.sha256).hexdigest()[:12])


def robust_z(values, groups, min_n=10):
    """Robust z-score of log price within groups (median / MAD); NaN for groups below min_n."""
    logv = np.log(values.where(values > 0))
    grp = logv.groupby(groups, observed=True)
    med = grp.transform("median")
    mad = grp.transform(lambda s: (s - s.median()).abs().median())
    n = grp.transform("count")
    z = 0.6745 * (logv - med) / mad.replace(0, np.nan)
    return z.where(n >= min_n)


def find_gaps(observed: pd.Series, hours=GAP_HOURS) -> pd.DataFrame:
    t = observed.sort_values().reset_index(drop=True)
    gap = t.diff()
    m = gap >= pd.Timedelta(hours=hours)
    g = pd.DataFrame({"start": t.shift(1)[m], "end": t[m]}).reset_index(drop=True)
    g["hours"] = (g["end"] - g["start"]) / pd.Timedelta(hours=1)
    return g


def gold_kind(title_norm: str, model) -> str:
    """Split gold-keyword listings into plated watches, anodized watches with gold parts, bands and services."""
    if re.search(SERVICE, title_norm):
        return "Plating service, no watch"
    if re.search(r"\bbands\b.*\ball series\b", title_norm):
        return "Band only"
    if "anodiz" in title_norm:
        return "Anodized watch, 24k parts"
    return "Gold-plated watch"


def load(conn) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    listings = pd.read_sql_query(f"SELECT {', '.join(LISTING_COLS)} FROM listings", conn)
    snaps = pd.read_sql_query(
        "SELECT item_id, observed_at, source, price, current_bid, bid_count, reserve_price_met, "
        "est_sold_qty, est_available_qty, http_status FROM snapshots", conn)
    outcomes = pd.read_sql_query("SELECT * FROM outcomes", conn)
    return listings, snaps, outcomes


def clean(listings: pd.DataFrame, snaps: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    df = listings.copy()
    for c in ["start_time", "end_time", "first_seen_at", "last_seen_at", "detail_fetched_at"]:
        df[c] = to_utc(df[c])
    df["aspects"] = df["aspects_json"].map(lambda s: json.loads(s) if isinstance(s, str) and s else {})
    df = add_features(df)

    # model and case-size corrections (labels outside Apple's lineup come from other numbers in the title)
    df["model"] = df["model"].replace({"Series 7000": "Series 0", "SE 2022": "SE 2"})
    df["model"] = df["model"].where(df["model"].isin(VALID_MODELS))
    df["family"] = df["model"].map(lambda m: m.split()[0] if isinstance(m, str) else None)
    df.loc[~df["case_size"].isin(VALID_SIZES), "case_size"] = np.nan
    df["condition_group"] = df["condition_std"].map(COND_GROUP)

    t = df["title_norm"]
    df["is_lot"] = t.str.contains(LOT, regex=True) | (df["lot_size"].fillna(0) > 1) | (df["is_bundle"] == 1)
    df["is_accessory"] = (t.str.contains(ACCESSORY, regex=True) | t.str.contains(SERVICE, regex=True)) & ~df["is_lot"]
    df["is_other"] = ((~t.str.contains("watch", regex=False) | t.str.contains(r"iphone|ipad|macbook|airpods", regex=True))
                      & ~t.str.contains(r"apple\s*watch|\bseries\s*\d|\bultra\b|\bwatch\s*se\b", regex=True))
    df["is_single_watch"] = ~(df["is_lot"] | df["is_accessory"] | df["is_other"])
    df["gold"] = t.str.contains(GOLD, regex=True).astype(int)
    df["gold_kind"] = [gold_kind(tt, m) if g else None for tt, m, g in zip(t, df["model"], df["gold"])]

    # last pre-end observation, first observation, lifetime sold quantity, repricing
    s = snaps.copy()
    s["observed_at"] = to_utc(s["observed_at"])
    s = s.sort_values(["item_id", "observed_at"])
    live = s[(s["source"] != "end_check") & (s["http_status"].fillna(200) == 200)]
    last = live.groupby("item_id").tail(1).set_index("item_id")
    first = live.groupby("item_id").head(1).set_index("item_id")
    df = df.join(last[["price", "current_bid", "bid_count", "observed_at"]]
                 .rename(columns={"price": "last_price", "current_bid": "last_bid", "bid_count": "last_bid_count",
                                  "observed_at": "last_observed_at"}), on="item_id")
    df = df.join(first[["bid_count"]].rename(columns={"bid_count": "first_bid_count"}), on="item_id")
    df["available_qty"] = df["item_id"].map(s.dropna(subset=["est_available_qty"]).groupby("item_id")["est_available_qty"].last())
    sold_qty = s.dropna(subset=["est_sold_qty"]).groupby("item_id")["est_sold_qty"].agg(["first", "last"])
    df = df.join(sold_qty.rename(columns={"first": "sold_qty_first", "last": "sold_qty_lifetime"}), on="item_id")
    px = live.dropna(subset=["price"]).groupby("item_id")["price"].agg(["first", "last", "size", "min", "max"])
    df = df.join(px.rename(columns={"first": "price_first_obs", "last": "price_last_obs", "size": "n_price_obs",
                                    "min": "price_min_obs", "max": "price_max_obs"}), on="item_id")
    reserve = live.groupby("item_id")["reserve_price_met"].apply(lambda x: x.notna().any())
    df["has_reserve"] = df["item_id"].map(reserve).fillna(False)

    df["price"] = df["last_bid"].where(df["is_auction"] == 1).fillna(df["last_price"])
    df["seller_feedback_pct"] = df["seller_feedback_pct"].mask(df["seller_feedback_pct"] == 0)
    df["free_shipping"] = (df["shipping_cost"] == 0).astype("boolean").mask(df["shipping_cost"].isna())
    df["format"] = np.select([df["is_auction"] == 1, df["best_offer_enabled"] == 1],
                             ["Auction", "Fixed price + Best Offer"], "Fixed price")
    df["auction_with_bin"] = ((df["is_auction"] == 1) & (df["is_fixed_price"] == 1)).astype(int)
    df["gtc"] = ((df["is_auction"] == 0) & df["end_time"].isna()).astype(int)
    df["detail"] = df["detail_fetched_at"].notna().astype(int)

    # outcomes
    o = outcomes.copy()
    o["ended_at"] = to_utc(o["ended_at"])
    df = df.merge(o[["item_id", "ended_at", "outcome", "final_price", "units_sold", "bid_count", "method", "confidence"]]
                  .rename(columns={"bid_count": "final_bids", "method": "outcome_method",
                                   "confidence": "outcome_confidence"}), on="item_id", how="left")
    df["outcome"] = df["outcome"].fillna("active")
    # an auction that ended with no bids but whose sold counter rose sold through Buy It Now or an accepted offer
    bin_sale = (df["is_auction"] == 1) & (df["outcome"] == "unsold") & (df["sold_qty_lifetime"] > 0)
    df.loc[bin_sale, ["outcome", "final_price", "units_sold", "outcome_confidence"]] = \
        ["sold", np.nan, 1, "medium"]
    df.loc[bin_sale, "final_price"] = df.loc[bin_sale, "last_price"]

    # price outliers: robust z of log price within model x condition group (single watches only)
    single = df["is_single_watch"] & df["model"].notna()
    df["price_outlier"] = False
    z = robust_z(df.loc[single, "price"], [df.loc[single, "model"], df.loc[single, "condition_group"]])
    df.loc[z.index, "price_outlier"] = z.abs() > 3.5
    sold = single & (df["outcome"] == "sold") & (df["final_price"] > 0)
    z2 = robust_z(df.loc[sold, "final_price"], [df.loc[sold, "model"], df.loc[sold, "condition_group"]], min_n=8)
    df["final_price_outlier"] = False
    df.loc[z2.index, "final_price_outlier"] = z2.abs() > 3.5
    df["seller_listings"] = df["seller_username"].map(df["seller_username"].value_counts())
    return df


PUBLIC_COLS = [
    "listing", "seller", "seller_listings", "format", "is_auction", "best_offer_enabled", "auction_with_bin",
    "has_reserve", "gtc", "detail", "model", "family", "condition_group", "case_size", "material", "connectivity",
    "cellular", "hermes", "titanium", "premium_band", "ceramic", "gold", "gold_kind", "is_single_watch", "is_lot",
    "is_accessory", "is_other", "price_outlier", "final_price_outlier", "start_time", "end_time", "first_seen_at",
    "last_observed_at", "ended_at", "first_price", "first_bid_count", "price", "price_first_obs", "price_min_obs",
    "price_max_obs", "n_price_obs", "last_bid_count", "outcome", "outcome_method", "outcome_confidence",
    "final_price", "units_sold", "final_bids", "sold_qty_first", "sold_qty_lifetime", "available_qty", "shipping_cost",
    "free_shipping", "ship_to_worldwide", "returns_accepted", "return_period_days", "image_count",
    "top_rated_buying", "seller_feedback_score", "seller_feedback_pct", "us_location",
]


def to_public(df: pd.DataFrame, salt: bytes, rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    out = df.copy()
    out["listing"] = rng.permutation(len(out)) + 1
    out["seller"] = seller_key(out["seller_username"], salt)
    out["seller_feedback_score"] = round_sig(out["seller_feedback_score"])
    out["us_location"] = (out["location_country"] == "US").astype(int)
    for c in ["start_time", "end_time", "first_seen_at", "last_observed_at", "ended_at"]:
        out[c] = out[c].dt.strftime("%Y-%m-%dT%H:%MZ")
    key_map = dict(zip(df["item_id"], out["listing"]))
    return out[PUBLIC_COLS].sort_values("listing").reset_index(drop=True), key_map


def auction_bids(df: pd.DataFrame, snaps: pd.DataFrame, key_map: dict) -> pd.DataFrame:
    """Bid observations for ended auctions with a known outcome, as hours before the end."""
    a = df[(df["is_auction"] == 1) & df["outcome"].isin(["sold", "unsold", "reserve_not_met"])]
    s = snaps[snaps["item_id"].isin(a["item_id"]) & (snaps["source"] != "end_check")
              & snaps["current_bid"].notna()].copy()
    s["observed_at"] = to_utc(s["observed_at"])
    s = s.merge(a[["item_id", "ended_at"]], on="item_id")
    s["hours_before_end"] = (s["ended_at"] - s["observed_at"]) / pd.Timedelta(hours=1)
    s = s[s["hours_before_end"] >= 0]
    s["listing"] = s["item_id"].map(key_map)
    return (s[["listing", "hours_before_end", "current_bid", "bid_count", "source"]]
            .round({"hours_before_end": 3}).sort_values(["listing", "hours_before_end"], ascending=[True, False]))


def collection_activity(conn, snaps) -> pd.DataFrame:
    calls = pd.read_sql_query("SELECT ts, endpoint, status FROM api_calls", conn)
    calls["hour"] = to_utc(calls["ts"]).dt.floor("h")
    calls["kind"] = np.select([calls["endpoint"].str.contains("item_summary/search"),
                               calls["endpoint"].str.startswith("/item/")], ["search", "getItems"], "getItem")
    a = calls.pivot_table(index="hour", columns="kind", values="ts", aggfunc="size", fill_value=0).add_prefix("calls_")
    s = snaps[["observed_at", "source"]].copy()
    s["hour"] = to_utc(s["observed_at"]).dt.floor("h")
    b = s.pivot_table(index="hour", columns="source", values="observed_at", aggfunc="size", fill_value=0).add_prefix("obs_")
    out = a.join(b, how="outer").fillna(0).astype(int).reset_index()
    out["hour"] = out["hour"].dt.strftime("%Y-%m-%dT%H:00Z")
    return out


def summary(conn, df, snaps, gaps) -> dict:
    q = lambda s: conn.execute(s).fetchone()[0]
    calls = pd.read_sql_query("SELECT endpoint, status FROM api_calls", conn)
    obs = to_utc(snaps["observed_at"])
    return dict(
        listings=int(len(df)), snapshots=int(len(snaps)), outcomes=int(q("SELECT COUNT(*) FROM outcomes")),
        api_calls=int(len(calls)),
        api_calls_by_kind={k: int(v) for k, v in calls["endpoint"].map(
            lambda e: "search" if "item_summary/search" in e else ("getItems" if e.startswith("/item/") else "getItem"))
            .value_counts().items()},
        api_status={str(int(k)): int(v) for k, v in calls["status"].dropna().value_counts().items()},
        sweeps=int(q("SELECT COUNT(*) FROM sweeps")),
        sweep_items=[int(r[0]) for r in conn.execute("SELECT items_seen FROM sweeps ORDER BY sweep_id")],
        snapshots_by_source={k: int(v) for k, v in snaps["source"].value_counts().items()},
        outcomes_by=[dict(outcome=r[0], method=r[1], confidence=r[2], n=int(r[3])) for r in conn.execute(
            "SELECT outcome, method, confidence, COUNT(*) FROM outcomes GROUP BY 1, 2, 3")],
        first_observation=obs.min().strftime("%Y-%m-%dT%H:%MZ"), last_observation=obs.max().strftime("%Y-%m-%dT%H:%MZ"),
        sellers=int(df["seller_username"].nunique()),
        legacy_listings=int(df["legacy_item_id"].nunique()),
        detail_share=float(df["detail_fetched_at"].notna().mean()),
        gaps=[dict(start=g.start.strftime("%Y-%m-%dT%H:%MZ"), end=g.end.strftime("%Y-%m-%dT%H:%MZ"),
                   hours=round(g.hours, 2)) for g in gaps.itertuples()],
        brand_missing_share=float(df["brand"].isna().mean()),
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(RAW_DB))
    ap.add_argument("--out", default=str(PUBLIC_DIR))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    salt = os.environ.get("PIG2_SELLER_SALT", "").encode() or os.urandom(32)
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(salt).digest()[:8], "big"))
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    listings, snaps, outcomes = load(conn)
    df = clean(listings, snaps, outcomes)
    gaps = find_gaps(to_utc(snaps["observed_at"]))
    pub, key_map = to_public(df, salt, rng)
    pub.to_csv(out / "listings.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    auction_bids(df, snaps, key_map).to_csv(out / "auction_bids.csv.gz", index=False,
                                            compression={"method": "gzip", "mtime": 0})
    collection_activity(conn, snaps).to_csv(out / "collection_activity.csv", index=False)
    gaps.assign(start=gaps["start"].dt.strftime("%Y-%m-%dT%H:%MZ"), end=gaps["end"].dt.strftime("%Y-%m-%dT%H:%MZ")) \
        .round(2).to_csv(out / "collection_gaps.csv", index=False)
    (out / "collection_summary.json").write_text(json.dumps(summary(conn, df, snaps, gaps), indent=1))
    for f in sorted(out.iterdir()):
        print(f"{f.relative_to(out.parent.parent)}  {f.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
