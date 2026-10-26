"""Export the SQLite store to CSV files in data/processed/."""
import argparse

import _bootstrap  # noqa: F401

from collector import db
from collector.config import Settings
from collector.export import export_all


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", help="SQLite path (default data/raw/ebay_apple_watch.db)")
    ap.add_argument("--out", help="output folder (default data/processed)")
    args = ap.parse_args(argv)
    settings = Settings.from_env(**({"db_path": args.db} if args.db else {}))
    conn = db.connect(settings.db_path)
    paths = export_all(conn, **({"out_dir": args.out} if args.out else {}))
    for name, path in paths.items():
        print(f"{name:18s} {path}")


if __name__ == "__main__":
    main()
