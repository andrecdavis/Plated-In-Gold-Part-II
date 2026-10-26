"""Offline stand-in for the eBay APIs, used by the test suite and `--mock` runs.

`MockMarket` generates a deterministic synthetic Apple Watch market from the JSON
fixtures in tests/collector/fixtures and answers the same endpoints the collector calls,
including the 10,000-result search window, ended listings, and transient errors.
"""
from __future__ import annotations

import copy
import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse

from . import ROOT
from .client import Response
from .timeutil import Clock, ebay_iso, parse_iso

FIXTURES = ROOT / "tests" / "collector" / "fixtures"

MODELS = [
    ("Series 9", "Apple Watch Series 9", [41, 45], "Aluminum", 120, 260),
    ("Series 8", "Apple Watch Series 8", [41, 45], "Aluminum", 100, 220),
    ("Series 7", "Apple Watch Series 7", [41, 45], "Stainless Steel", 90, 250),
    ("Series 6", "Apple Watch Series 6", [40, 44], "Aluminum", 70, 160),
    ("Series 10", "Apple Watch Series 10", [42, 46], "Titanium", 250, 520),
    ("SE 2", "Apple Watch SE (2nd Generation)", [40, 44], "Aluminum", 70, 170),
    ("Ultra 2", "Apple Watch Ultra 2", [49], "Titanium", 420, 700),
    ("Ultra 1", "Apple Watch Ultra", [49], "Titanium", 300, 520),
    ("Series 3", "Apple Watch Series 3", [38, 42], "Aluminum", 25, 70),
]
CONDITIONS = [("New", "1000"), ("Open box", "1500"), ("Used", "3000"), ("Pre-owned", "3000"),
              ("Excellent - Refurbished", "2010"), ("For parts or not working", "7000")]


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


@dataclass
class MockItem:
    data: dict
    start: datetime
    end: datetime | None          # auctions and fixed-length listings
    start_price: float
    final_price: float
    final_bids: int
    reserve_met: bool
    sold_at: datetime | None      # fixed price sale time
    removed_at: datetime | None   # ended early / withdrawn
    ended_returns_200: bool       # whether getItem still answers after the end
    extra: dict = field(default_factory=dict)

    @property
    def item_id(self) -> str:
        return self.data["itemId"]


