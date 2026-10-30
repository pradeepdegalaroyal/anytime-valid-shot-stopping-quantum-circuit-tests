"""Figures (200 dpi, viridis palette) built from the CSV files in results/."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LABELS = {"chi2": "chi-square assertion (fixed budget)", "tv_fixed": "TV threshold (fixed budget)",
          "stability": "stability stop (delta 0.02)", "sequential": "sequential, confidence-bound stop"}
_CMAP = plt.get_cmap("viridis")
COLORS = {"chi2": _CMAP(0.05), "tv_fixed": _CMAP(0.33), "stability": _CMAP(0.62), "sequential": _CMAP(0.85)}
DPI = 200


def _save(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)


def dumbbell(inst: pd.DataFrame, out: Path, tau: float) -> None:
    """Per-instance wrong-verdict probability: stability stop (open) versus sequential (filled)."""
    d = inst[(inst.tv > 0.5 * tau) & (inst.tv < 1.5 * tau)]
    wide = d.pivot_table(index="id", columns="method", values=["committed_wrong", "abstain"])
    tvs = d.drop_duplicates("id").set_index("id").tv
    wide = wide.join(tvs.rename(("tv", "")))
    wide = wide.sort_values(("tv", ""))
    pick = np.unique(np.linspace(0, len(wide) - 1, min(24, len(wide))).astype(int))
    wide = wide.iloc[pick]
    y = np.arange(len(wide))
    a = wide[("committed_wrong", "stability")].to_numpy()
    b = wide[("committed_wrong", "sequential")].to_numpy()
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    ax.hlines(y, b, a, color=_CMAP(0.5), lw=1.6, zorder=1)
    ax.scatter(a, y, s=46, facecolor="white", edgecolor=COLORS["stability"], lw=1.8, zorder=3, label="stability stop")
    ax.scatter(b, y, s=46, color=COLORS["sequential"], edgecolor="black", lw=0.6, zorder=3,
               label="sequential (committed verdicts only)")
    ax.set_yticks(y, [f"{t:.3f}" for t in wide[("tv", "")]])
    ax.axvline(0.05, color="grey", ls=":", lw=1)
    ax.set_xlabel("probability of a wrong committed verdict (100 runs per instance)")
    ax.set_ylabel(f"true total variation distance to the ideal output (tolerance {tau})")
    ax.set_title("Near-threshold instances: wrong verdicts, stability vs sequential stop")
    ax.legend(loc="lower right", fontsize=8)
    _save(fig, out)


def phase(sweep: pd.DataFrame, inst: pd.DataFrame, out: Path, tau: float) -> None:
    """Filled contours over (true TV, stability tolerance): where the sequential test is better."""
    edges = np.array([0, 0.02, 0.04, 0.06, 0.075, 0.09, 0.11, 0.125, 0.14, 0.16, 0.2, 0.3, 1.0])
    seq = inst[inst.method == "sequential"].set_index("id")[["committed_wrong", "mean_shots"]]
    s = sweep.join(seq, on="id", rsuffix="_seq")
    s["bin"] = pd.cut(s.tv, edges, labels=False)
    s["d_wrong"] = s.committed_wrong - s.committed_wrong_seq
    s["log_ratio"] = np.log10(s.mean_shots / s.mean_shots_seq)
    deltas = np.sort(s.delta.unique())
    centers = 0.5 * (edges[:-1] + edges[1:])
    keep = [b for b in range(len(centers)) if centers[b] < 0.3]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, col, title, lev, lab in (
        (axes[0], "d_wrong", "(a) extra wrong verdicts of the stability stop", np.linspace(-0.05, 0.3, 15),
         "wrong-verdict probability, stability minus sequential"),
        (axes[1], "log_ratio", "(b) shots used, stability relative to sequential", np.linspace(-0.8, 1.2, 15),
         "log10 of shots(stability) / shots(sequential)")):
        grid = s.groupby(["delta", "bin"])[col].mean().unstack().reindex(index=deltas, columns=keep)
        cs = ax.contourf(centers[keep], deltas, grid.to_numpy(), levels=lev, cmap="viridis", extend="both")
        ax.contour(centers[keep], deltas, grid.to_numpy(), levels=[0.0], colors="white", linewidths=1.8)
        ax.axvline(tau, color="black", ls="--", lw=1)
        ax.set_yscale("log")
        ax.set_xlabel("true total variation distance to the ideal output")
        ax.set_ylabel("stability tolerance delta (total variation per batch)")
        ax.set_title(title, fontsize=10)
        fig.colorbar(cs, ax=ax, label=lab)
    _save(fig, out)


def ecdf(samples: pd.DataFrame, out: Path) -> None:
    """Empirical CDF of shots used until the verdict, per instance class."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    for ax, (lab, title) in zip(axes, (("correct", "clear-correct (TV at most 0.05)"),
                                        ("near", "near-threshold (0.05 to 0.15)"),
                                        ("buggy", "clear-buggy (TV at least 0.15)"))):
        for m in ("stability", "sequential"):
            x = np.sort(samples[(samples.label == lab) & (samples.method == m)].shots.to_numpy())
            ax.step(x, np.arange(1, len(x) + 1) / len(x), where="post", color=COLORS[m], lw=2, label=LABELS[m])
        ax.set_xscale("log")
        ax.set_xticks([500, 1000, 2000, 5000, 10000, 20000], ["500", "1k", "2k", "5k", "10k", "20k"])
        ax.minorticks_off()
        ax.set_xlabel("shots used before the verdict")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("fraction of test runs finished")
    axes[0].legend(fontsize=8, loc="lower right")
    _save(fig, out)


