"""Collector settings. Every field can be overridden with an environment variable."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields

from . import DB_PATH, ROOT

API_ROOT = "https://api.ebay.com"
SANDBOX_API_ROOT = "https://api.sandbox.ebay.com"

SCOPE_BASE = "https://api.ebay.com/oauth/api_scope"
SCOPE_INSIGHTS = "https://api.ebay.com/oauth/api_scope/buy.marketplace.insights"

# Price bands (USD) used to split the search so no single query exceeds the
# 10,000-result window of item_summary/search. Bands that are still too large
# are halved automatically at run time.
DEFAULT_PRICE_BANDS = (
    (0, 25), (25, 50), (50, 75), (75, 100), (100, 125), (125, 150),
    (150, 175), (175, 200), (200, 250), (250, 300), (300, 350), (350, 400),
    (400, 500), (500, 650), (650, 800), (800, 1000), (1000, 100000),
)


def load_dotenv(path=ROOT / ".env") -> None:
    """Read KEY=VALUE lines from .env into os.environ without overriding existing values."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default, cast):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    if cast is bool:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return cast(raw)


@dataclass
class Settings:
    client_id: str = ""
    client_secret: str = ""
    sandbox: bool = False
    marketplace_id: str = "EBAY_US"
    category_id: str = "178893"          # Smart Watches
    brand: str = "Apple"
    # Buyer location used by eBay to estimate shipping costs.
    buyer_country: str = "US"
    buyer_zip: str = "80202"
    db_path: str = str(DB_PATH)

    # Call budget (Browse API default: 5,000 calls per day per application).
    daily_call_limit: int = 5000
    safety_margin: float = 0.05
    # Calls held back for end-of-listing checks; detail fetches cannot use them.
    end_check_reserve: int = 1200

    # Task intervals (minutes)
    full_sweep_minutes: int = 24 * 60
    new_listings_minutes: int = 30
    ending_soon_minutes: int = 20
    end_check_minutes: int = 5
    detail_minutes: int = 5
    insights_minutes: int = 24 * 60

    # Ending-soon window: auctions ending within this many minutes are snapshotted.
    ending_soon_window_minutes: int = 45
    new_listings_max_pages: int = 3
    page_size: int = 200
    result_window: int = 10000
    detail_batch_per_tick: int = 60

    # Post-end checks, minutes after the end time (one getItem(s) attempt per entry).
    post_end_delays: tuple = (10, 180, 1440)
    # Fixed-price listings with no end time: how many consecutive full sweeps an item
    # may be missing before it is checked as possibly ended.
    missing_sweeps_before_check: int = 1

    use_marketplace_insights: bool = False
    use_get_items_batch: bool = True

    http_timeout: float = 30.0
    max_retries: int = 5
    backoff_base: float = 2.0
    backoff_cap: float = 120.0

    price_bands: tuple = field(default=DEFAULT_PRICE_BANDS)

    @property
    def api_root(self) -> str:
        return SANDBOX_API_ROOT if self.sandbox else API_ROOT

    @property
    def usable_daily_calls(self) -> int:
        return int(self.daily_call_limit * (1 - self.safety_margin))

    @classmethod
    def from_env(cls, **overrides) -> "Settings":
        load_dotenv()
        s = cls()
        env_names = {
            "client_id": "EBAY_CLIENT_ID",
            "client_secret": "EBAY_CLIENT_SECRET",
            "sandbox": "EBAY_SANDBOX",
            "use_marketplace_insights": "EBAY_USE_MARKETPLACE_INSIGHTS",
            "db_path": "EBAY_DB_PATH",
        }
        for f in fields(cls):
            if f.name in ("price_bands", "post_end_delays"):
                continue
            env_name = env_names.get(f.name, "COLLECTOR_" + f.name.upper())
            current = getattr(s, f.name)
            setattr(s, f.name, _env(env_name, current, type(current)))
        for k, v in overrides.items():
            setattr(s, k, v)
        return s
