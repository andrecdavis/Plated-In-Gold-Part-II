"""Decide whether an ended listing sold, and at what price, from the evidence collected.

Outcome labels
  sold             the listing ended with a sale
  unsold           the listing ended without a sale
  reserve_not_met  auction ended with bids below the reserve
  ended_unknown    the listing is no longer available, but the API does not say why
                   (sold, ended early by the seller, or removed)

Methods, from strongest to weakest
  marketplace_insights   sale record from the Marketplace Insights API
  browse_post_end        listing re-read after its end time
  last_observed          last snapshot taken before the end time
  disappeared            listing no longer returned by the API
"""
from __future__ import annotations

import json
from datetime import timedelta

from .timeutil import parse_iso

LATE_SNAPSHOT_MINUTES = 15


def _last(snaps, pred):
    for s in reversed(snaps):
        if pred(s):
            return s
    return None


def infer_outcome(listing: dict, snapshots: list[dict], insight: dict | None = None) -> dict | None:
    """Return an outcome dict, or None when the listing still appears to be active.

    `snapshots` must be ordered by observed_at and may include end-check rows
    (source == 'end_check') carrying the HTTP status of the post-end request.
    """
    end = parse_iso(listing.get("end_time"))
    is_auction = bool(listing.get("is_auction"))
    best_offer = bool(listing.get("best_offer_enabled"))

    if insight:
        return _result("sold", insight.get("last_sold_price"), insight.get("total_sold_qty") or 1, None,
                       "marketplace_insights", "high", end or parse_iso(insight.get("last_sold_date")),
                       {"source": "item_sales"})

    post = _last(snapshots, lambda s: s.get("source") == "end_check")
    pre = _last(snapshots, lambda s: s.get("source") != "end_check" and s.get("http_status") in (None, 200)
                and (end is None or parse_iso(s["observed_at"]) <= end))
    first = next((s for s in snapshots if s.get("est_sold_qty") is not None), None)

    if post and post.get("http_status") == 200:
        status = post.get("availability_status")
        post_end = parse_iso(post.get("end_time")) or end
        observed = parse_iso(post["observed_at"])
        if is_auction:
            if post_end and observed and observed < post_end:
                return None
            bids = post.get("bid_count") or 0
            if bids and post.get("reserve_price_met") == 0:
                return _result("reserve_not_met", None, 0, bids, "browse_post_end", "high", post_end,
                               {"high_bid": post.get("current_bid")})
            if bids:
                return _result("sold", post.get("current_bid") or post.get("price"), 1, bids,
                               "browse_post_end", "high", post_end, {})
            return _result("unsold", None, 0, 0, "browse_post_end", "high", post_end, {})

        # Fixed price
        if status in ("IN_STOCK", "LIMITED_STOCK") and (post_end is None or observed < post_end):
            return None
        sold_now = post.get("est_sold_qty")
        sold_before = first.get("est_sold_qty") if first and first is not post else 0
        if sold_now is not None and sold_now > (sold_before or 0):
            units = sold_now - (sold_before or 0)
            return _result("sold", post.get("price"), units, None, "browse_post_end",
                           "medium" if best_offer else "high", post_end or observed,
                           {"best_offer_enabled": best_offer, "est_sold_qty": sold_now})
        return _result("ended_unknown", None, None, None, "browse_post_end", "low", post_end or observed,
                       {"availability_status": status, "last_price": post.get("price")})

    # No readable post-end record (typically HTTP 404 once the listing has ended).
    if pre is None:
        return _result("ended_unknown", None, None, None, "disappeared", "low", end, {})
    lead_min = None
    if end is not None:
        lead_min = (end - parse_iso(pre["observed_at"])) / timedelta(minutes=1)
    late = lead_min is not None and lead_min <= LATE_SNAPSHOT_MINUTES
    evidence = {"minutes_before_end": round(lead_min, 1) if lead_min is not None else None,
                "post_end_http_status": post.get("http_status") if post else None}
    if is_auction:
        bids = pre.get("bid_count") or 0
        if bids and pre.get("reserve_price_met") == 0:
            return _result("reserve_not_met", None, 0, bids, "last_observed", "medium" if late else "low",
                           end, evidence)
        if bids:
            # Bids placed after the last snapshot can raise the final price.
            return _result("sold", pre.get("current_bid") or pre.get("price"), 1, bids, "last_observed",
                           "medium" if late else "low", end, evidence)
        return _result("unsold", None, 0, 0, "last_observed", "medium" if late else "low", end, evidence)
    evidence["last_price"] = pre.get("price")
    return _result("ended_unknown", None, None, None, "disappeared", "low", end, evidence)


def _result(outcome, price, units, bids, method, confidence, ended_at, evidence):
    from .timeutil import to_iso
    return {
        "outcome": outcome,
        "final_price": price,
        "units_sold": units,
        "bid_count": bids,
        "method": method,
        "confidence": confidence,
        "ended_at": to_iso(ended_at) if ended_at else None,
        "evidence": json.dumps(evidence),
    }
