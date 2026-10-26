"""The published tables and the app data are de-identified and internally consistent."""
import json
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "public"
FORBIDDEN_COLUMNS = {"item_id", "itemid", "legacy_item_id", "item_web_url", "url", "title", "description",
                     "short_description", "image", "image_url", "username", "seller_username", "raw", "json"}
ITEM_URL = re.compile(r"ebay\.com/itm|itemWebUrl|v1\|\d{9,}\|")


@pytest.fixture(scope="module")
def listings():
    return pd.read_csv(PUBLIC / "listings.csv.gz")


def test_no_identifying_columns(listings):
    for f in [PUBLIC / "listings.csv.gz", PUBLIC / "auction_bids.csv.gz"]:
        cols = {c.lower() for c in pd.read_csv(f, nrows=1).columns}
        assert not cols & FORBIDDEN_COLUMNS, f


def test_seller_keys_are_hashes(listings):
    assert listings["seller"].astype(str).str.fullmatch(r"[0-9a-f]{12}").all()


def test_listing_keys_are_small_integers(listings):
    assert listings["listing"].is_unique
    assert listings["listing"].between(1, 10 ** 6).all()


def test_feedback_rounded(listings):
    fb = listings["seller_feedback_score"].dropna().abs()
    fb = fb[fb >= 100]
    digits = fb.astype(int).astype(str).str.rstrip("0").str.len()
    assert (digits <= 2).all()


def test_no_item_urls_or_ids_in_text_outputs():
    files = [ROOT / "app" / "data.js", ROOT / "docs" / "results.json", *PUBLIC.glob("*.csv"), *PUBLIC.glob("*.json")]
    for f in files:
        if f.exists():
            assert not ITEM_URL.search(f.read_text(encoding="utf-8")), f


def test_app_data_is_aggregate():
    txt = (ROOT / "app" / "data.js").read_text(encoding="utf-8")
    assert len(txt) < 400_000
    seller_keys = set(pd.read_csv(PUBLIC / "listings.csv.gz", usecols=["seller"])["seller"].astype(str))
    found = set(re.findall(r"[0-9a-f]{12}", txt))
    assert not found & seller_keys


def test_outcome_invariants(listings):
    sold = listings[listings["outcome"] == "sold"]
    assert len(sold) == 2063
    assert sold["final_price"].notna().all() and (sold["final_price"] > 0).all()
    assert listings.loc[listings["outcome"] == "active", "final_price"].isna().all()
    assert set(listings["outcome"]) <= {"active", "sold", "unsold", "ended_unknown", "reserve_not_met"}


def test_gold_listings_never_sold(listings):
    g = listings[listings["gold"] == 1]
    assert len(g) == 299 and g["outcome"].eq("active").all()


def test_results_match_public_data(listings):
    r = json.loads((ROOT / "docs" / "results.json").read_text())
    assert r["overview"]["listings"] == len(listings)
    assert r["overview"]["outcome_counts"]["sold"] == int((listings["outcome"] == "sold").sum())
