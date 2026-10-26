"""eBay REST client: OAuth application token, call budget, retries with backoff."""
from __future__ import annotations

import base64
import logging
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol

from .config import SCOPE_BASE, SCOPE_INSIGHTS, Settings
from .timeutil import Clock, to_iso

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}
BROWSE = "browse"
INSIGHTS = "marketplace_insights"
ANALYTICS = "analytics"


@dataclass
class Response:
    status: int
    headers: dict
    body: Any


class Transport(Protocol):
    def request(self, method: str, url: str, *, params=None, headers=None, data=None,
                timeout: float = 30.0) -> Response: ...


class TransportError(Exception):
    """Network-level failure (connection reset, timeout, DNS)."""


class RequestsTransport:
    def __init__(self):
        import requests
        self._requests = requests
        self.session = requests.Session()

    def request(self, method, url, *, params=None, headers=None, data=None, timeout=30.0):
        try:
            r = self.session.request(method, url, params=params, headers=headers, data=data, timeout=timeout)
        except self._requests.RequestException as exc:
            raise TransportError(str(exc)) from exc
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:2000]}
        return Response(r.status_code, dict(r.headers), body)


class BudgetExceeded(Exception):
    pass


class ApiError(Exception):
    def __init__(self, status: int, body: Any, url: str):
        super().__init__(f"HTTP {status} for {url}: {str(body)[:300]}")
        self.status = status
        self.body = body


class CallBudget:
    """Rolling 24-hour call counter persisted in the api_calls table."""

    def __init__(self, conn, clock: Clock, limits: dict[str, int]):
        self.conn = conn
        self.clock = clock
        self.limits = limits

    def used(self, api: str = BROWSE) -> int:
        since = to_iso(self.clock.now() - timedelta(hours=24))
        row = self.conn.execute("SELECT COUNT(*) AS n FROM api_calls WHERE api = ? AND ts > ?",
                                (api, since)).fetchone()
        return int(row["n"])

    def remaining(self, api: str = BROWSE) -> int:
        return max(0, self.limits.get(api, 0) - self.used(api))

    def record(self, api: str, endpoint: str, status: int | None) -> None:
        self.conn.execute("INSERT INTO api_calls(ts, api, endpoint, status) VALUES (?, ?, ?, ?)",
                          (to_iso(self.clock.now()), api, endpoint, status))
        self.conn.commit()


