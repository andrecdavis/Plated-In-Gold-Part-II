"""Feature extraction compatible with the Plated in Gold smartwatch dataset.

The title-based columns (model, family, hermes, cellular, titanium, gold,
premium_band, ceramic) reproduce the Plated in Gold rules so the two datasets
can be compared directly. Columns derived from eBay item specifics
(case_size, material, connectivity, model_aspect) add structure that the
original title-only dataset did not have.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

from .parsing import COUNTRY_NAMES

# ---------------------------------------------------------------- text helpers

def remove_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize_title(title: str | None) -> str:
    """Lowercase, strip accents, remove case sizes like '45mm' (Plated in Gold rule)."""
    t = remove_accents(str(title or "")).lower()
    return re.sub(r"\d{2}\s*mm", "", t)


# ---------------------------------------------------------------- model / family

def extract_model(text) -> str | None:
    """Plated in Gold model rule, applied to a normalized title."""
    text = str(text).lower()

    ultra_num = re.search(r"ultra\s*(\d)", text)
    if ultra_num:
        return f"Ultra {ultra_num.group(1)}"
    if re.search(r"\bultra\b", text):
        return "Ultra 1"

    se_num = re.search(r"\bse\s*(\d+)", text)
    if se_num:
        return f"SE {se_num.group(1)}"
    if re.search(r"\bse\b", text):
        return "SE 1"

    series_num = re.search(r"\bseries\s*(\d+)", text)
    series = re.search(r"\bseries\b", text)
    s_match = re.search(r"\bs(\d+)\b|gen\s*(\d+)", text)
    watch_match = re.search(r"watch\s*(\d+)", text)
    series_zero = re.search(r"sport|a1553|a1554|1st|gen\s*1", text)
    serie_match = re.search(r"serie\s*(\d+)|seri\s*(\d+)", text)
    gen_match = re.search(r"\bgen\b\s*(\d+)", text)
    if series_num:
        return f"Series {series_num.group(1)}"
    if gen_match:
        return f"Series {gen_match.group(1)}"
    if series:
        return "Series 1"
    if s_match:
        return f"Series {s_match.group(1)}"
    if watch_match:
        return f"Series {watch_match.group(1)}"
    if serie_match:
        return f"Series {serie_match.group(1)}"
    if series_zero:
        return "Series 0"
    return None


BAD_MODELS = {"None", "Series 24", "Series 44", "Series None", "SE 44"}

_ORDINAL_GEN = re.compile(r"\(?\s*(\d)\s*(?:st|nd|rd|th)\s*gen(?:eration)?\s*\)?")


def model_from_aspect(value: str | None) -> str | None:
    """Item-specifics model, e.g. 'Apple Watch SE (2nd Generation)' -> 'SE 2'."""
    if not value:
        return None
    t = remove_accents(str(value)).lower()
    t = re.sub(r"\d{2}\s*mm", "", t)
    t = re.sub(r"\bse\s*" + _ORDINAL_GEN.pattern, r"se \1", t)
    t = re.sub(r"ultra\s*" + _ORDINAL_GEN.pattern, r"ultra \1", t)
    if re.search(r"\bse\b|ultra|series|watch\s*\d", t):
        m = extract_model(t)
        return None if m in BAD_MODELS else m
    return None


def extract_family(model) -> str | None:
    text = str(model).lower()
    if re.search(r"\bultra\b", text):
        return "Ultra"
    if re.search(r"\bseries\b", text):
        return "Series"
    if re.search(r"\bse\b", text):
        return "SE"
    return None


# ---------------------------------------------------------------- premium flags (title)

PREMIUM_PATTERNS = {
    "hermes": r"\bhermes\b",
    "cellular": r"cellular|lte",
    "titanium": r"\btitanium\b",
    "gold": r"24k|24ct|24\skarat",
    "premium_band": r"milanese|link",
    "ceramic": r"ceramic",
}

# ---------------------------------------------------------------- item specifics

def case_size_mm(aspects: dict, title: str | None) -> float | None:
    for key in ("Case Size", "Watch Case Size", "Case Diameter", "Size"):
        v = aspects.get(key)
        if v:
            m = re.search(r"(\d{2}(?:\.\d)?)\s*mm", str(v).lower())
            if m:
                return float(m.group(1))
    m = re.search(r"\b(3[8-9]|4[0-9])\s*mm\b", str(title or "").lower())
    return float(m.group(1)) if m else None


MATERIALS = [
    ("Titanium", r"titanium"),
    ("Ceramic", r"ceramic"),
    ("Stainless Steel", r"stainless|steel"),
    ("Gold", r"\b(?:18k|24k|24ct)\b|solid gold|gold plated|gold-plated"),
    ("Aluminum", r"alumin"),
]


def case_material(aspects: dict, title: str | None, model: str | None) -> str | None:
    for key in ("Case Material", "Material"):
        v = aspects.get(key)
        if v:
            for name, pat in MATERIALS:
                if re.search(pat, str(v).lower()):
                    return name
    t = str(title or "").lower()
    for name, pat in MATERIALS:
        if re.search(pat, t):
            return name
    if isinstance(model, str) and model.startswith("Ultra"):
        return "Titanium"
    return None


def connectivity(aspects: dict, title: str | None) -> str | None:
    blob = " ".join(str(aspects.get(k, "")) for k in ("Connectivity", "Features", "Network", "Model"))
    blob = (blob + " " + str(title or "")).lower()
    if re.search(r"cellular|lte|\b4g\b|\b5g\b|gps\s*\+\s*cell", blob):
        return "GPS + Cellular"
    if re.search(r"\bgps\b", blob):
        return "GPS"
    return None


# ---------------------------------------------------------------- condition

CONDITION_BY_ID = {
    "1000": "New", "1500": "New", "1750": "New", "2000": "Certified - Refurbished",
    "2010": "Excellent - Refurbished", "2020": "Very Good - Refurbished",
    "2030": "Good - Refurbished", "2500": "Seller refurbished", "2750": "Used",
    "2990": "Used", "3000": "Used", "3010": "Used", "4000": "Used", "5000": "Used",
    "6000": "Used", "7000": "For parts or not working",
}


def standardize_condition(condition: str | None, condition_id, title_norm: str) -> str:
    text = str(condition or "").strip().lower()
    if text.startswith("open box"):
        cond = "Open box"
    elif condition_id is not None and str(condition_id) in CONDITION_BY_ID:
        cond = CONDITION_BY_ID[str(condition_id)]
    elif text.startswith("new"):
        cond = "New"
    elif "refurb" in text:
        cond = "Seller refurbished"
    elif text.startswith(("used", "pre-owned")):
        cond = "Used"
    elif "parts" in text:
        cond = "For parts or not working"
    else:
        cond = "Unknown"
    if re.search(r"brand\s*new|unopened", title_norm) and cond not in ("New", "Open box"):
        cond = "New"
    return cond


# ---------------------------------------------------------------- dataframe

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Expects columns: title, aspects (dict), condition, condition_id, location_country,
    seller_username, ship_to_worldwide."""
    df = df.copy()
    aspects = df["aspects"].apply(lambda a: a if isinstance(a, dict) else {})
    df["title_norm"] = df["title"].map(normalize_title)
    df["model_from_title"] = df["title_norm"].map(extract_model)
    df.loc[df["model_from_title"].isin(BAD_MODELS), "model_from_title"] = None
    df["model_aspect"] = aspects.map(lambda a: model_from_aspect(a.get("Model")))
    df["model"] = df["model_aspect"].fillna(df["model_from_title"])
    df["family"] = df["model"].map(lambda m: extract_family(m) if isinstance(m, str) else None)
    for col, pat in PREMIUM_PATTERNS.items():
        df[col] = df["title_norm"].str.contains(pat, case=False, regex=True, na=False).astype(int)
    df.loc[df["model"].fillna("").str.startswith("Ultra"), "titanium"] = 1
    df["case_size"] = [case_size_mm(a, t) for a, t in zip(aspects, df["title"])]
    df["material"] = [case_material(a, t, m) for a, t, m in zip(aspects, df["title"], df["model"])]
    df["connectivity"] = [connectivity(a, t) for a, t in zip(aspects, df["title"])]
    df["condition_std"] = [standardize_condition(c, i, t) for c, i, t in
                           zip(df["condition"], df["condition_id"], df["title_norm"])]
    df["country"] = df["location_country"].map(lambda c: COUNTRY_NAMES.get(c, c) if c else None)
    df["seller_id"] = df["seller_username"]
    df["worldwide_shipping"] = df["ship_to_worldwide"]
    df["is_bundle"] = df["title_norm"].str.contains(r"\bbundle\b|\blot\b|iphone", regex=True, na=False).astype(int)
    counts = df["seller_id"].map(df["seller_id"].value_counts())
    df["power_seller"] = (counts >= 2).astype(int)
    return df
