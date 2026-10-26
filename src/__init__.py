"""Plated in Gold, Part II: analysis package (cleaning, statistics, models, figures)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DB = ROOT / "data" / "raw" / "ebay_apple_watch.db"
PUBLIC_DIR = ROOT / "data" / "public"
IMAGES = ROOT / "images"
TZ = "America/Denver"
