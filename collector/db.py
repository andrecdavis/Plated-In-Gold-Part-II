"""SQLite storage: listings, snapshots, outcomes, and collector bookkeeping."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    item_id                TEXT PRIMARY KEY,
    legacy_item_id         TEXT,
    title                  TEXT,
    item_web_url           TEXT,
    category_id            TEXT,
    category_path          TEXT,
    buying_options         TEXT,
    is_auction             INTEGER,
    is_fixed_price         INTEGER,
    best_offer_enabled     INTEGER,
    start_time             TEXT,
    end_time               TEXT,
    first_seen_at          TEXT NOT NULL,
    last_seen_at           TEXT NOT NULL,
    last_seen_sweep        INTEGER,
    missing_sweeps         INTEGER DEFAULT 0,
    status                 TEXT DEFAULT 'active',
    detail_fetched_at      TEXT,
    detail_error           TEXT,
    first_price            REAL,
    currency               TEXT,
    condition              TEXT,
    condition_id           TEXT,
    condition_description  TEXT,
    seller_username        TEXT,
    seller_feedback_score  INTEGER,
    seller_feedback_pct    REAL,
    seller_account_type    TEXT,
    top_rated_buying       INTEGER,
    shipping_cost          REAL,
    shipping_cost_type     TEXT,
    shipping_options_json  TEXT,
    ship_to_worldwide      INTEGER,
    location_country       TEXT,
    location_state         TEXT,
    location_city          TEXT,
    location_postal        TEXT,
    image_count            INTEGER,
    returns_accepted       INTEGER,
    return_period_days     INTEGER,
    return_shipping_payer  TEXT,
    epid                   TEXT,
    gtin                   TEXT,
    mpn                    TEXT,
    brand                  TEXT,
    color                  TEXT,
    lot_size               INTEGER,
    quantity_limit         INTEGER,
    original_price         REAL,
    short_description      TEXT,
    description_html       TEXT,
    description_text       TEXT,
    aspects_json           TEXT,
    raw_summary_json       TEXT,
    raw_detail_json        TEXT
);
CREATE INDEX IF NOT EXISTS ix_listings_end ON listings(end_time);
CREATE INDEX IF NOT EXISTS ix_listings_status ON listings(status);

CREATE TABLE IF NOT EXISTS snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id             TEXT NOT NULL,
    observed_at         TEXT NOT NULL,
    source              TEXT NOT NULL,
    price               REAL,
    current_bid         REAL,
    bid_count           INTEGER,
    unique_bidder_count INTEGER,
    reserve_price_met   INTEGER,
    availability_status TEXT,
    est_available_qty   INTEGER,
    est_sold_qty        INTEGER,
    shipping_cost       REAL,
    end_time            TEXT,
    http_status         INTEGER,
    UNIQUE(item_id, observed_at, source)
);
CREATE INDEX IF NOT EXISTS ix_snap_item ON snapshots(item_id, observed_at);

CREATE TABLE IF NOT EXISTS outcomes (
    item_id        TEXT PRIMARY KEY,
    determined_at  TEXT NOT NULL,
    ended_at       TEXT,
    outcome        TEXT NOT NULL,
    final_price    REAL,
    units_sold     INTEGER,
    bid_count      INTEGER,
    method         TEXT NOT NULL,
    confidence     TEXT NOT NULL,
    evidence       TEXT
);

CREATE TABLE IF NOT EXISTS end_queue (
    item_id      TEXT PRIMARY KEY,
    reason       TEXT NOT NULL,
    next_due_at  TEXT NOT NULL,
    attempts     INTEGER DEFAULT 0,
    finalized    INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_queue_due ON end_queue(finalized, next_due_at);

CREATE TABLE IF NOT EXISTS sales_insights (
    item_id          TEXT,
    last_sold_date   TEXT,
    last_sold_price  REAL,
    total_sold_qty   INTEGER,
    title            TEXT,
    condition        TEXT,
    raw_json         TEXT,
    fetched_at       TEXT,
    PRIMARY KEY (item_id, last_sold_date)
);

CREATE TABLE IF NOT EXISTS api_calls (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    api       TEXT NOT NULL,
    endpoint  TEXT NOT NULL,
    status    INTEGER
);
CREATE INDEX IF NOT EXISTS ix_calls_ts ON api_calls(ts);

CREATE TABLE IF NOT EXISTS task_runs (
    task        TEXT PRIMARY KEY,
    last_run_at TEXT,
    last_status TEXT
);

CREATE TABLE IF NOT EXISTS sweeps (
    sweep_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    items_seen   INTEGER DEFAULT 0,
    calls_used   INTEGER DEFAULT 0,
    state_json   TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = str(path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, table: str, row: dict, key: str | tuple = "item_id",
           keep_existing: tuple = ()) -> None:
    """Insert or update. Columns in `keep_existing` are only written when currently NULL;
    None values never overwrite stored values."""
    keys = (key,) if isinstance(key, str) else tuple(key)
    cols = list(row)
    placeholders = ", ".join("?" for _ in cols)
    updates = []
    for c in cols:
        if c in keys:
            continue
        if c in keep_existing:
            updates.append(f"{c} = COALESCE({table}.{c}, excluded.{c})")
        else:
            updates.append(f"{c} = COALESCE(excluded.{c}, {table}.{c})")
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    if updates:
        sql += f" ON CONFLICT({', '.join(keys)}) DO UPDATE SET {', '.join(updates)}"
    else:
        sql += " ON CONFLICT DO NOTHING"
    conn.execute(sql, [_coerce(row[c]) for c in cols])


def insert_snapshot(conn: sqlite3.Connection, snap: dict) -> None:
    cols = list(snap)
    conn.execute(
        f"INSERT OR IGNORE INTO snapshots ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        [_coerce(snap[c]) for c in cols],
    )


def _coerce(v):
    if isinstance(v, (dict, list, tuple)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return int(v)
    return v


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value) -> None:
    conn.execute("INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (key, str(value)))
