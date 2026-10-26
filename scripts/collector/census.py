"""Measure the market size per price band and project the daily API call budget.

Uses one search call per band (limit=1) plus one rate-limit lookup, so it is
cheap to run before starting a collection.
"""
import argparse
import math

import _bootstrap  # noqa: F401

from collector import db
from collector.client import EbayClient
from collector.config import Settings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args(argv)
    settings = Settings.from_env(db_path=":memory:")
    conn = db.connect(":memory:")
    if args.mock:
        from collector.mock import MockMarket
        from collector.timeutil import FakeClock, parse_iso
        clock = FakeClock(parse_iso("2026-10-19T00:00:00Z"))
        settings.client_id = settings.client_secret = "mock"
        client = EbayClient(settings, conn, transport=MockMarket(clock, n_items=400), clock=clock)
    else:
        client = EbayClient(settings, conn)

    total_items, sweep_calls = 0, 0
    print(f"{'band (USD)':>16} {'listings':>9} {'pages':>6}")
    for lo, hi in settings.price_bands:
        body = client.search(filters=[f"price:[{lo}..{hi}]", "priceCurrency:USD"], limit=1)
        n = body.get("total", 0)
        pages = math.ceil(n / settings.page_size)
        splits = max(1, math.ceil(n / settings.result_window))
        total_items += n
        sweep_calls += pages + splits
        flag = "  (split at run time)" if n > settings.result_window else ""
        print(f"{lo:>7}-{hi:<8} {n:>9} {pages:>6}{flag}")
    auctions = client.search(filters=["buyingOptions:{AUCTION}"], limit=1).get("total", 0)
    print(f"\nactive Apple listings in category {settings.category_id}: {total_items}")
    print(f"active auctions: {auctions}")
    print(f"calls for one full sweep: ~{sweep_calls}")
    try:
        rl = client.rate_limits()
        for api in rl.get("rateLimits", []):
            for res in api.get("resources", []):
                for rate in res.get("rates", []):
                    print(f"rate limit {res['name']}: {rate.get('remaining')} of {rate.get('limit')} remaining, "
                          f"window {rate.get('timeWindow')}s")
    except Exception as exc:  # the analytics endpoint is informational only
        print(f"rate limit lookup unavailable: {exc}")


if __name__ == "__main__":
    main()