class EbayClient:
    def __init__(self, settings: Settings, conn, transport: Transport | None = None,
                 clock: Clock | None = None, rng: random.Random | None = None):
        self.s = settings
        self.conn = conn
        self.transport = transport or RequestsTransport()
        self.clock = clock or Clock()
        self.rng = rng or random.Random()
        self.budget = CallBudget(conn, self.clock, {
            BROWSE: settings.usable_daily_calls,
            INSIGHTS: settings.usable_daily_calls,
            ANALYTICS: 1000,
        })
        self._tokens: dict[str, tuple[str, Any]] = {}

    # ---------------------------------------------------------------- auth
    def _token(self, scope: str, force: bool = False) -> str:
        cached = self._tokens.get(scope)
        if cached and not force and cached[1] > self.clock.now():
            return cached[0]
        if not (self.s.client_id and self.s.client_secret):
            raise RuntimeError("EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must be set (or use --mock).")
        basic = base64.b64encode(f"{self.s.client_id}:{self.s.client_secret}".encode()).decode()
        url = f"{self.s.api_root}/identity/v1/oauth2/token"
        resp = self._send("POST", url, api="oauth", headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        }, data={"grant_type": "client_credentials", "scope": scope}, count=False)
        if resp.status != 200:
            raise ApiError(resp.status, resp.body, url)
        token = resp.body["access_token"]
        ttl = int(resp.body.get("expires_in", 7200))
        self._tokens[scope] = (token, self.clock.now() + timedelta(seconds=max(60, ttl - 300)))
        return token

    # ---------------------------------------------------------------- http
    def _send(self, method, url, *, api, params=None, headers=None, data=None, count=True) -> Response:
        attempt = 0
        while True:
            if count and self.budget.remaining(api) <= 0:
                raise BudgetExceeded(f"{api} daily budget exhausted")
            status = None
            try:
                resp = self.transport.request(method, url, params=params, headers=headers, data=data,
                                              timeout=self.s.http_timeout)
                status = resp.status
            except TransportError as exc:
                resp = None
                log.warning("network error on %s: %s", url, exc)
            if count:
                self.budget.record(api, url.split("/v1")[-1][:80], status)
            if resp is not None and resp.status not in RETRY_STATUS:
                return resp
            attempt += 1
            if attempt > self.s.max_retries:
                if resp is None:
                    raise TransportError(f"giving up on {url} after {attempt} attempts")
                return resp
            delay = min(self.s.backoff_cap, self.s.backoff_base ** attempt) * (0.5 + self.rng.random())
            if resp is not None:
                ra = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
                if ra and str(ra).isdigit():
                    delay = max(delay, float(ra))
            log.info("retrying %s in %.1fs (attempt %d, status %s)", url, delay, attempt, status)
            self.clock.sleep(delay)

    def _get(self, path: str, params: dict | None = None, *, api: str = BROWSE,
             scope: str = SCOPE_BASE) -> Response:
        url = f"{self.s.api_root}{path}"
        ctx = f"contextualLocation=country%3D{self.s.buyer_country}%2Czip%3D{self.s.buyer_zip}"
        for refresh in (False, True):
            headers = {
                "Authorization": f"Bearer {self._token(scope, force=refresh)}",
                "X-EBAY-C-MARKETPLACE-ID": self.s.marketplace_id,
                "X-EBAY-C-ENDUSERCTX": ctx,
                "Accept": "application/json",
            }
            resp = self._send("GET", url, api=api, params=params, headers=headers)
            if resp.status != 401:
                return resp
            log.info("token rejected, refreshing")
        return resp

    # ---------------------------------------------------------------- endpoints
    def _aspect_filter(self) -> str:
        return f"categoryId:{self.s.category_id},Brand:{{{self.s.brand}}}"

    def search(self, *, filters: list[str] | None = None, sort: str | None = None,
               offset: int = 0, limit: int | None = None) -> dict:
        params = {
            "category_ids": self.s.category_id,
            "aspect_filter": self._aspect_filter(),
            "limit": str(limit or self.s.page_size),
            "offset": str(offset),
            "fieldgroups": "EXTENDED",
        }
        if filters:
            params["filter"] = ",".join(filters)
        if sort:
            params["sort"] = sort
        resp = self._get("/buy/browse/v1/item_summary/search", params)
        if resp.status != 200:
            raise ApiError(resp.status, resp.body, "item_summary/search")
        return resp.body

    def get_item(self, item_id: str) -> Response:
        """Returns the raw Response so callers can treat 404 (ended / removed) as data."""
        return self._get(f"/buy/browse/v1/item/{item_id}")

    def get_items(self, item_ids: list[str]) -> Response:
        if len(item_ids) > 20:
            raise ValueError("getItems accepts at most 20 item IDs")
        return self._get("/buy/browse/v1/item/", {"item_ids": ",".join(item_ids)})

    def item_sales_search(self, *, offset: int = 0, limit: int = 200, filters=None) -> dict:
        params = {
            "category_ids": self.s.category_id,
            "aspect_filter": self._aspect_filter(),
            "limit": str(limit),
            "offset": str(offset),
        }
        if filters:
            params["filter"] = ",".join(filters)
        resp = self._get("/buy/marketplace_insights/v1_beta/item_sales/search", params,
                         api=INSIGHTS, scope=SCOPE_INSIGHTS)
        if resp.status != 200:
            raise ApiError(resp.status, resp.body, "item_sales/search")
        return resp.body

    def rate_limits(self) -> dict:
        resp = self._get("/developer/analytics/v1_beta/rate_limit/",
                         {"api_context": "buy", "api_name": "browse"}, api=ANALYTICS)
        if resp.status != 200:
            raise ApiError(resp.status, resp.body, "rate_limit")
        return resp.body
