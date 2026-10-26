"""Run the full analysis once and collect every number used in the README, app and notebook."""
from __future__ import annotations

import json
import pickle

import numpy as np
import pandas as pd

from . import ROOT
from . import analysis as A
from . import models as M

CACHE = ROOT / "build" / "story.pkl"
RESULTS = ROOT / "docs" / "results.json"


def compute() -> dict:
    r = A.run_all()
    r["sale_model"] = M.fit_sale_model()
    r["price_model"] = M.fit_price_model()
    r["price_grid"] = M.price_grid(r["price_model"])
    r["sale_grid"] = M.sale_grid(r["sale_model"])
    return r


def load(refresh: bool = False) -> dict:
    if CACHE.exists() and not refresh:
        return pickle.loads(CACHE.read_bytes())
    r = compute()
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_bytes(pickle.dumps(r))
    write_results(r)
    return r


def _plain(x):
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, pd.DataFrame):
        return _plain(x.to_dict(orient="records"))
    if isinstance(x, pd.Series):
        return _plain(x.to_dict())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if np.isnan(x) else float(f"{float(x):.6g}")
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    return x


def write_results(r: dict) -> None:
    """Machine-readable numbers for the claims audit (no listing-level rows)."""
    skip = {"paths", "plated", "curves", "frame", "X", "oof", "oof_cal", "oof_logit", "model", "shap"}
    out = {}
    for k, v in r.items():
        if isinstance(v, dict):
            out[k] = {kk: _plain(vv) for kk, vv in v.items() if kk not in skip}
        elif isinstance(v, pd.DataFrame) and k not in ("price_grid", "sale_grid"):
            out[k] = _plain(v)
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(out, indent=1, ensure_ascii=False))
