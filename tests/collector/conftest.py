import json
from pathlib import Path

import pytest

from collector import db
from collector.client import EbayClient
from collector.collector import Collector
from collector.config import Settings
from collector.mock import MockMarket
from collector.timeutil import FakeClock, parse_iso

FIXTURES = Path(__file__).parent / "fixtures"
T0 = parse_iso("2026-10-19T00:00:00Z")


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def clock():
    return FakeClock(T0)


@pytest.fixture
def settings(tmp_path):
    return Settings(client_id="id", client_secret="secret", db_path=str(tmp_path / "test.db"))


@pytest.fixture
def conn(settings):
    c = db.connect(settings.db_path)
    yield c
    c.close()


def build(settings, conn, clock, **market_kwargs):
    market = MockMarket(clock, start=T0, **market_kwargs)
    client = EbayClient(settings, conn, transport=market, clock=clock)
    return market, client, Collector(settings, conn, client, clock)