def noise_sweep(df: pd.DataFrame, out: Path) -> None:
    """Share of runs declared buggy versus depolarising strength (mean and std over seeds)."""
    cases = list(df.case.unique())
    fig, axes = plt.subplots(1, len(cases), figsize=(11, 4), sharey=True)
    for ax, case in zip(np.atleast_1d(axes), cases):
        for m in ("chi2", "tv_fixed", "stability", "sequential"):
            g = df[(df.case == case) & (df.method == m)].groupby(["seed", "p"]).buggy_rate.mean().unstack(0)
            ax.errorbar(g.index, g.mean(axis=1), yerr=g.std(axis=1, ddof=1), color=COLORS[m], marker="o", ms=4,
                        capsize=3, label=LABELS[m])
        tv = df[(df.case == case) & (df.method == "sequential")].groupby("p").tv.mean()
        ax.set_xlabel("two-qubit depolarising probability per gate")
        ax.set_title(case + f"; mean TV from {tv.iloc[0]:.2f} to {tv.iloc[-1]:.2f}", fontsize=10)
        ax.grid(alpha=0.25)
    np.atleast_1d(axes)[0].set_ylabel("share of runs declared buggy")
    np.atleast_1d(axes)[0].legend(fontsize=7.5, loc="center left")
    _save(fig, out)


def scaling(df: pd.DataFrame, out: Path) -> None:
    """Mean shots to verdict (log scale) versus qubit count for clear instances and the abstain share."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for m in ("stability", "sequential"):
        for lab, ls in (("correct", "-"), ("buggy", "--")):
            g = df[(df.method == m) & (df.label == lab)].groupby(["seed", "n"]).mean_shots.mean().unstack(0)
            axes[0].errorbar(g.index, g.mean(axis=1), yerr=g.std(axis=1, ddof=1), color=COLORS[m], ls=ls,
                             marker="o", capsize=3, label=f"{m}, {lab} circuits")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("number of qubits")
    axes[0].set_ylabel("mean shots until the verdict")
    axes[0].legend(fontsize=7.5)
    axes[0].grid(alpha=0.25)
    near = df[df.label == "near"]
    for m, col, mk in (("sequential", "abstain", "s"), ("sequential", "committed_wrong", "^"),
                       ("stability", "committed_wrong", "^")):
        g = near[near.method == m].groupby(["seed", "n"])[col].mean().unstack(0)
        name = "abstain share" if col == "abstain" else "wrong committed verdicts"
        axes[1].errorbar(g.index, g.mean(axis=1), yerr=g.std(axis=1, ddof=1), color=COLORS[m] if col != "abstain"
                         else _CMAP(0.45), marker=mk, capsize=3, ls=":" if col == "abstain" else "-",
                         label=f"{m}: {name}")
    axes[1].set_xlabel("number of qubits")
    axes[1].set_ylabel("share of runs")
    axes[1].set_title("near-threshold circuits (TV 0.05 to 0.15)", fontsize=10)
    axes[1].legend(fontsize=7.5)
    axes[1].grid(alpha=0.25)
    _save(fig, out)


def ablation(df: pd.DataFrame, out: Path, alpha: float) -> None:
    """Stopped-and-wrong share per confidence-bound variant at the boundary instances."""
    df = df.assign(variant=df.radius + " / " + df.schedule)
    order = list(dict.fromkeys(df.variant))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    rels = sorted(df.rel.unique())
    w = 0.8 / len(rels)
    for k, rel in enumerate(rels):
        g = df[df.rel == rel].groupby(["variant", "seed"]).decided_wrong.mean().unstack(1).loc[order]
        h = df[df.rel == rel].groupby(["variant", "seed"]).decided.mean().unstack(1).loc[order]
        x = np.arange(len(order)) + k * w
        axes[0].bar(x, g.mean(axis=1), w, yerr=g.std(axis=1, ddof=1), color=_CMAP(0.1 + 0.25 * k), capsize=2,
                    label=f"TV = {rel:.2f} x tolerance")
        axes[1].bar(x, h.mean(axis=1), w, yerr=h.std(axis=1, ddof=1), color=_CMAP(0.1 + 0.25 * k), capsize=2)
    axes[0].axhline(alpha, color="black", ls="--", lw=1)
    for ax, yl in ((axes[0], "share of runs that stopped on a wrong verdict"),
                   (axes[1], "share of runs that reached a certified verdict")):
        ax.set_xticks(np.arange(len(order)) + 0.4 - w / 2, order, rotation=20, fontsize=8)
        ax.set_ylabel(yl)
        ax.set_xlabel("confidence radius / error-spending schedule")
    axes[0].legend(fontsize=7.5)
    axes[0].set_title("validity (dashed line: target level)", fontsize=10)
    axes[1].set_title("power (certified verdicts within the budget)", fontsize=10)
    _save(fig, out)
