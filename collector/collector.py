"""Scheduled collection tasks.

Each call to `Collector.tick()` runs whichever tasks are due, highest priority first:

  final_look    re-read auctions a few minutes before they end (getItems, 20 per call)
  end_checks    re-read listings after their end time, or after they drop out of search
  ending_soon   search auctions ending within the next window
  new_listings  search newest listings
  full_sweep    page through the whole category in price bands (resumable)
  details       full item record (description, item specifics, returns, availability)
  insights      Marketplace Insights sales (only when the application has access)

All state lives in SQLite, so the process can be stopped and restarted at any time.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from . import db
from .client import ApiError, BudgetExceeded, EbayClient, TransportError, BROWSE
from .config import Settings
from .outcomes import infer_outcome
from .parsing import detail_to_listing, detail_to_snapshot, summary_to_listing, summary_to_snapshot
from .timeutil import Clock, ebay_iso, parse_iso, to_iso

log = logging.getLogger(__name__)

FINAL_LOOK_MINUTES = 4


class Collector:
    def __init__(self, settings: Settings, conn, client: EbayClient, clock: Clock | None = None):
        self.s = settings
        self.conn = conn
        self.client = client
        self.clock = clock or client.clock
        self._batch_ok = settings.use_get_items_batch

    # ------------------------------------------------------------ scheduling
    def _due(self, task: str, minutes: float) -> bool:
        row = self.conn.execute("SELECT last_run_at FROM task_runs WHERE task = ?", (task,)).fetchone()
        if not row or not row["last_run_at"]:
            return True
        return self.clock.now() - parse_iso(row["last_run_at"]) >= timedelta(minutes=minutes)

    def _mark(self, task: str, status: str = "ok") -> None:
        self.conn.execute(
            "INSERT INTO task_runs(task, last_run_at, last_status) VALUES (?, ?, ?) "
            "ON CONFLICT(task) DO UPDATE SET last_run_at = excluded.last_run_at, last_status = excluded.last_status",
            (task, to_iso(self.clock.now()), status))
        self.conn.commit()

    def tick(self) -> dict:
        ran = {}
        plan = [
            ("final_look", 1, self.final_look),
            ("end_checks", self.s.end_check_minutes, self.end_checks),
            ("ending_soon", self.s.ending_soon_minutes, self.ending_soon),
            ("new_listings", self.s.new_listings_minutes, self.new_listings),
            ("full_sweep", 0 if self._sweep_open() else self.s.full_sweep_minutes, self.full_sweep),
            ("details", self.s.detail_minutes, self.details),
        ]
        if self.s.use_marketplace_insights and db.get_meta(self.conn, "insights_access") != "denied":
            plan.append(("insights", self.s.insights_minutes, self.insights))
        for name, minutes, fn in plan:
            if not self._due(name, minutes):
                continue
            try:
                ran[name] = fn()
                self._mark(name)
            except BudgetExceeded as exc:
                log.warning("%s stopped: %s", name, exc)
                self._mark(name, "budget")
                ran[name] = "budget"
            except (ApiError, TransportError) as exc:
                log.error("%s failed: %s", name, exc)
                self._mark(name, "error")
                ran[name] = "error"
        db.set_meta(self.conn, "heartbeat", to_iso(self.clock.now()))
        self.conn.commit()
        return ran

    def run(self, until=None, tick_seconds: int = 60, stop_flag=None) -> None:
        while True:
            if stop_flag is not None and stop_flag():
                break
            if until is not None and self.clock.now() >= until:
                break
            ran = self.tick()
            if any(k != "final_look" or v != {"items": 0} for k, v in ran.items()):
                log.info("tick %s | calls used (24h): %d", ran, self.client.budget.used(BROWSE))
            self.clock.sleep(tick_seconds)

    def close_out(self) -> dict:
        """Final pass at the end of a collection window: complete a full sweep so that
        listings which ended since the last sweep are queued, then run every due end check."""
        self.conn.execute("UPDATE sweeps SET finished_at = started_at WHERE finished_at IS NULL")
        res = {"sweep": None, "end_checks": []}
        while True:
            r = self.full_sweep(max_pages_per_tick=10_000)
            if r.get("finished"):
                res["sweep"] = r
                break
        self.conn.execute("UPDATE end_queue SET next_due_at = ? WHERE finalized = 0 AND next_due_at > ? "
                          "AND item_id IN (SELECT item_id FROM listings WHERE end_time IS NULL OR end_time <= ?)",
                          (to_iso(self.clock.now()),) * 3)
        while True:
            r = self.end_checks()
            res["end_checks"].append(r)
            if not r.get("checked"):
                break
        return res

    # ------------------------------------------------------------ recording
    def _record_summary(self, s: dict, source: str, sweep_id: int | None = None) -> bool:
        """Store one search result. Returns True if the listing was new."""
        now = to_iso(self.clock.now())
        known = self.conn.execute("SELECT 1 FROM listings WHERE item_id = ?", (s["itemId"],)).fetchone()
        row = summary_to_listing(s)
        row.update(first_seen_at=now, last_seen_at=now, status="active", missing_sweeps=0,
                   first_price=(row_price(s)))
        if sweep_id is not None:
            row["last_seen_sweep"] = sweep_id
        db.upsert(self.conn, "listings", row, keep_existing=("first_seen_at", "first_price", "raw_summary_json"))
        snap = summary_to_snapshot(s)
        snap.update(observed_at=now, source=source)
        db.insert_snapshot(self.conn, snap)
        if row.get("end_time"):
            self._schedule_end_check(s["itemId"], row["end_time"], "ended")
        return not known

    def _schedule_end_check(self, item_id: str, end_time: str, reason: str) -> None:
        due = parse_iso(end_time) + timedelta(minutes=self.s.post_end_delays[0])
        self.conn.execute(
            "INSERT INTO end_queue(item_id, reason, next_due_at) VALUES (?, ?, ?) "
            "ON CONFLICT(item_id) DO UPDATE SET next_due_at = excluded.next_due_at "
            "WHERE end_queue.finalized = 0 AND end_queue.reason = excluded.reason",
            (item_id, reason, to_iso(due)))

    def _search_pages(self, filters, sort, source, max_pages=None, sweep_id=None, start_offset=0,
                      stop_when_known=False):
        offset, pages, new, seen, total = start_offset, 0, 0, 0, None
        while True:
            if offset + self.s.page_size > self.s.result_window:
                break
            body = self.client.search(filters=filters, sort=sort, offset=offset)
            total = body.get("total", 0)
            items = body.get("itemSummaries") or []
            page_new = sum(self._record_summary(s, source, sweep_id) for s in items)
            self.conn.commit()
            new += page_new
            seen += len(items)
            pages += 1
            offset += self.s.page_size
            if not items or offset >= total or len(items) < self.s.page_size:
                break
            if stop_when_known and page_new == 0:
                break
            if max_pages and pages >= max_pages:
                break
        return {"pages": pages, "seen": seen, "new": new, "total": total}

    # ------------------------------------------------------------ search tasks
    def new_listings(self):
        return self._search_pages(None, "newlyListed", "new_listings",
                                  max_pages=self.s.new_listings_max_pages, stop_when_known=True)

    def ending_soon(self):
        now = self.clock.now()
        filters = ["buyingOptions:{AUCTION}",
                   f"itemEndDate:[{ebay_iso(now)}..{ebay_iso(now + timedelta(minutes=self.s.ending_soon_window_minutes))}]"]
        return self._search_pages(filters, "endingSoonest", "ending_soon", max_pages=10)

    def _sweep_open(self):
        return self.conn.execute("SELECT 1 FROM sweeps WHERE finished_at IS NULL").fetchone() is not None

    def full_sweep(self, max_pages_per_tick: int = 60):
        row = self.conn.execute("SELECT * FROM sweeps WHERE finished_at IS NULL ORDER BY sweep_id DESC LIMIT 1").fetchone()
        if row is None:
            state = {"bands": [list(b) for b in self.s.price_bands], "offset": 0, "checked": False}
            cur = self.conn.execute("INSERT INTO sweeps(started_at, state_json) VALUES (?, ?)",
                                    (to_iso(self.clock.now()), json.dumps(state)))
            sweep_id = cur.lastrowid
            self.conn.commit()
        else:
            sweep_id, state = row["sweep_id"], json.loads(row["state_json"])
        pages = 0
        while state["bands"] and pages < max_pages_per_tick:
            lo, hi = state["bands"][0]
            filters = [f"price:[{lo}..{hi}]", "priceCurrency:USD"]
            if not state["checked"]:
                body = self.client.search(filters=filters, offset=0)
                pages += 1
                total = body.get("total", 0)
                if total > self.s.result_window and hi - lo > 0.02:
                    mid = round((lo + hi) / 2, 2)
                    state["bands"][0:1] = [[lo, mid], [mid, hi]]
                    self._save_sweep(sweep_id, state)
                    continue
                for s in body.get("itemSummaries") or []:
                    self._record_summary(s, "sweep", sweep_id)
                state["checked"] = True
                state["offset"] = self.s.page_size
                if total <= self.s.page_size:
                    self._next_band(state)
                self._save_sweep(sweep_id, state)
                continue
            res = self._search_pages(filters, None, "sweep", max_pages=1, sweep_id=sweep_id,
                                     start_offset=state["offset"])
            pages += 1
            state["offset"] += self.s.page_size
            if (res["pages"] == 0 or res["seen"] < self.s.page_size
                    or state["offset"] >= min(res["total"] or 0, self.s.result_window)):
                self._next_band(state)
            self._save_sweep(sweep_id, state)
        if not state["bands"]:
            return self._close_sweep(sweep_id)
        return {"sweep_id": sweep_id, "bands_left": len(state["bands"]), "pages": pages}

    @staticmethod
    def _next_band(state):
        state["bands"].pop(0)
        state["offset"] = 0
        state["checked"] = False

    def _save_sweep(self, sweep_id, state):
        self.conn.execute("UPDATE sweeps SET state_json = ? WHERE sweep_id = ?", (json.dumps(state), sweep_id))
        self.conn.commit()

    def _close_sweep(self, sweep_id):
        now = self.clock.now()
        seen = self.conn.execute("SELECT COUNT(*) n FROM listings WHERE last_seen_sweep = ?", (sweep_id,)).fetchone()["n"]
        self.conn.execute(
            "UPDATE listings SET missing_sweeps = missing_sweeps + 1 WHERE status = 'active' "
            "AND (last_seen_sweep IS NULL OR last_seen_sweep < ?) AND first_seen_at < "
            "(SELECT started_at FROM sweeps WHERE sweep_id = ?)", (sweep_id, sweep_id))
        missing = self.conn.execute(
            "SELECT item_id, end_time FROM listings WHERE status = 'active' AND missing_sweeps >= ? "
            "AND item_id NOT IN (SELECT item_id FROM outcomes)", (self.s.missing_sweeps_before_check,)).fetchall()
        for r in missing:
            end = parse_iso(r["end_time"])
            if end is None or end <= now:
                self.conn.execute(
                    "INSERT OR IGNORE INTO end_queue(item_id, reason, next_due_at) VALUES (?, 'missing', ?)",
                    (r["item_id"], to_iso(now)))
        self.conn.execute("UPDATE sweeps SET finished_at = ?, items_seen = ? WHERE sweep_id = ?",
                          (to_iso(now), seen, sweep_id))
        self.conn.commit()
        return {"sweep_id": sweep_id, "finished": True, "items_seen": seen, "missing_queued": len(missing)}

    # ------------------------------------------------------------ item reads
    def _fetch_many(self, item_ids: list[str]) -> dict[str, tuple[int, dict | None]]:
        """Read items via getItems (20 per call) with a per-item getItem fallback.
        Returns {item_id: (http_status, body_or_None)}."""
        out: dict[str, tuple[int, dict | None]] = {}
        if self._batch_ok:
            for i in range(0, len(item_ids), 20):
                chunk = item_ids[i:i + 20]
                resp = self.client.get_items(chunk)
                if resp.status in (200, 207):
                    found = {it["itemId"]: it for it in (resp.body or {}).get("items") or []}
                    for iid in chunk:
                        out[iid] = (200, found[iid]) if iid in found else (404, None)
                elif resp.status == 404:
                    for iid in chunk:
                        out[iid] = (404, None)
                else:
                    log.warning("getItems returned %s; switching to getItem", resp.status)
                    self._batch_ok = False
                    break
        for iid in item_ids:
            if iid not in out:
                resp = self.client.get_item(iid)
                out[iid] = (resp.status, resp.body if resp.status == 200 else None)
        return out

    def final_look(self):
        now = self.clock.now()
        rows = self.conn.execute(
            "SELECT item_id FROM listings WHERE is_auction = 1 AND status = 'active' "
            "AND end_time > ? AND end_time <= ? AND item_id NOT IN "
            "(SELECT item_id FROM snapshots WHERE source = 'final_look')",
            (to_iso(now), to_iso(now + timedelta(minutes=FINAL_LOOK_MINUTES)))).fetchall()
        ids = [r["item_id"] for r in rows]
        if not ids:
            return {"items": 0}
        results = self._fetch_many(ids)
        for iid, (status, body) in results.items():
            snap = detail_to_snapshot(body) if body else {"item_id": iid}
            snap.update(item_id=iid, observed_at=to_iso(now), source="final_look", http_status=status)
            db.insert_snapshot(self.conn, snap)
        self.conn.commit()
        return {"items": len(ids)}

    def end_checks(self, max_items: int = 400):
        now = self.clock.now()
        rows = self.conn.execute(
            "SELECT q.item_id, q.reason, q.attempts FROM end_queue q WHERE q.finalized = 0 "
            "AND q.next_due_at <= ? ORDER BY q.next_due_at LIMIT ?", (to_iso(now), max_items)).fetchall()
        if not rows:
            return {"checked": 0}
        results = self._fetch_many([r["item_id"] for r in rows])
        decided = 0
        for r in rows:
            iid = r["item_id"]
            status, body = results.get(iid, (None, None))
            snap = detail_to_snapshot(body) if body else {"item_id": iid}
            snap.update(item_id=iid, observed_at=to_iso(now), source="end_check", http_status=status)
            db.insert_snapshot(self.conn, snap)
            if body:
                db.upsert(self.conn, "listings", {**detail_to_listing(body), "first_seen_at": to_iso(now),
                                                  "last_seen_at": to_iso(now)},
                          keep_existing=("first_seen_at", "first_price", "description_html",
                                         "description_text", "raw_detail_json"))
            if decided_now := self._decide(iid, r, status):
                decided += decided_now
        self.conn.commit()
        return {"checked": len(rows), "decided": decided}

    def _decide(self, iid, qrow, status) -> int:
        now = self.clock.now()
        listing = dict(self.conn.execute("SELECT * FROM listings WHERE item_id = ?", (iid,)).fetchone())
        snaps = [dict(x) for x in self.conn.execute(
            "SELECT * FROM snapshots WHERE item_id = ? ORDER BY observed_at, id", (iid,)).fetchall()]
        insight = self._insight_for(iid)
        result = infer_outcome(listing, snaps, insight)
        if result is None:
            attempts = qrow["attempts"] + 1
            delays = self.s.post_end_delays
            if qrow["reason"] == "missing" or attempts >= len(delays):
                # Still listed: back to active, the next sweep or end time will re-queue it.
                self.conn.execute("UPDATE listings SET status = 'active', missing_sweeps = 0 WHERE item_id = ?", (iid,))
                self.conn.execute("DELETE FROM end_queue WHERE item_id = ?", (iid,))
            else:
                end = parse_iso(listing.get("end_time")) or now
                due = max(now + timedelta(minutes=5), end + timedelta(minutes=delays[attempts]))
                self.conn.execute("UPDATE end_queue SET attempts = ?, next_due_at = ? WHERE item_id = ?",
                                  (attempts, to_iso(due), iid))
            return 0
        if status is None and qrow["attempts"] + 1 < len(self.s.post_end_delays):
            self.conn.execute("UPDATE end_queue SET attempts = attempts + 1, next_due_at = ? WHERE item_id = ?",
                              (to_iso(now + timedelta(minutes=self.s.post_end_delays[qrow["attempts"] + 1])), iid))
            return 0
        result.update(item_id=iid, determined_at=to_iso(now))
        db.upsert(self.conn, "outcomes", result)
        self.conn.execute("UPDATE listings SET status = 'ended' WHERE item_id = ?", (iid,))
        self.conn.execute("UPDATE end_queue SET finalized = 1, attempts = attempts + 1 WHERE item_id = ?", (iid,))
        return 1

    def details(self):
        remaining = self.client.budget.remaining(BROWSE) - self.s.end_check_reserve
        n = min(self.s.detail_batch_per_tick, max(0, remaining))
        if n <= 0:
            return {"fetched": 0, "reason": "reserve"}
        now = self.clock.now()
        rows = self.conn.execute(
            "SELECT item_id FROM listings WHERE detail_fetched_at IS NULL AND detail_error IS NULL "
            "AND status = 'active' ORDER BY "
            "CASE WHEN is_auction = 1 AND end_time IS NOT NULL THEN 0 ELSE 1 END, "
            "end_time ASC, first_seen_at DESC LIMIT ?", (n,)).fetchall()
        fetched = 0
        for r in rows:
            resp = self.client.get_item(r["item_id"])
            ts = to_iso(self.clock.now())
            if resp.status == 200:
                row = detail_to_listing(resp.body)
                row.update(first_seen_at=ts, last_seen_at=ts, detail_fetched_at=ts, first_price=row_price(resp.body))
                db.upsert(self.conn, "listings", row, keep_existing=("first_seen_at", "first_price"))
                snap = detail_to_snapshot(resp.body)
                snap.update(observed_at=ts, source="detail", http_status=200)
                db.insert_snapshot(self.conn, snap)
                fetched += 1
            elif resp.status == 404:
                self.conn.execute("UPDATE listings SET detail_error = '404' WHERE item_id = ?", (r["item_id"],))
                self.conn.execute("INSERT OR IGNORE INTO end_queue(item_id, reason, next_due_at) VALUES (?, 'missing', ?)",
                                  (r["item_id"], to_iso(now)))
            else:
                self.conn.execute("UPDATE listings SET detail_error = ? WHERE item_id = ?", (str(resp.status), r["item_id"]))
            self.conn.commit()
        return {"fetched": fetched}

    # ------------------------------------------------------------ marketplace insights
    def _insight_for(self, iid):
        row = self.conn.execute("SELECT * FROM sales_insights WHERE item_id = ? ORDER BY last_sold_date DESC LIMIT 1",
                                (iid,)).fetchone()
        return dict(row) if row else None

    def insights(self, max_pages: int = 50):
        stored, offset = 0, 0
        for _ in range(max_pages):
            try:
                body = self.client.item_sales_search(offset=offset)
            except ApiError as exc:
                if exc.status in (401, 403):
                    log.warning("Marketplace Insights not available to this application (%s)", exc.status)
                    db.set_meta(self.conn, "insights_access", "denied")
                    return {"access": "denied"}
                raise
            sales = body.get("itemSales") or []
            now = to_iso(self.clock.now())
            for it in sales:
                db.upsert(self.conn, "sales_insights", {
                    "item_id": it.get("itemId"),
                    "last_sold_date": it.get("lastSoldDate"),
                    "last_sold_price": float((it.get("lastSoldPrice") or {}).get("value") or 0) or None,
                    "total_sold_qty": int(it.get("totalSoldQuantity") or 0) or None,
                    "title": it.get("title"),
                    "condition": it.get("condition"),
                    "raw_json": it,
                    "fetched_at": now,
                }, key=("item_id", "last_sold_date"))
                stored += 1
            self.conn.commit()
            offset += 200
            if len(sales) < 200 or offset >= min(body.get("total", 0), self.s.result_window):
                break
        db.set_meta(self.conn, "insights_access", "granted")
        # Upgrade outcomes that a sale record now confirms.
        for r in self.conn.execute(
                "SELECT item_id FROM listings WHERE item_id IN (SELECT item_id FROM sales_insights) "
                "AND item_id NOT IN (SELECT item_id FROM outcomes WHERE method = 'marketplace_insights')").fetchall():
            self._decide(r["item_id"], {"attempts": 99, "reason": "insights"}, 200)
        self.conn.commit()
        return {"stored": stored}


def row_price(s: dict) -> float | None:
    p = s.get("currentBidPrice") or s.get("price")
    try:
        return float(p["value"]) if p else None
    except (KeyError, TypeError, ValueError):
        return None
