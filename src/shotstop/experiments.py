"""Experiment drivers. Each function returns pandas data frames that run_all.py writes to results/."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .circuits import FAMILIES, CircuitSpec, exact_distribution, make_spec
from .stats import tv_distance
from .verdicts import Outcome, chi2_fixed, sample_cumulative, sequential, stability, tv_fixed

METHODS = ("chi2", "tv_fixed", "stability", "sequential")
STAB_DELTAS = (0.003, 0.006, 0.01, 0.015, 0.02, 0.03, 0.045, 0.07)


@dataclass
class Config:
    """Shared settings. ``tau`` is the tolerated total variation distance to the ideal output."""

    tau: float = 0.10
    alpha: float = 0.05
    batch: int = 500
    steps: int = 40
    reps: int = 100
    stab_delta: float = 0.02
    patience: int = 2
    seeds: int = 5
    n: int = 4
    eps_grid: tuple = (0.0, 0.03, 0.06, 0.1, 0.15, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0, 1.2)
    p_grid: tuple = (0.0, 0.004, 0.01, 0.02, 0.03)
    families: tuple = FAMILIES
    boundary_reps: int = 400
    noise_grid: tuple = (0.0, 0.005, 0.01, 0.02, 0.03, 0.04)
    scaling_n: tuple = (3, 4, 5, 6)
    scaling_steps: int = 80
    extra: dict = field(default_factory=dict)

    @classmethod
    def quick(cls) -> "Config":
        return cls(reps=30, seeds=2, eps_grid=(0.0, 0.1, 0.3, 0.8), p_grid=(0.0, 0.01, 0.03),
                   boundary_reps=60, noise_grid=(0.0, 0.02, 0.04), scaling_n=(3, 4), scaling_steps=40)


def label_of(tv: float, tau: float) -> str:
    """Clear-correct (TV <= tau/2), clear-buggy (TV >= 1.5 tau) or near-threshold in between."""
    if tv <= 0.5 * tau:
        return "correct"
    if tv >= 1.5 * tau:
        return "buggy"
    return "near"


def run_methods(cum: np.ndarray, p0: np.ndarray, cfg: Config) -> dict[str, Outcome]:
    """Apply the four main procedures to the same simulated shot streams."""
    return {
        "chi2": chi2_fixed(cum, p0, cfg.batch, cfg.alpha),
        "tv_fixed": tv_fixed(cum, p0, cfg.tau, cfg.batch),
        "stability": stability(cum, p0, cfg.tau, cfg.batch, cfg.stab_delta, cfg.patience),
        "sequential": sequential(cum, p0, cfg.tau, cfg.batch, cfg.alpha),
    }


def build_instances(cfg: Config, n: int, eps_grid, p_grid) -> list[dict]:
    """Enumerate (family, seed, drift, noise) test cases with their exact distributions."""
    out = []
    for fam in cfg.families:
        for seed in range(cfg.seeds):
            spec = make_spec(fam, n, seed)
            p0 = exact_distribution(spec, 0.0, 0.0)
            for eps in eps_grid:
                for p in p_grid:
                    dist = exact_distribution(spec, float(eps), float(p))
                    out.append(dict(family=fam, seed=seed, n=n, eps=float(eps), p=float(p),
                                    tv=float(tv_distance(dist, p0)), p0=p0, dist=dist))
    return out


def score(name: str, out: Outcome, tv: float, tau: float) -> dict:
    """Summarise one procedure on one instance.

    ``wrong_rate`` counts every verdict, including the forced end-of-budget one. For the sequential
    test, ``committed_wrong`` counts only verdicts it stopped on, and ``abstain`` is the share of
    runs that ran out of budget without a certified verdict; other procedures always commit.
    """
    wrong = out.buggy != (tv > tau)
    sequential_test = name == "sequential"
    return dict(buggy_rate=float(out.buggy.mean()), wrong_rate=float(wrong.mean()),
                committed_wrong=float((out.decided & wrong).mean() if sequential_test else wrong.mean()),
                abstain=float(1.0 - out.decided.mean()) if sequential_test else 0.0,
                mean_shots=float(out.shots.mean()), decided=float(out.decided.mean()))


def run_benchmark(cfg: Config) -> dict[str, pd.DataFrame]:
    """Main benchmark: all methods on every instance, plus the stability-tolerance sweep."""
    insts = build_instances(cfg, cfg.n, cfg.eps_grid, cfg.p_grid)
    rows, sweep, shots = [], [], []
    for i, inst in enumerate(insts):
        rng = np.random.default_rng([2026, i])
        cum = sample_cumulative(inst["dist"], cfg.reps, cfg.steps, cfg.batch, rng)
        lab = label_of(inst["tv"], cfg.tau)
        base = {k: inst[k] for k in ("family", "seed", "n", "eps", "p", "tv")} | {"label": lab, "id": i}
        for name, out in run_methods(cum, inst["p0"], cfg).items():
            rows.append(base | dict(method=name) | score(name, out, inst["tv"], cfg.tau))
            if name in ("stability", "sequential"):
                for s in out.shots[:10]:
                    shots.append(dict(id=i, label=lab, method=name, shots=int(s)))
        for d in STAB_DELTAS:
            out = stability(cum, inst["p0"], cfg.tau, cfg.batch, d, cfg.patience)
            sc = score("stability", out, inst["tv"], cfg.tau)
            sweep.append(base | dict(delta=d, committed_wrong=sc["committed_wrong"], mean_shots=sc["mean_shots"]))
    return {"instance_level": pd.DataFrame(rows), "stability_sweep": pd.DataFrame(sweep),
            "shot_samples": pd.DataFrame(shots)}


def main_table(inst_level: pd.DataFrame) -> pd.DataFrame:
    """Per-method scores on clear and near-threshold instances; mean and std over circuit seeds."""
    recs = []
    for method, g in inst_level.groupby("method"):
        per_seed = []
        for seed, gs in g.groupby("seed"):
            c, b, nr = (gs[gs.label == k] for k in ("correct", "buggy", "near"))
            clear = gs[gs.label != "near"]
            per_seed.append(dict(false_fail=c.buggy_rate.mean(), missed_bug=1 - b.buggy_rate.mean(),
                                 clear_shots=clear.mean_shots.mean(), near_committed_wrong=nr.committed_wrong.mean(),
                                 near_forced_wrong=nr.wrong_rate.mean(), near_abstain=nr.abstain.mean(),
                                 near_shots=nr.mean_shots.mean()))
        ps = pd.DataFrame(per_seed)
        rec = {"method": method}
        for col in ps.columns:
            rec[col + "_mean"], rec[col + "_std"] = ps[col].mean(), ps[col].std(ddof=1)
        recs.append(rec)
    return pd.DataFrame(recs).set_index("method").loc[list(METHODS)].reset_index()


def eps_for_tv(spec: CircuitSpec, p: float, target: float) -> tuple[float, float] | None:
    """Bisect the drift that gives TV(p_noisy_mutant, p_ideal) = target; None if unreachable."""
    p0 = exact_distribution(spec, 0.0, 0.0)

    def tv_at(e: float) -> float:
        return float(tv_distance(exact_distribution(spec, e, p), p0))

    lo, hi = 0.0, 1.6
    if tv_at(lo) > target or tv_at(hi) < target:
        return None
    for _ in range(18):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if tv_at(mid) < target else (lo, mid)
    return hi, tv_at(hi)


ABLATION_VARIANTS = (("hoeffding", "uniform"), ("hoeffding", "polynomial"), ("hoeffding", "naive"),
                     ("wald", "naive"), ("wald", "uniform"))


def run_ablation(cfg: Config) -> pd.DataFrame:
    """Boundary instances (TV just on either side of tau): validity of each sequential variant."""
    rows, k = [], 0
    for rel in (0.90, 0.97, 1.03, 1.10):
        for fam in cfg.families:
            for seed in range(cfg.seeds):
                spec = make_spec(fam, cfg.n, seed)
                found = eps_for_tv(spec, 0.01, rel * cfg.tau)
                if found is None:
                    continue
                eps, tv = found
                p0 = exact_distribution(spec, 0.0, 0.0)
                dist = exact_distribution(spec, eps, 0.01)
                rng = np.random.default_rng([2027, k]); k += 1
                cum = sample_cumulative(dist, cfg.boundary_reps, cfg.steps, cfg.batch, rng)
                truth_buggy = tv > cfg.tau
                for radius, sched in ABLATION_VARIANTS:
                    out = sequential(cum, p0, cfg.tau, cfg.batch, cfg.alpha, sched, radius)
                    rows.append(dict(rel=rel, family=fam, seed=seed, tv=tv, radius=radius, schedule=sched,
                                     decided=float(out.decided.mean()),
                                     decided_wrong=float((out.decided & (out.buggy != truth_buggy)).mean()),
                                     forced_wrong=float((out.buggy != truth_buggy).mean()),
                                     mean_shots=float(out.shots.mean())))
    return pd.DataFrame(rows)


def run_noise_sweep(cfg: Config) -> pd.DataFrame:
    """Verdict rates versus depolarising strength for a correct circuit and for a bugged one."""
    rows, k = [], 0
    for fam in ("layered", "ghz"):
        for seed in range(cfg.seeds):
            spec = make_spec(fam, cfg.n, seed)
            p0 = exact_distribution(spec, 0.0, 0.0)
            found = eps_for_tv(spec, 0.0, 0.13)
            if found is None:
                continue
            for case, eps in (("correct circuit", 0.0), ("drift bug (TV 0.13 noise-free)", found[0])):
                for p in cfg.noise_grid:
                    dist = exact_distribution(spec, eps, p)
                    rng = np.random.default_rng([2028, k]); k += 1
                    cum = sample_cumulative(dist, cfg.reps * 2, cfg.steps, cfg.batch, rng)
                    for name, out in run_methods(cum, p0, cfg).items():
                        tv = float(tv_distance(dist, p0))
                        rows.append(dict(case=case, family=fam, seed=seed, p=p, method=name, tv=tv)
                                    | score(name, out, tv, cfg.tau))
    return pd.DataFrame(rows)


def run_scaling(cfg: Config) -> pd.DataFrame:
    """Shots-to-verdict and error of the sequential test and stability rule versus qubit count."""
    rows = []
    sub = Config(**{**cfg.__dict__, "steps": cfg.scaling_steps})
    for n in cfg.scaling_n:
        insts = build_instances(sub, n, (0.0, 0.1, 0.45, 1.2), (0.005, 0.02))
        for i, inst in enumerate(insts):
            lab = label_of(inst["tv"], cfg.tau)
            rng = np.random.default_rng([2029, n, i])
            cum = sample_cumulative(inst["dist"], cfg.reps, sub.steps, cfg.batch, rng)
            for name, out in run_methods(cum, inst["p0"], sub).items():
                rows.append(dict(n=n, family=inst["family"], seed=inst["seed"], label=lab, tv=inst["tv"],
                                 method=name) | score(name, out, inst["tv"], cfg.tau))
    return pd.DataFrame(rows)


def band_table(inst_level: pd.DataFrame, tau: float, width: float = 0.25) -> pd.DataFrame:
    """Scores on instances with TV within ``width`` x tau of the tolerance; mean and std over seeds."""
    band = inst_level[(inst_level.tv - tau).abs() <= width * tau]
    per_seed = band.groupby(["method", "seed"])[["committed_wrong", "abstain", "wrong_rate", "mean_shots"]].mean()
    out = per_seed.groupby("method").agg(["mean", "std"])
    out.columns = [f"{a}_{b}" for a, b in out.columns]
    out["n_instances"] = band[band.method == "sequential"].shape[0]
    return out.loc[list(METHODS)].reset_index()


def shots_by_class(inst_level: pd.DataFrame) -> pd.DataFrame:
    """Mean shots until the verdict per instance class and method; mean and std over seeds."""
    per_seed = inst_level.groupby(["label", "method", "seed"]).mean_shots.mean()
    out = per_seed.groupby(["label", "method"]).agg(["mean", "std"]).reset_index()
    return out.rename(columns={"mean": "shots_mean", "std": "shots_std"})


def summarise(df: pd.DataFrame, keys: list[str], cols: list[str]) -> pd.DataFrame:
    """Mean and std over circuit seeds of ``cols`` after averaging within a seed, grouped by ``keys``."""
    per_seed = df.groupby(keys + ["seed"])[cols].mean()
    out = per_seed.groupby(keys).agg(["mean", "std"])
    out.columns = [f"{a}_{b}" for a, b in out.columns]
    return out.reset_index()
