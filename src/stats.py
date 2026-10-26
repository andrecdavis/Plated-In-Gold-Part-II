"""Small statistics helpers: proportions, bootstrap intervals and tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

SEED = 7


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def rate_table(df: pd.DataFrame, by, success: pd.Series | str = "sold", min_n: int = 1) -> pd.DataFrame:
    """Share of successes by group with Wilson 95% intervals."""
    s = df[success] if isinstance(success, str) else success
    g = pd.DataFrame({"k": s.astype(int), "by": df[by] if isinstance(by, str) else by}).groupby("by", observed=True)["k"]
    t = pd.DataFrame({"k": g.sum(), "n": g.size()})
    t["rate"] = t["k"] / t["n"]
    ci = [wilson(k, n) for k, n in zip(t["k"], t["n"])]
    t["lo"], t["hi"] = [c[0] for c in ci], [c[1] for c in ci]
    return t[t["n"] >= min_n]


def boot_ci(x, stat=np.median, n_boot: int = 4000, seed: int = SEED, alpha: float = 0.05):
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    if len(x) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), (n_boot, len(x)))
    b = stat(x[idx], axis=1)
    return tuple(np.quantile(b, [alpha / 2, 1 - alpha / 2]))


def boot_ratio_ci(a, b, n_boot: int = 4000, seed: int = SEED, alpha: float = 0.05):
    """Bootstrap interval for median(a) / median(b), resampling each group independently."""
    a = np.asarray(pd.Series(a).dropna(), dtype=float)
    b = np.asarray(pd.Series(b).dropna(), dtype=float)
    rng = np.random.default_rng(seed)
    ma = np.median(a[rng.integers(0, len(a), (n_boot, len(a)))], axis=1)
    mb = np.median(b[rng.integers(0, len(b), (n_boot, len(b)))], axis=1)
    return tuple(np.quantile(ma / mb, [alpha / 2, 1 - alpha / 2]))


def two_prop(k1, n1, k2, n2) -> dict:
    """Difference in proportions with a Newcombe-style interval and Fisher's exact p-value."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    lo = d - np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    p = stats.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])[1]
    return dict(p1=p1, p2=p2, diff=d, lo=lo, hi=hi, p=p, n1=int(n1), n2=int(n2), k1=int(k1), k2=int(k2))


def trend_test(df: pd.DataFrame, x: str, y: str) -> dict:
    """Cochran-Armitage style trend: logistic regression of y on an ordinal score."""
    import statsmodels.api as sm
    d = df[[x, y]].dropna()
    m = sm.Logit(d[y].astype(float), sm.add_constant(d[x].astype(float))).fit(disp=0)
    return dict(coef=float(m.params[x]), p=float(m.pvalues[x]), n=int(len(d)))
