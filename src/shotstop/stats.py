"""Distances, concentration radii and error-spending schedules."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


def tv_distance(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Total variation distance along the last axis."""
    return 0.5 * np.abs(p - q).sum(axis=-1)


def hoeffding_radius(n_shots, k_outcomes: int, delta):
    """Finite-sample radius r with P(|TV(p_hat, p0) - TV(p, p0)| >= r) <= delta.

    TV(p_hat, p0) is the maximum over the 2**K outcome subsets S of p_hat(S) - p0(S); a two-sided
    Hoeffding bound plus a union bound over subsets gives r = sqrt((K ln 2 + ln(2/delta)) / (2 n)).
    """
    return np.sqrt((k_outcomes * np.log(2.0) + np.log(2.0 / np.asarray(delta))) / (2.0 * np.asarray(n_shots)))


def wald_radius(p_hat: np.ndarray, p0: np.ndarray, n_shots, delta) -> np.ndarray:
    """Asymptotic (delta-method) radius for TV(p_hat, p0); not valid at small n or near TV = 0.

    ``p_hat`` has shape (..., K); ``n_shots`` and ``delta`` broadcast against ``p_hat[..., 0]``.
    """
    s = np.sign(p_hat - p0)
    var = np.clip(1.0 - (s * p_hat).sum(axis=-1) ** 2, 0.0, None)
    return norm.isf(np.asarray(delta) / 2.0) * 0.5 * np.sqrt(var / n_shots)


def spending_schedule(name: str, steps: int, alpha: float) -> np.ndarray:
    """Per-look error levels delta_t.

    ``uniform`` splits alpha over the planned looks, ``polynomial`` uses alpha / (t (t + 1)) (valid
    for any number of looks), and ``naive`` re-uses alpha at every look (repeated peeking).
    """
    t = np.arange(1, steps + 1, dtype=float)
    if name == "uniform":
        return np.full(steps, alpha / steps)
    if name == "polynomial":
        return alpha / (t * (t + 1.0))
    if name == "naive":
        return np.full(steps, alpha)
    raise ValueError(f"unknown schedule {name!r}")
