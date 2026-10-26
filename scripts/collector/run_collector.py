"""Run the eBay Apple Watch collector.

Examples
  python scripts/collector/run_collector.py --once                 # one scheduling pass (cron-friendly)
  python scripts/collector/run_collector.py --days 7               # long-running process for one week
  python scripts/collector/run_collector.py --mock --simulate-hours 72   # offline run against the mock market
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
from datetime import timedelta
from logging.handlers import RotatingFileHandler

import _bootstrap  # noqa: F401

from collector import LOG_DIR
from collector import db
from collector.client import EbayClient
from collector.collector import Collector
from collector.config import Settings
from collector.timeutil import Clock, FakeClock, parse_iso, to_iso


def setup_logging(verbose: bool) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    fh = RotatingFileHandler(LOG_DIR / "collector.log", maxBytes=20_000_000, backupCount=5)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run one scheduling pass and exit")
    mode.add_argument("--days", type=float, help="run for this many days, then exit")
    ap.add_argument("--tick", type=int, default=60, help="seconds between scheduling passes")
    ap.add_argument("--db", help="SQLite path (default data/raw/ebay_apple_watch.db)")
    ap.add_argument("--mock", action="store_true", help="use the offline mock market instead of eBay")
    ap.add_argument("--simulate-hours", type=float, default=48, help="mock only: simulated hours to run")
    ap.add_argument("--mock-items", type=int, default=400, help="mock only: listings in the synthetic market")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    setup_logging(args.verbose)
    log = logging.getLogger("run_collector")

    overrides = {}
    if args.db:
        overrides["db_path"] = args.db
    elif args.mock:
        overrides["db_path"] = str(_bootstrap.ROOT / "data" / "raw" / "mock_ebay_apple_watch.db")
    settings = Settings.from_env(**overrides)
    conn = db.connect(settings.db_path)

    if args.mock:
        from collector.mock import MockMarket
        clock = FakeClock(parse_iso("2026-10-19T00:00:00Z"))
        settings.client_id, settings.client_secret = "mock-id", "mock-secret"
        market = MockMarket(clock, n_items=args.mock_items, error_rate=0.01)
        client = EbayClient(settings, conn, transport=market, clock=clock)
        collector = Collector(settings, conn, client, clock)
        collector.run(until=clock.now() + timedelta(hours=args.simulate_hours), tick_seconds=args.tick)
        log.info("close-out: %s", collector.close_out())
        _summary(conn, log)
        return 0

    if not (settings.client_id and settings.client_secret):
        log.error("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET (see .env.example).")
        return 2
    clock = Clock()
    client = EbayClient(settings, conn, clock=clock)
    collector = Collector(settings, conn, client, clock)

    if args.once:
        log.info("pass: %s", collector.tick())
        return 0

    stop = {"flag": False}

    def _handle(signum, _frame):
        log.info("signal %s received, finishing current pass", signum)
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    until = None
    if args.days:
        started = db.get_meta(conn, "collection_started_at")
        if not started:
            started = to_iso(clock.now())
            db.set_meta(conn, "collection_started_at", started)
            conn.commit()
        until = parse_iso(started) + timedelta(days=args.days)
        log.info("collecting until %s UTC", to_iso(until))
    collector.run(until=until, tick_seconds=args.tick, stop_flag=lambda: stop["flag"])
    if until is not None and clock.now() >= until:
        log.info("collection window complete; close-out: %s", collector.close_out())
    _summary(conn, log)
    return 0


def _summary(conn, log) -> None:
    q = lambda sql: conn.execute(sql).fetchone()[0]
    log.info("listings=%d snapshots=%d outcomes=%d api_calls=%d",
             q("SELECT COUNT(*) FROM listings"), q("SELECT COUNT(*) FROM snapshots"),
             q("SELECT COUNT(*) FROM outcomes"), q("SELECT COUNT(*) FROM api_calls"))
    for row in conn.execute("SELECT outcome, method, COUNT(*) n FROM outcomes GROUP BY 1, 2 ORDER BY 3 DESC"):
        log.info("  %-16s %-22s %d", row[0], row[1], row[2])


if __name__ == "__main__":
    raise SystemExit(main())
