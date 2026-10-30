"""Shot-based pass/fail procedures for a circuit whose ideal output distribution ``p0`` is known.

A circuit is *correct* if TV(p, p0) <= tau and *buggy* otherwise, where p is the true noisy output
distribution. Every procedure returns an :class:`Outcome` for a batch of independent test runs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2

from .stats import hoeffding_radius, spending_schedule, tv_distance, wald_radius


@dataclass
class Outcome:
    """Result of ``reps`` independent executions of one test procedure.

    Attributes:
        buggy: Verdict per run (True = declared buggy).
        shots: Shots consumed per run.
        decided: True if the procedure's own stopping criterion fired before the budget ended.
    """

    buggy: np.ndarray
    shots: np.ndarray
    decided: np.ndarray


def sample_cumulative(p: np.ndarray, reps: int, steps: int, batch: int, rng: np.random.Generator) -> np.ndarray:
    """Cumulative outcome counts after each batch, shape (reps, steps, K)."""
    p = np.clip(p, 0.0, None)
    p = p / p.sum()
    return np.cumsum(rng.multinomial(batch, p, size=(reps, steps)), axis=1)


def _first_true(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Index of the first True along axis 1 (last index if none) and whether any was True."""
    any_hit = mask.any(axis=1)
    idx = np.where(any_hit, mask.argmax(axis=1), mask.shape[1] - 1)
    return idx, any_hit


def tv_fixed(cum: np.ndarray, p0: np.ndarray, tau: float, batch: int) -> Outcome:
    """Classical baseline: spend the whole budget, declare buggy if TV(p_hat, p0) > tau."""
    reps, steps, _ = cum.shape
    p_hat = cum[:, -1] / (steps * batch)
    return Outcome(tv_distance(p_hat, p0) > tau, np.full(reps, steps * batch), np.ones(reps, bool))


def chi2_fixed(cum: np.ndarray, p0: np.ndarray, batch: int, alpha: float = 0.05) -> Outcome:
    """Standard statistical assertion: Pearson chi-square test of exact equality with p0."""
    reps, steps, _ = cum.shape
    n = steps * batch
    obs = cum[:, -1]
    support = p0 > 1e-12
    stat = (((obs[:, support] - n * p0[support]) ** 2) / (n * p0[support])).sum(axis=1)
    pval = chi2.sf(stat, df=max(int(support.sum()) - 1, 1))
    off_support = obs[:, ~support].sum(axis=1) > 0
    return Outcome((pval < alpha) | off_support, np.full(reps, n), np.ones(reps, bool))


def stability(cum: np.ndarray, p0: np.ndarray, tau: float, batch: int, delta: float, patience: int = 2) -> Outcome:
    """Incremental-execution style rule: stop once the cumulative distribution stops moving.

    Stops at the first look where the last ``patience`` batch-to-batch total variation changes are
    all below ``delta``; the verdict compares the point estimate to ``tau``. No error guarantee.
    """
    reps, steps, _ = cum.shape
    n_t = batch * np.arange(1, steps + 1)
    est = cum / n_t[None, :, None]
    moved_little = tv_distance(est[:, 1:], est[:, :-1]) < delta  # column j compares look j+1 with j
    stable = np.zeros((reps, steps), bool)
    for j in range(patience - 1, steps - 1):
        stable[:, j + 1] = moved_little[:, j - patience + 1 : j + 1].all(axis=1)
    idx, hit = _first_true(stable)
    chosen = est[np.arange(reps), idx]
    return Outcome(tv_distance(chosen, p0) > tau, n_t[idx], hit)


def sequential(
    cum: np.ndarray,
    p0: np.ndarray,
    tau: float,
    batch: int,
    alpha: float = 0.05,
    schedule: str = "uniform",
    radius: str = "hoeffding",
) -> Outcome:
    """Anytime-valid sequential test: stop when the confidence interval for TV excludes ``tau``.

    With ``radius='hoeffding'`` and ``schedule`` in {uniform, polynomial} the probability that any
    stopped verdict is wrong is at most ``alpha``. ``wald`` and ``naive`` are ablation variants.
    If no look separates the interval from ``tau`` the run falls back to the point estimate at the
    end of the budget and is marked undecided.
    """
    reps, steps, k = cum.shape
    n_t = batch * np.arange(1, steps + 1)
    est = cum / n_t[None, :, None]
    tv_hat = tv_distance(est, p0)
    delta_t = spending_schedule(schedule, steps, alpha)[None, :]
    if radius == "hoeffding":
        rad = hoeffding_radius(n_t[None, :], k, delta_t)
    elif radius == "wald":
        rad = wald_radius(est, p0, n_t[None, :], delta_t)
    else:
        raise ValueError(f"unknown radius {radius!r}")
    says_buggy = tv_hat - rad > tau
    says_ok = tv_hat + rad < tau
    idx, hit = _first_true(says_buggy | says_ok)
    rows = np.arange(reps)
    buggy = np.where(hit, says_buggy[rows, idx], tv_hat[:, -1] > tau)
    return Outcome(buggy, n_t[idx], hit)
