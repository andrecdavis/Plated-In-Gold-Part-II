import pandas as pd
import pytest

from collector.features import (BAD_MODELS, add_features, case_material, case_size_mm, connectivity, extract_model,
                          model_from_aspect, normalize_title, standardize_condition)
from tests.collector.conftest import fixture


def test_title_model_matches_plated_in_gold():
    """The title rule reproduces the Plated in Gold labels on its own dataset."""
    rows = fixture("plated_titles.json")
    def label(title):
        m = extract_model(normalize_title(title))
        return None if m in BAD_MODELS else m

    mismatches = [r for r in rows if label(r["title"]) != r["model"]]
    assert not mismatches, mismatches[:5]


@pytest.mark.parametrize("value, expected", [
    ("Apple Watch Series 9", "Series 9"),
    ("Apple Watch SE (2nd Generation)", "SE 2"),
    ("Apple Watch SE", "SE 1"),
    ("Apple Watch Ultra 2", "Ultra 2"),
    ("Apple Watch Ultra", "Ultra 1"),
    ("Apple Watch Series 10 46mm", "Series 10"),
    ("Galaxy Watch", None),
    (None, None),
])
def test_model_from_aspect(value, expected):
    assert model_from_aspect(value) == expected


def test_case_size_material_connectivity():
    assert case_size_mm({"Case Size": "45 mm"}, "") == 45.0
    assert case_size_mm({}, "Apple Watch Series 7 41mm GPS") == 41.0
    assert case_size_mm({}, "Apple Watch") is None
    assert case_material({"Case Material": "Stainless Steel"}, "", None) == "Stainless Steel"
    assert case_material({}, "Apple Watch Ultra 2", "Ultra 2") == "Titanium"
    assert connectivity({"Connectivity": "Bluetooth, Cellular, GPS"}, "") == "GPS + Cellular"
    assert connectivity({}, "Series 8 GPS 45mm") == "GPS"


def test_condition_standardization():
    assert standardize_condition("Pre-owned", "3000", "") == "Used"
    assert standardize_condition("Open box", "1500", "") == "Open box"
    assert standardize_condition("New other (see details)", "1500", "") == "New"
    assert standardize_condition("Used", "3000", "apple watch brand new sealed") == "New"
    assert standardize_condition("Very Good - Refurbished", "2020", "") == "Very Good - Refurbished"


def test_add_features_frame():
    df = pd.DataFrame({
        "title": ["Apple Watch Series 9 45mm 24K Gold Plated Milanese", "Apple Watch Ultra 2 49mm"],
        "aspects": [{"Model": "Apple Watch Series 9"}, {}],
        "condition": ["New", "Used"], "condition_id": ["1000", "3000"],
        "location_country": ["US", "GB"], "seller_username": ["a", "a"], "ship_to_worldwide": [1, 0],
    })
    out = add_features(df)
    assert list(out["model"]) == ["Series 9", "Ultra 2"]
    assert list(out["gold"]) == [1, 0] and list(out["premium_band"]) == [1, 0]
    assert list(out["titanium"]) == [0, 1]
    assert list(out["country"]) == ["United States", "United Kingdom"]
    assert list(out["power_seller"]) == [1, 1]
