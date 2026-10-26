import numpy as np
import pandas as pd
import pytest

from src.stats import boot_ci, boot_ratio_ci, rate_table, two_prop, wilson


def test_wilson_known_values():
    lo, hi = wilson(373, 724)
    assert lo == pytest.approx(0.4788, abs=1e-4) and hi == pytest.approx(0.5514, abs=1e-4)
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == 1.0
    assert all(np.isnan(wilson(0, 0)))


def test_wilson_contains_point_estimate():
    for k, n in [(1, 3), (7, 25), (105, 152), (0, 566)]:
        lo, hi = wilson(k, n)
        assert lo <= k / n <= hi


def test_rate_table():
    df = pd.DataFrame({"g": list("aaabb"), "sold": [1, 0, 1, 0, 0]})
    t = rate_table(df, "g")
    assert t.loc["a", "k"] == 2 and t.loc["a", "n"] == 3 and t.loc["b", "rate"] == 0


def test_two_prop():
    r = two_prop(63, 100, 26, 73)
    assert r["diff"] == pytest.approx(0.63 - 26 / 73)
    assert r["lo"] < r["diff"] < r["hi"] and r["p"] < 0.001


def test_bootstrap_intervals():
    rng = np.random.default_rng(0)
    x = rng.normal(100, 10, 400)
    lo, hi = boot_ci(x, n_boot=1000)
    assert lo < np.median(x) < hi
    lo, hi = boot_ratio_ci(2 * x, x, n_boot=1000)
    assert lo < 2 < hi
    assert boot_ci(x, n_boot=500) == boot_ci(x, n_boot=500)  # seeded
