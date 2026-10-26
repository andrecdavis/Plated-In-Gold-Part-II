import pytest

from collector.client import BROWSE, BudgetExceeded, EbayClient, Response
from tests.collector.conftest import fixture


class ScriptedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        if url.endswith("/oauth2/token"):
            return Response(200, {}, fixture("token.json"))
        return self.responses.pop(0)


def test_retries_with_backoff_and_retry_after(settings, conn, clock):
    t = ScriptedTransport([Response(429, {"Retry-After": "30"}, {}), Response(503, {}, {}),
                           Response(200, {}, fixture("search_page.json"))])
    c = EbayClient(settings, conn, transport=t, clock=clock)
    start = clock.now()
    body = c.search()
    assert body["total"] == 3
    assert (clock.now() - start).total_seconds() >= 30
    assert c.budget.used(BROWSE) == 3


def test_headers_and_params(settings, conn, clock):
    t = ScriptedTransport([Response(200, {}, fixture("search_page.json"))])
    EbayClient(settings, conn, transport=t, clock=clock).search(filters=["price:[0..50]", "priceCurrency:USD"])
    _, url, kw = t.calls[-1]
    assert url.endswith("/buy/browse/v1/item_summary/search")
    assert kw["headers"]["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
    assert kw["params"]["aspect_filter"] == "categoryId:178893,Brand:{Apple}"
    assert kw["params"]["filter"] == "price:[0..50],priceCurrency:USD"


def test_token_refresh_on_401(settings, conn, clock):
    t = ScriptedTransport([Response(401, {}, {}), Response(200, {}, fixture("item_auction.json"))])
    c = EbayClient(settings, conn, transport=t, clock=clock)
    assert c.get_item("v1|100000000001|0").status == 200
    assert sum(1 for m, u, _ in t.calls if u.endswith("/oauth2/token")) == 2


def test_token_cached(settings, conn, clock):
    t = ScriptedTransport([Response(200, {}, {})] * 3)
    c = EbayClient(settings, conn, transport=t, clock=clock)
    for _ in range(3):
        c.get_item("x")
    assert sum(1 for m, u, _ in t.calls if u.endswith("/oauth2/token")) == 1


def test_budget_exhausted(settings, conn, clock):
    settings.daily_call_limit, settings.safety_margin = 2, 0.0
    t = ScriptedTransport([Response(200, {}, {})] * 5)
    c = EbayClient(settings, conn, transport=t, clock=clock)
    c.get_item("a"); c.get_item("b")
    with pytest.raises(BudgetExceeded):
        c.get_item("c")
    clock.advance(hours=25)
    c.get_item("d")


def test_missing_credentials(settings, conn, clock):
    settings.client_id = ""
    with pytest.raises(RuntimeError):
        EbayClient(settings, conn, transport=ScriptedTransport([]), clock=clock).get_item("x")


def test_get_items_limit(settings, conn, clock):
    with pytest.raises(ValueError):
        EbayClient(settings, conn, transport=ScriptedTransport([]), clock=clock).get_items([str(i) for i in range(21)])
