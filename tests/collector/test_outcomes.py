from collector.outcomes import infer_outcome

END = "2026-10-20T12:00:00Z"
AUCTION = {"end_time": END, "is_auction": 1, "best_offer_enabled": 0}
FIXED = {"end_time": None, "is_auction": 0, "best_offer_enabled": 1}


def snap(t, source="search", **kw):
    return {"observed_at": t, "source": source, "http_status": kw.pop("http_status", None), **kw}


def test_auction_post_end_sold():
    s = [snap("2026-10-20T11:00:00Z", bid_count=5, current_bid=100),
         snap("2026-10-20T12:10:00Z", "end_check", http_status=200, bid_count=9, current_bid=140,
              reserve_price_met=1, end_time=END)]
    r = infer_outcome(AUCTION, s)
    assert (r["outcome"], r["final_price"], r["method"], r["confidence"]) == ("sold", 140, "browse_post_end", "high")


def test_auction_reserve_not_met():
    s = [snap("2026-10-20T12:10:00Z", "end_check", http_status=200, bid_count=3, current_bid=80,
              reserve_price_met=0, end_time=END)]
    assert infer_outcome(AUCTION, s)["outcome"] == "reserve_not_met"


def test_auction_404_falls_back_to_last_observed():
    s = [snap("2026-10-20T09:00:00Z", bid_count=2, current_bid=50),
         snap("2026-10-20T11:57:00Z", "final_look", http_status=200, bid_count=7, current_bid=120),
         snap("2026-10-20T12:10:00Z", "end_check", http_status=404)]
    r = infer_outcome(AUCTION, s)
    assert (r["outcome"], r["final_price"], r["method"], r["confidence"]) == ("sold", 120, "last_observed", "medium")


def test_auction_no_bids_early_snapshot_is_low_confidence():
    s = [snap("2026-10-20T06:00:00Z", bid_count=0, current_bid=20),
         snap("2026-10-20T12:10:00Z", "end_check", http_status=404)]
    r = infer_outcome(AUCTION, s)
    assert r["outcome"] == "unsold" and r["confidence"] == "low"


def test_fixed_price_sold_quantity_increase():
    s = [snap("2026-10-19T10:00:00Z", "detail", http_status=200, est_sold_qty=0, price=300),
         snap("2026-10-20T10:00:00Z", "end_check", http_status=200, est_sold_qty=1, price=300,
              availability_status="OUT_OF_STOCK")]
    r = infer_outcome(FIXED, s)
    assert r["outcome"] == "sold" and r["final_price"] == 300 and r["confidence"] == "medium"


def test_fixed_price_still_active_returns_none():
    s = [snap("2026-10-20T10:00:00Z", "end_check", http_status=200, est_sold_qty=0, price=300,
              availability_status="IN_STOCK")]
    assert infer_outcome(FIXED, s) is None


def test_fixed_price_disappeared_is_unknown():
    s = [snap("2026-10-19T10:00:00Z", price=300), snap("2026-10-20T10:00:00Z", "end_check", http_status=404)]
    r = infer_outcome(FIXED, s)
    assert r["outcome"] == "ended_unknown" and r["final_price"] is None


def test_insight_overrides():
    r = infer_outcome(FIXED, [], {"last_sold_price": 275.0, "total_sold_qty": 1, "last_sold_date": END})
    assert r["method"] == "marketplace_insights" and r["final_price"] == 275.0
