"""Print collection progress and API usage from the SQLite store."""
import argparse

import _bootstrap  # noqa: F401

from collector import db
from collector.config import Settings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db")
    args = ap.parse_args(argv)
    s = Settings.from_env(**({"db_path": args.db} if args.db else {}))
    conn = db.connect(s.db_path)
    q = lambda sql, *p: conn.execute(sql, p).fetchone()[0]
    print("heartbeat (UTC):     ", db.get_meta(conn, "heartbeat"))
    print("listings:            ", q("SELECT COUNT(*) FROM listings"))
    print("  with full details: ", q("SELECT COUNT(*) FROM listings WHERE detail_fetched_at IS NOT NULL"))
    print("  auctions:          ", q("SELECT COUNT(*) FROM listings WHERE is_auction = 1"))
    print("snapshots:           ", q("SELECT COUNT(*) FROM snapshots"))
    print("pending end checks:  ", q("SELECT COUNT(*) FROM end_queue WHERE finalized = 0"))
    print("outcomes:            ", q("SELECT COUNT(*) FROM outcomes"))
    for r in conn.execute("SELECT outcome, method, confidence, COUNT(*) FROM outcomes GROUP BY 1, 2, 3 ORDER BY 4 DESC"):
        print(f"    {r[0]:16s} {r[1]:22s} {r[2]:7s} {r[3]}")
    print("sweeps completed:    ", q("SELECT COUNT(*) FROM sweeps WHERE finished_at IS NOT NULL"))
    print("Browse calls, last 24h:", q("SELECT COUNT(*) FROM api_calls WHERE api = 'browse' "
                                       "AND ts > strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-1 day')"))
    for r in conn.execute("SELECT task, last_run_at, last_status FROM task_runs ORDER BY task"):
        print(f"    {r[0]:14s} {r[1]}  {r[2]}")


if __name__ == "__main__":
    main()
