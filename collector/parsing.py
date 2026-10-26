"""Map Browse API JSON to listing rows and price snapshots."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser

COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia",
    "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain", "JP": "Japan",
    "KR": "South Korea", "CN": "China", "HK": "Hong Kong", "TW": "Taiwan", "IL": "Israel",
    "NL": "Netherlands", "IE": "Ireland", "MX": "Mexico", "SG": "Singapore", "AE": "United Arab Emirates",
}


def _money(obj) -> float | None:
    if not obj or obj.get("value") in (None, ""):
        return None
    try:
        return float(obj["value"])
    except (TypeError, ValueError):
        return None


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    p = _TextExtractor()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _shipping(options: list | None) -> tuple[float | None, str | None]:
    if not options:
        return None, None
    costs = [(o, _money(o.get("shippingCost"))) for o in options]
    priced = [c for c in costs if c[1] is not None]
    if not priced:
        return None, options[0].get("shippingCostType")
    o, cost = min(priced, key=lambda c: c[1])
    return cost, o.get("shippingCostType")


def _availability(item: dict) -> dict:
    av = (item.get("estimatedAvailabilities") or [{}])[0]
    return {
        "availability_status": av.get("estimatedAvailabilityStatus"),
        "est_available_qty": _int(av.get("estimatedAvailableQuantity")),
        "est_sold_qty": _int(av.get("estimatedSoldQuantity")),
    }


def aspects_dict(item: dict) -> dict:
    out: dict[str, str] = {}
    for a in item.get("localizedAspects") or []:
        name, value = a.get("name"), a.get("value")
        if name and value is not None:
            out[name] = value
    return out


def summary_to_listing(s: dict) -> dict:
    opts = s.get("buyingOptions") or []
    loc = s.get("itemLocation") or {}
    seller = s.get("seller") or {}
    ship_cost, ship_type = _shipping(s.get("shippingOptions"))
    images = (1 if s.get("image") else 0) + len(s.get("additionalImages") or [])
    cats = s.get("categories") or []
    return {
        "item_id": s["itemId"],
        "legacy_item_id": s.get("legacyItemId"),
        "title": s.get("title"),
        "item_web_url": s.get("itemWebUrl"),
        "category_id": (s.get("leafCategoryIds") or [None])[0] or (cats[0].get("categoryId") if cats else None),
        "buying_options": json.dumps(opts),
        "is_auction": int("AUCTION" in opts),
        "is_fixed_price": int("FIXED_PRICE" in opts),
        "best_offer_enabled": int("BEST_OFFER" in opts),
        "start_time": s.get("itemCreationDate") or s.get("itemOriginDate"),
        "end_time": s.get("itemEndDate"),
        "currency": (s.get("price") or s.get("currentBidPrice") or {}).get("currency"),
        "condition": s.get("condition"),
        "condition_id": s.get("conditionId"),
        "seller_username": seller.get("username"),
        "seller_feedback_score": _int(seller.get("feedbackScore")),
        "seller_feedback_pct": _float(seller.get("feedbackPercentage")),
        "top_rated_buying": int(bool(s.get("topRatedBuyingExperience"))),
        "shipping_cost": ship_cost,
        "shipping_cost_type": ship_type,
        "location_country": loc.get("country"),
        "location_state": loc.get("stateOrProvince"),
        "location_city": loc.get("city"),
        "location_postal": loc.get("postalCode"),
        "image_count": images or None,
        "epid": s.get("epid"),
        "original_price": _money((s.get("marketingPrice") or {}).get("originalPrice")),
        "short_description": s.get("shortDescription"),
        "raw_summary_json": json.dumps(s, ensure_ascii=False),
    }


def summary_to_snapshot(s: dict) -> dict:
    ship_cost, _ = _shipping(s.get("shippingOptions"))
    return {
        "item_id": s["itemId"],
        "price": _money(s.get("price")),
        "current_bid": _money(s.get("currentBidPrice")),
        "bid_count": _int(s.get("bidCount")),
        "shipping_cost": ship_cost,
        "end_time": s.get("itemEndDate"),
    }


def detail_to_listing(d: dict) -> dict:
    row = summary_to_listing(d)
    row.pop("raw_summary_json")
    aspects = aspects_dict(d)
    seller = d.get("seller") or {}
    ret = d.get("returnTerms") or {}
    period = ret.get("returnPeriod") or {}
    regions = [r.get("regionName", "") for r in (d.get("shipToLocations") or {}).get("regionIncluded") or []]
    row.update({
        "category_id": d.get("categoryId") or row["category_id"],
        "category_path": d.get("categoryPath"),
        "condition_description": d.get("conditionDescription"),
        "seller_account_type": seller.get("sellerAccountType"),
        "shipping_options_json": json.dumps(d.get("shippingOptions") or []),
        "ship_to_worldwide": int(any(r.lower() == "worldwide" for r in regions)) if regions else None,
        "returns_accepted": int(bool(ret.get("returnsAccepted"))) if ret else None,
        "return_period_days": _int(period.get("value")) if "DAY" in (period.get("unit") or "DAY").upper() else None,
        "return_shipping_payer": ret.get("returnShippingCostPayer"),
        "gtin": d.get("gtin"),
        "mpn": d.get("mpn") or aspects.get("MPN"),
        "brand": d.get("brand") or aspects.get("Brand"),
        "color": d.get("color") or aspects.get("Color"),
        "lot_size": _int(d.get("lotSize")),
        "quantity_limit": _int(d.get("quantityLimitPerBuyer")),
        "description_html": d.get("description"),
        "description_text": html_to_text(d.get("description")),
        "aspects_json": json.dumps(aspects, ensure_ascii=False),
        "raw_detail_json": json.dumps(d, ensure_ascii=False),
    })
    return row


def detail_to_snapshot(d: dict) -> dict:
    snap = summary_to_snapshot(d)
    snap.update(_availability(d))
    snap["unique_bidder_count"] = _int(d.get("uniqueBidderCount"))
    rpm = d.get("reservePriceMet")
    snap["reserve_price_met"] = None if rpm is None else int(bool(rpm))
    return snap
