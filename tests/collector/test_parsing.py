import json

from collector.parsing import (detail_to_listing, detail_to_snapshot, html_to_text, summary_to_listing,
                         summary_to_snapshot)
from tests.collector.conftest import fixture


def test_summary_fields():
    page = fixture("search_page.json")
    auction, fixed, se = page["itemSummaries"]
    row = summary_to_listing(auction)
    assert row["item_id"] == "v1|100000000001|0"
    assert row["is_auction"] == 1 and row["is_fixed_price"] == 0
    assert row["end_time"] == "2026-10-21T18:02:11.000Z"
    assert row["seller_feedback_pct"] == 99.6
    assert row["shipping_cost"] == 6.95          # cheapest option
    assert row["image_count"] == 4
    assert row["category_id"] == "178893"

    f = summary_to_listing(fixed)
    assert f["best_offer_enabled"] == 1 and f["end_time"] is None
    assert f["shipping_cost"] == 0.0

    s = summary_to_listing(se)
    assert s["shipping_cost"] is None and s["shipping_cost_type"] == "CALCULATED"
    snap = summary_to_snapshot(auction)
    assert snap["current_bid"] == 182.5 and snap["bid_count"] == 14


def test_detail_fields():
    d = detail_to_listing(fixture("item_auction.json"))
    assert d["returns_accepted"] == 1 and d["return_period_days"] == 30
    assert d["ship_to_worldwide"] == 0
    assert d["mpn"] == "MRMC3LL/A" and d["brand"] == "Apple"
    aspects = json.loads(d["aspects_json"])
    assert aspects["Model"] == "Apple Watch Series 9"
    assert "var x" not in d["description_text"]
    assert "Battery health 98%" in d["description_text"]

    fp = detail_to_listing(fixture("item_fixed_price.json"))
    assert fp["ship_to_worldwide"] == 1 and fp["return_shipping_payer"] == "SELLER"
    snap = detail_to_snapshot(fixture("item_fixed_price.json"))
    assert snap["est_sold_qty"] == 23 and snap["availability_status"] == "IN_STOCK"
    a = detail_to_snapshot(fixture("item_auction.json"))
    assert a["reserve_price_met"] == 1 and a["unique_bidder_count"] == 6


def test_html_to_text_handles_entities_and_blocks():
    assert html_to_text("<p>A &amp; B</p><p>C</p>") == "A & B\nC"
    assert html_to_text(None) is None
