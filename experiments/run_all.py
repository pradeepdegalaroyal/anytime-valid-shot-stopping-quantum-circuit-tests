"""Reproduce every result and figure: ``python experiments/run_all.py`` (add ``--quick`` for a smoke run)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shotstop import experiments as ex  # noqa: E402
from shotstop import plots  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="tiny configuration for CI (under one minute)")
    args = ap.parse_args()
    cfg = ex.Config.quick() if args.quick else ex.Config()
    res = ROOT / ("results_quick" if args.quick else "results")
    fig = ROOT / ("figures_quick" if args.quick else "figures")
    res.mkdir(exist_ok=True)
    fig.mkdir(exist_ok=True)
    t0 = time.time()
    timings = {}

    def stage(name: str):
        print(f"[{time.time() - t0:6.1f}s] {name}", flush=True)
        timings[name] = time.time()

    stage("main benchmark and stability sweep")
    bench = ex.run_benchmark(cfg)
    for name, df in bench.items():
        df.to_csv(res / f"{name}.csv", index=False)
    table = ex.main_table(bench["instance_level"])
    table.to_csv(res / "main_table.csv", index=False)
    print(table.round(3).to_string())
    ex.band_table(bench["instance_level"], cfg.tau).to_csv(res / "band_table.csv", index=False)
    ex.shots_by_class(bench["instance_level"]).to_csv(res / "shots_by_class.csv", index=False)

    stage("ablation on boundary instances")
    ablation = ex.run_ablation(cfg)
    ablation.to_csv(res / "ablation.csv", index=False)
    ex.summarise(ablation, ["rel", "radius", "schedule"], ["decided", "decided_wrong", "forced_wrong", "mean_shots"]
                 ).to_csv(res / "ablation_summary.csv", index=False)

    stage("noise sweep")
    noise = ex.run_noise_sweep(cfg)
    noise.to_csv(res / "noise_sweep.csv", index=False)
    ex.summarise(noise, ["case", "method", "p"], ["tv", "buggy_rate", "abstain", "mean_shots"]
                 ).to_csv(res / "noise_summary.csv", index=False)

    stage("qubit scaling")
    scaling = ex.run_scaling(cfg)
    scaling.to_csv(res / "scaling.csv", index=False)
    ex.summarise(scaling, ["label", "method", "n"], ["mean_shots", "committed_wrong", "abstain", "wrong_rate"]
                 ).to_csv(res / "scaling_summary.csv", index=False)

    stage("figures")
    plots.dumbbell(bench["instance_level"], fig / "fig1_dumbbell_near_threshold.png", cfg.tau)
    plots.phase(bench["stability_sweep"], bench["instance_level"], fig / "fig2_phase_stability_vs_sequential.png", cfg.tau)
    plots.ecdf(bench["shot_samples"], fig / "fig3_ecdf_shots.png")
    plots.noise_sweep(noise, fig / "fig4_noise_sweep.png")
    plots.scaling(scaling, fig / "fig5_qubit_scaling.png")
    plots.ablation(ablation, fig / "fig6_ablation_validity.png", cfg.alpha)

    meta = {"quick": args.quick, "runtime_seconds": round(time.time() - t0, 1), "tau": cfg.tau, "alpha": cfg.alpha,
            "batch": cfg.batch, "steps": cfg.steps, "reps": cfg.reps, "seeds": cfg.seeds, "qubits": cfg.n,
            "n_instances": int(bench["instance_level"].id.nunique())}
    (res / "run_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"done in {meta['runtime_seconds']} s")


if __name__ == "__main__":
    main()
