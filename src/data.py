"""Load the published tables and derive the analysis samples."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from . import PUBLIC_DIR, TZ

MODEL_ORDER = ([f"Series {i}" for i in range(13)] + [f"SE {i}" for i in range(1, 4)]
               + [f"Ultra {i}" for i in range(1, 5)])
COND_ORDER = ["New", "Open box", "Refurbished", "Used", "For parts"]
FORMAT_ORDER = ["Auction", "Fixed price", "Fixed price + Best Offer"]
FEEDBACK_BINS = [-np.inf, 0, 10, 100, 1000, 10000, np.inf]
FEEDBACK_LABELS = ["≤0", "1–10", "11–100", "101–1k", "1k–10k", "10k+"]
KNOWN = ["sold", "unsold", "reserve_not_met"]
DATES = ["start_time", "end_time", "first_seen_at", "last_observed_at", "ended_at"]


@lru_cache(maxsize=1)
def summary() -> dict:
    return json.loads((PUBLIC_DIR / "collection_summary.json").read_text())


def window() -> tuple[pd.Timestamp, pd.Timestamp]:
    s = summary()
    return pd.Timestamp(s["first_observation"]), pd.Timestamp(s["last_observation"])


def gaps() -> pd.DataFrame:
    g = pd.read_csv(PUBLIC_DIR / "collection_gaps.csv")
    g["start"] = pd.to_datetime(g["start"], utc=True)
    g["end"] = pd.to_datetime(g["end"], utc=True)
    return g


def model_sort_key(m):
    return MODEL_ORDER.index(m) if m in MODEL_ORDER else 99


@lru_cache(maxsize=1)
def _listings() -> pd.DataFrame:
    df = pd.read_csv(PUBLIC_DIR / "listings.csv.gz", low_memory=False)
    for c in DATES:
        df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601")
    for c in ["is_single_watch", "is_lot", "is_accessory", "is_other", "price_outlier", "final_price_outlier",
              "has_reserve"]:
        df[c] = df[c].astype(str).str.lower().eq("true")
    df["sold"] = (df["outcome"] == "sold").astype(int)
    df["known"] = df["outcome"].isin(KNOWN)
    df["ended"] = df["outcome"] != "active"
    df["feedback_bin"] = pd.cut(df["seller_feedback_score"], FEEDBACK_BINS, labels=FEEDBACK_LABELS)
    df["free_shipping"] = df["free_shipping"].map({"True": True, "False": False, True: True, False: False}).astype("boolean")
    df["end_local"] = df["ended_at"].dt.tz_convert(TZ)
    start, end = window()
    df["age_years"] = (end - df["start_time"]).dt.total_seconds() / (365.25 * 86400)
    df["analysis"] = df["is_single_watch"] & df["model"].notna() & (df["gold"] == 0) & ~df["price_outlier"]
    return df


def listings() -> pd.DataFrame:
    return _listings().copy()


def watches() -> pd.DataFrame:
    """Single watches with an identified model, excluding gold-plated listings and price outliers."""
    d = listings()
    return d[d["analysis"]].copy()


def sold_watches() -> pd.DataFrame:
    w = watches()
    return w[(w["outcome"] == "sold") & (w["final_price"] > 0) & ~w["final_price_outlier"]].copy()


def ended_auctions() -> pd.DataFrame:
    """Auctions of single watches (gold excluded) with a known outcome. No price-outlier filter: a low
    current bid on an unsold auction is not a data error."""
    d = listings()
    keep = d["is_single_watch"] & d["model"].notna() & (d["gold"] == 0)
    return d[keep & (d["is_auction"] == 1) & d["outcome"].isin(KNOWN)].copy()


def auction_bids() -> pd.DataFrame:
    return pd.read_csv(PUBLIC_DIR / "auction_bids.csv.gz")


def activity() -> pd.DataFrame:
    a = pd.read_csv(PUBLIC_DIR / "collection_activity.csv")
    a["hour"] = pd.to_datetime(a["hour"], utc=True)
    return a
