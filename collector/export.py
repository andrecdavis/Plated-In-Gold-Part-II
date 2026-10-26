"""Build analysis tables from the SQLite store and write them to data/processed/."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import PROCESSED_DIR
from .features import add_features

LISTING_COLS = [
    "item_id", "legacy_item_id", "title", "item_web_url", "buying_options", "is_auction", "is_fixed_price",
    "best_offer_enabled", "start_time", "end_time", "first_seen_at", "last_seen_at", "status",
    "first_price", "currency", "condition", "condition_id", "condition_description", "seller_username",
    "seller_feedback_score", "seller_feedback_pct", "seller_account_type", "top_rated_buying",
    "shipping_cost", "shipping_cost_type", "ship_to_worldwide", "location_country", "location_state",
    "location_city", "location_postal", "image_count", "returns_accepted", "return_period_days",
    "return_shipping_payer", "epid", "gtin", "mpn", "brand", "color", "lot_size", "quantity_limit",
    "original_price", "short_description", "description_text", "aspects_json", "detail_fetched_at",
]

PLATED_COLS = ["condition", "case_size", "country", "price", "seller_id", "worldwide_shipping", "title",
               "model", "family", "hermes", "cellular", "titanium", "gold", "premium_band", "ceramic",
               "power_seller"]


def load_listings(conn) -> pd.DataFrame:
    df = pd.read_sql_query(f"SELECT {', '.join(LISTING_COLS)} FROM listings", conn)
    last = pd.read_sql_query(
        """SELECT s.item_id, s.price AS last_price, s.current_bid AS last_bid, s.bid_count AS last_bid_count,
                  s.observed_at AS last_observed_at
           FROM snapshots s
           JOIN (SELECT item_id, MAX(id) AS id FROM snapshots
                 WHERE source != 'end_check' AND (http_status IS NULL OR http_status = 200)
                 GROUP BY item_id) m ON s.id = m.id""", conn)
    n_snap = pd.read_sql_query("SELECT item_id, COUNT(*) AS n_snapshots FROM snapshots GROUP BY item_id", conn)
    out = pd.read_sql_query(
        "SELECT item_id, outcome, final_price, units_sold, bid_count AS final_bid_count, method AS outcome_method, "
        "confidence AS outcome_confidence, ended_at FROM outcomes", conn)
    df = df.merge(last, on="item_id", how="left").merge(n_snap, on="item_id", how="left") \
           .merge(out, on="item_id", how="left")
    df["outcome"] = df["outcome"].fillna("active")
    df["aspects"] = df["aspects_json"].map(lambda s: json.loads(s) if isinstance(s, str) and s else {})
    df = add_features(df)
    df["price"] = df["last_bid"].fillna(df["last_price"])
    df["sold"] = (df["outcome"] == "sold").astype(int)
    start = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    end = pd.to_datetime(df["ended_at"].fillna(df["end_time"]), utc=True, errors="coerce")
    df["duration_hours"] = (end - start).dt.total_seconds() / 3600
    return df


def plated_compatible(df: pd.DataFrame, max_price: float = 2000) -> pd.DataFrame:
    """Same columns and filters as the Plated in Gold cleaned dataset, plus sale outcome."""
    d = df[(df["brand"].fillna("Apple") == "Apple") & (df["is_bundle"] == 0) & df["model"].notna()
           & (df["price"] <= max_price)].copy()
    d["condition"] = d["condition_std"]
    d["title"] = d["title_norm"]
    return d[PLATED_COLS + ["material", "connectivity", "outcome", "final_price", "item_id"]]


def export_all(conn, out_dir: Path = PROCESSED_DIR) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load_listings(conn)
    paths = {
        "listings": out_dir / "listings.csv",
        "snapshots": out_dir / "snapshots.csv",
        "outcomes": out_dir / "outcomes.csv",
        "plated_compatible": out_dir / "apple_watch_plated_compatible.csv",
    }
    df.drop(columns=["aspects"]).to_csv(paths["listings"], index=False)
    pd.read_sql_query("SELECT * FROM snapshots ORDER BY item_id, observed_at", conn).to_csv(paths["snapshots"], index=False)
    pd.read_sql_query("SELECT * FROM outcomes", conn).to_csv(paths["outcomes"], index=False)
    plated_compatible(df).to_csv(paths["plated_compatible"], index=False)
    return paths
