"""Aggregate Part I's asking prices by model into data/public/part1_model_prices.csv.

Part I (github.com/andrecdavis/Plated-In-Gold) web-scraped asking prices from online
marketplaces. This script needs a local clone of that repository and writes only
per-model aggregates.

    python scripts/part1_bridge.py --part1 ../Plated-In-Gold
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part1", required=True, help="path to a clone of the Part I repository")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(a.part1).resolve()))
    from src.data import load_clean  # Part I's loader
    df = load_clean()
    g = df.groupby("model").agg(part1_mean_ask=("price", "mean"), part1_median_ask=("price", "median"),
                                part1_n=("price", "size"), part1_gold_share=("gold", "mean"))
    ng = df[df["gold"] == 0].groupby("model")["price"].mean().rename("part1_mean_ask_no_gold")
    out = g.join(ng).round(2).reset_index()
    out.to_csv(ROOT / "data" / "public" / "part1_model_prices.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
