import numpy as np

from shotstop import (chi2_fixed, exact_distribution, hoeffding_radius, make_spec, sample_cumulative, sequential,
                      spending_schedule, stability, tv_distance, tv_fixed)


def test_exact_distribution_normalised_and_noise_moves_it():
    spec = make_spec("layered", 3, 0)
    p0 = exact_distribution(spec, 0.0, 0.0)
    noisy = exact_distribution(spec, 0.0, 0.03)
    drift = exact_distribution(spec, 0.4, 0.0)
    assert abs(p0.sum() - 1) < 1e-9 and abs(noisy.sum() - 1) < 1e-9
    assert tv_distance(noisy, p0) > 0.0 and tv_distance(drift, p0) > 0.0


def test_hoeffding_radius_shrinks_with_shots_and_grows_with_outcomes():
    assert hoeffding_radius(4000, 8, 0.01) < hoeffding_radius(1000, 8, 0.01)
    assert hoeffding_radius(1000, 16, 0.01) > hoeffding_radius(1000, 8, 0.01)


def test_spending_schedules_respect_total_level():
    assert spending_schedule("uniform", 40, 0.05).sum() <= 0.05 + 1e-12
    assert spending_schedule("polynomial", 400, 0.05).sum() < 0.05
    assert spending_schedule("naive", 40, 0.05).sum() > 0.05


def test_sequential_decides_clear_cases_quickly_and_correctly():
    rng = np.random.default_rng(0)
    p0 = np.array([0.5, 0.0, 0.0, 0.5])
    bad = np.array([0.25, 0.25, 0.25, 0.25])
    ok = sequential(sample_cumulative(p0, 50, 40, 500, rng), p0, 0.1, 500)
    bug = sequential(sample_cumulative(bad, 50, 40, 500, rng), p0, 0.1, 500)
    assert not ok.buggy.any() and ok.decided.all()
    assert bug.buggy.all() and bug.decided.all()
    assert bug.shots.max() <= 2000


def test_sequential_never_commits_wrongly_at_the_boundary():
    rng = np.random.default_rng(1)
    p0 = np.array([0.4, 0.3, 0.2, 0.1])
    p = np.array([0.4, 0.3, 0.2, 0.1]) + np.array([0.09, -0.09, 0.0, 0.0])  # TV = 0.09 < tau
    out = sequential(sample_cumulative(p, 300, 40, 500, rng), p0, 0.1, 500)
    assert (out.decided & out.buggy).mean() <= 0.05


def test_baselines_run_and_chi2_rejects_small_exact_deviation():
    rng = np.random.default_rng(2)
    p0 = np.array([0.4, 0.3, 0.2, 0.1])
    p = np.array([0.42, 0.29, 0.19, 0.10])
    cum = sample_cumulative(p, 40, 40, 500, rng)
    assert chi2_fixed(cum, p0, 500).buggy.mean() > 0.9
    assert not tv_fixed(cum, p0, 0.1, 500).buggy.any()
    st = stability(cum, p0, 0.1, 500, delta=0.05)
    assert st.shots.min() >= 1000 and st.shots.max() <= 20000