class MockMarket:
    def __init__(self, clock: Clock, n_items: int = 300, seed: int = 7, start: datetime | None = None,
                 error_rate: float = 0.0, insights_access: bool = False):
        self.clock = clock
        self.rng = random.Random(seed)
        self.error_rate = error_rate
        self.insights_access = insights_access
        self.calls: list[tuple[str, dict]] = []
        t0 = start or clock.now()
        auction_t = load_fixture("item_auction.json")
        fixed_t = load_fixture("item_fixed_price.json")
        self.items: dict[str, MockItem] = {}
        for i in range(n_items):
            short, model_name, sizes, material, lo, hi = self.rng.choice(MODELS)
            size = self.rng.choice(sizes)
            cond, cond_id = self.rng.choice(CONDITIONS)
            auction = self.rng.random() < 0.4
            base = copy.deepcopy(auction_t if auction else fixed_t)
            legacy = str(300000000000 + i)
            iid = f"v1|{legacy}|0"
            cell = self.rng.random() < 0.35
            title = f"Apple Watch {short} {size}mm {'GPS + Cellular' if cell else 'GPS'} {material} Case"
            if self.rng.random() < 0.05:
                title += " 24K Gold Plated"
            value = round(self.rng.uniform(lo, hi), 2)
            start_dt = t0 - timedelta(hours=self.rng.uniform(0, 240)) if self.rng.random() < 0.7 \
                else t0 + timedelta(hours=self.rng.uniform(0, 96))
            base.update(itemId=iid, legacyItemId=legacy, title=title, condition=cond, conditionId=cond_id,
                        itemWebUrl=f"https://www.ebay.com/itm/{legacy}", itemCreationDate=ebay_iso(start_dt))
            base["seller"] = {"username": f"seller_{self.rng.randint(1, n_items // 3)}",
                              "feedbackPercentage": f"{self.rng.uniform(95, 100):.1f}",
                              "feedbackScore": self.rng.randint(0, 20000)}
            base["localizedAspects"] = [
                {"type": "STRING", "name": "Brand", "value": "Apple"},
                {"type": "STRING", "name": "Model", "value": model_name},
                {"type": "STRING", "name": "Case Size", "value": f"{size} mm"},
                {"type": "STRING", "name": "Case Material", "value": material},
                {"type": "STRING", "name": "Connectivity", "value": "GPS + Cellular" if cell else "GPS"},
            ]
            end = sold_at = removed_at = None
            if auction:
                end = start_dt + timedelta(days=self.rng.choice([1, 3, 5, 7, 10]))
                start_price = round(value * self.rng.uniform(0.1, 0.8), 2)
                bids = 0 if self.rng.random() < 0.25 else self.rng.randint(1, 30)
                final = value if bids else start_price
                reserve_met = self.rng.random() > 0.08
                base["itemEndDate"] = ebay_iso(end)
            else:
                start_price = final = value
                bids, reserve_met = 0, True
                base.pop("itemEndDate", None)
                base.pop("currentBidPrice", None)
                base.pop("bidCount", None)
                r = self.rng.random()
                when = max(start_dt, t0) + timedelta(hours=self.rng.uniform(1, 160))
                if r < 0.25:
                    sold_at = when
                elif r < 0.32:
                    removed_at = when
            self.items[iid] = MockItem(base, start_dt, end, start_price, final, bids, reserve_met,
                                       sold_at, removed_at, ended_returns_200=(i % 2 == 1))

    # ------------------------------------------------------------ state at a time
    def _active(self, it: MockItem, now: datetime) -> bool:
        if now < it.start:
            return False
        if it.end and now >= it.end:
            return False
        if it.sold_at and now >= it.sold_at:
            return False
        if it.removed_at and now >= it.removed_at:
            return False
        return True

    def _ended(self, it: MockItem, now: datetime) -> bool:
        return now >= it.start and not self._active(it, now)

    def _view(self, it: MockItem, now: datetime) -> dict:
        d = copy.deepcopy(it.data)
        if it.end:
            span = (it.end - it.start).total_seconds()
            frac = min(1.0, max(0.0, (now - it.start).total_seconds() / span))
            # The last few percent of the final price arrives in end-of-auction bidding.
            bid_frac = 1.0 if now >= it.end else 0.95 * frac ** 3
            bids = int(round(it.final_bids * min(1.0, frac ** 2))) if now < it.end else it.final_bids
            price = it.start_price + (it.final_price - it.start_price) * bid_frac if bids else it.start_price
            d["currentBidPrice"] = {"value": f"{price:.2f}", "currency": "USD"}
            d["price"] = dict(d["currentBidPrice"])
            d["bidCount"] = bids
            d["reservePriceMet"] = it.reserve_met
            avail = "OUT_OF_STOCK" if now >= it.end else "IN_STOCK"
            sold_qty = 1 if (now >= it.end and it.final_bids and it.reserve_met) else 0
        else:
            d["price"] = {"value": f"{it.final_price:.2f}", "currency": "USD"}
            sold = bool(it.sold_at and now >= it.sold_at)
            avail = "OUT_OF_STOCK" if self._ended(it, now) else "IN_STOCK"
            sold_qty = 1 if sold else 0
        d["estimatedAvailabilities"] = [{"estimatedAvailabilityStatus": avail,
                                         "estimatedAvailableQuantity": 0 if avail == "OUT_OF_STOCK" else 1,
                                         "estimatedSoldQuantity": sold_qty}]
        return d

    def _summary(self, d: dict) -> dict:
        keep = ["itemId", "legacyItemId", "title", "price", "currentBidPrice", "bidCount", "buyingOptions",
                "condition", "conditionId", "seller", "itemLocation", "shippingOptions", "image",
                "additionalImages", "itemCreationDate", "itemEndDate", "itemWebUrl", "shortDescription",
                "topRatedBuyingExperience"]
        s = {k: d[k] for k in keep if k in d}
        s["leafCategoryIds"] = ["178893"]
        return s

    def _readable(self, it: MockItem, now: datetime) -> bool:
        if now < it.start:
            return False
        return self._active(it, now) or it.ended_returns_200

    # ------------------------------------------------------------ transport
    def request(self, method, url, *, params=None, headers=None, data=None, timeout=30.0):
        path = urlparse(url).path
        params = params or {}
        self.calls.append((path, dict(params)))
        now = self.clock.now()
        if path.endswith("/oauth2/token"):
            return Response(200, {}, load_fixture("token.json"))
        if self.error_rate and self.rng.random() < self.error_rate:
            return Response(self.rng.choice([429, 500, 503]), {"Retry-After": "1"}, {"errors": []})
        if path.endswith("/item_summary/search"):
            return self._search(params, now)
        if path.endswith("/item/") and "item_ids" in params:
            ids = params["item_ids"].split(",")
            found = [self._view(self.items[i], now) for i in ids
                     if i in self.items and self._readable(self.items[i], now)]
            if not found:
                return Response(404, {}, load_fixture("item_not_found.json"))
            return Response(200, {}, {"items": found})
        m = re.search(r"/item/([^/]+)$", path)
        if m:
            it = self.items.get(m.group(1))
            if it is None or not self._readable(it, now):
                return Response(404, {}, load_fixture("item_not_found.json"))
            return Response(200, {}, self._view(it, now))
        if path.endswith("/item_sales/search"):
            if not self.insights_access:
                return Response(403, {}, load_fixture("insights_forbidden.json"))
            sales = []
            for it in self.items.values():
                when = it.end if it.end else it.sold_at
                if when and now >= when and (it.end is None or (it.final_bids and it.reserve_met)):
                    sales.append({"itemId": it.item_id, "title": it.data["title"],
                                  "lastSoldPrice": {"value": f"{it.final_price:.2f}", "currency": "USD"},
                                  "lastSoldDate": ebay_iso(when), "totalSoldQuantity": 1,
                                  "condition": it.data["condition"]})
            off, lim = int(params.get("offset", 0)), int(params.get("limit", 200))
            return Response(200, {}, {"total": len(sales), "itemSales": sales[off:off + lim]})
        if path.endswith("/rate_limit/"):
            return Response(200, {}, {"rateLimits": [{"apiContext": "buy", "apiName": "browse", "resources": [
                {"name": "buy.browse", "rates": [{"limit": 5000, "remaining": 4900, "reset": ebay_iso(now),
                                                  "timeWindow": 86400}]}]}]})
        return Response(404, {}, {"errors": [{"message": "unknown path " + path}]})

    def _search(self, params, now):
        flt = params.get("filter", "")
        items = [it for it in self.items.values() if self._active(it, now)]
        m = re.search(r"price:\[([\d.]*)\.\.([\d.]*)\]", flt)
        views = [self._view(it, now) for it in items]
        if m:
            lo = float(m.group(1) or 0)
            hi = float(m.group(2) or 1e12)
            views = [v for v in views if lo <= float(v["price"]["value"]) <= hi]
        if "buyingOptions:{AUCTION}" in flt:
            views = [v for v in views if "AUCTION" in v["buyingOptions"]]
        m = re.search(r"itemEndDate:\[([^\]]*?)\.\.([^\]]*?)\]", flt)
        if m:
            a, b = parse_iso(m.group(1)), parse_iso(m.group(2))
            views = [v for v in views if v.get("itemEndDate") and a <= parse_iso(v["itemEndDate"]) <= b]
        sort = params.get("sort")
        if sort == "newlyListed":
            views.sort(key=lambda v: v["itemCreationDate"], reverse=True)
        elif sort == "endingSoonest":
            views.sort(key=lambda v: v.get("itemEndDate") or "9999")
        else:
            views.sort(key=lambda v: v["itemId"])
        off, lim = int(params.get("offset", 0)), int(params.get("limit", 50))
        if off + lim > 10000:
            return Response(400, {}, {"errors": [{"errorId": 12023, "message": "offset+limit exceeds 10000"}]})
        page = views[off:off + lim]
        return Response(200, {}, {"total": len(views), "offset": off, "limit": lim,
                                  "itemSummaries": [self._summary(v) for v in page]})
