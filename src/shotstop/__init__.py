"""shotstop: stopping rules for shot-based pass/fail tests of noisy quantum circuits."""

from .circuits import CircuitSpec, exact_distribution, make_spec
from .stats import hoeffding_radius, spending_schedule, tv_distance
from .verdicts import Outcome, chi2_fixed, sample_cumulative, sequential, stability, tv_fixed

__all__ = [
    "CircuitSpec",
    "Outcome",
    "chi2_fixed",
    "exact_distribution",
    "hoeffding_radius",
    "make_spec",
    "sample_cumulative",
    "sequential",
    "spending_schedule",
    "stability",
    "tv_distance",
    "tv_fixed",
]
__version__ = "0.1.0"
