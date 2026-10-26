from datetime import timedelta

from collector import db
from collector.client import EbayClient
from collector.collector import Collector
from collector.export import export_all, PLATED_COLS
from tests.collector.conftest import T0, build


def _truth(market, item_id):
    it = market.items[item_id]
    if it.end:
        if it.final_bids and it.reserve_met:
            return "sold"
        return "reserve_not_met" if it.final_bids else "unsold"
    return "sold" if it.sold_at else "withdrawn"


def test_end_to_end_mock_week(settings, conn, clock):
    market, client, col = build(settings, conn, clock, n_items=250, error_rate=0.01)
    col.run(until=T0 + timedelta(days=3), tick_seconds=60)
    col.close_out()
    rows = conn.execute("SELECT o.*, l.is_auction FROM outcomes o JOIN listings l USING(item_id)").fetchall()
    assert len(rows) > 30
    for r in rows:
        truth = _truth(market, r["item_id"])
        if r["is_auction"]:
            assert r["outcome"] == truth
            if truth == "sold":
                assert 0.9 * market.items[r["item_id"]].final_price <= r["final_price"] <= market.items[r["item_id"]].final_price + 0.01
        elif r["outcome"] == "sold":
            assert truth == "sold"
    # every listing that ended during the window and was ever observed has an outcome
    now = clock.now()
    seen = {r[0] for r in conn.execute("SELECT item_id FROM listings")}
    decided = {r["item_id"] for r in rows}
    ended = [i for i in market.items.values()
             if i.item_id in seen and market._ended(i, now) and (i.end or i.sold_at or i.removed_at) > T0]
    assert all(i.item_id in decided for i in ended)
    # budget respected
    assert client.budget.used() <= settings.usable_daily_calls


def test_restart_is_idempotent(settings, conn, clock):
    market, client, col = build(settings, conn, clock, n_items=120)
    col.run(until=T0 + timedelta(hours=12), tick_seconds=60)
    n_list = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    n_out = conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    # New process on the same database
    conn2 = db.connect(settings.db_path)
    col2 = Collector(settings, conn2, EbayClient(settings, conn2, transport=market, clock=clock), clock)
    col2.tick()
    assert conn2.execute("SELECT COUNT(*) FROM listings").fetchone()[0] >= n_list
    assert conn2.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] >= n_out
    assert conn2.execute("SELECT COUNT(*) FROM listings GROUP BY item_id HAVING COUNT(*) > 1").fetchone() is None


def test_sweep_splits_bands_past_result_window(settings, conn, clock):
    settings.page_size, settings.result_window = 20, 60
    settings.price_bands = ((0, 100000),)
    market, client, col = build(settings, conn, clock, n_items=300)
    active = sum(market._active(i, clock.now()) for i in market.items.values())
    assert active > settings.result_window
    while True:
        r = col.full_sweep(max_pages_per_tick=5)       # resumes across calls
        if r.get("finished"):
            break
    assert r["items_seen"] == active


def test_sweep_survives_budget_exhaustion(settings, conn, clock):
    settings.page_size = 20
    settings.daily_call_limit, settings.safety_margin = 8, 0.0
    market, client, col = build(settings, conn, clock, n_items=300)
    assert col.tick()["full_sweep"] == "budget"
    settings.daily_call_limit = 10_000
    client.budget.limits["browse"] = 10_000
    while not col.full_sweep().get("finished"):
        pass
    active = sum(market._active(i, clock.now()) for i in market.items.values())
    assert conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0] >= active


def test_insights_denied_then_skipped(settings, conn, clock):
    settings.use_marketplace_insights = True
    market, client, col = build(settings, conn, clock, n_items=50)
    assert col.insights() == {"access": "denied"}
    assert db.get_meta(conn, "insights_access") == "denied"
    assert "insights" not in col.tick()


def test_insights_granted_confirms_sales(settings, conn, clock):
    settings.use_marketplace_insights = True
    market, client, col = build(settings, conn, clock, n_items=120, insights_access=True)
    col.run(until=T0 + timedelta(hours=36), tick_seconds=120)
    clock.advance(minutes=5)
    col.insights()
    n = conn.execute("SELECT COUNT(*) FROM outcomes WHERE method = 'marketplace_insights'").fetchone()[0]
    assert n > 0


def test_export(settings, conn, clock, tmp_path):
    market, client, col = build(settings, conn, clock, n_items=120)
    col.run(until=T0 + timedelta(hours=30), tick_seconds=120)
    paths = export_all(conn, tmp_path)
    import pandas as pd
    plated = pd.read_csv(paths["plated_compatible"])
    assert set(PLATED_COLS) <= set(plated.columns)
    assert plated["model"].notna().all()
    listings = pd.read_csv(paths["listings"])
    assert {"description_text", "outcome", "final_price", "material", "connectivity"} <= set(listings.columns)
