# Method

## Setting

A circuit under test has an ideal output distribution p0 over K = 2^n bitstrings (n qubits) and a true noisy output
distribution p. After m shots the test sees the empirical distribution p_hat. The oracle question is whether
TV(p, p0) <= tau, where total variation (TV) is half the L1 distance and tau = 0.10. Shots arrive in batches of 500, with a
budget of 40 batches (20,000 shots; 80 batches for the qubit-scaling study).

## Circuits and bugs

Three families, five random angle draws (seeds) each: `layered` (three layers of single-qubit Y-rotations (RY) and a chain of
controlled-NOT gates), `ghz` (Greenberger-Horne-Zeilinger preparation followed by RY rotations), and `qft` (quantum Fourier
transform of a product state). The injected bug is an angle drift added to one rotation (0 to 1.2 rad). Noise is
depolarising with probability p on every two-qubit gate and p/10 on every single-qubit gate, with p from 0 to 0.03 in the main
benchmark. Exact distributions come from the Qiskit Aer density-matrix simulator, so the true TV of every instance is known
and shots are drawn by multinomial sampling. The main benchmark has 900 instances at four qubits, each run 100 times.

## Procedures compared

| Name | Role | Rule |
|---|---|---|
| chi-square assertion | standard statistical oracle from the testing literature | spend the whole budget, reject exact equality with p0 at level 0.05 |
| TV threshold, fixed budget | classical baseline | spend the whole budget, declare buggy if TV(p_hat, p0) > tau |
| stability stop | IncrementalExecution-style baseline | stop when the last 2 batch-to-batch TV changes of the cumulative distribution are below delta (0.02); declare by the point estimate |
| sequential (proposed) | anytime-valid test | after each batch, build an interval TV_hat +- r_t; stop "buggy" if the lower end exceeds tau, "correct" if the upper end is below tau; otherwise continue; if the budget ends, abstain |

The radius uses a Hoeffding bound with a union bound over the 2^K outcome subsets, because TV(p_hat, p0) is the maximum
over subsets S of p_hat(S) - p0(S):

r_t = sqrt((K ln 2 + ln(2 / delta_t)) / (2 m_t)),

with error level delta_t = alpha / T split uniformly over the T planned looks (alpha = 0.05). With probability at least
1 - alpha, every interval contains the true TV simultaneously, so a stopped verdict is wrong with probability at most alpha.
Runs that reach the budget without a certified verdict are counted as abstentions; their forced point-estimate verdict is
reported separately as "forced wrong".

## Metrics

- Instances are labelled by true TV: clear-correct (TV <= 0.05), clear-buggy (TV >= 0.15), near-threshold (in between).
- False-fail rate (verdict "buggy" on clear-correct), missed-bug rate (verdict "correct" on clear-buggy).
- Wrong committed verdict rate on near-threshold instances (for the sequential test, only stopped verdicts), abstain share,
  and mean shots until the verdict.
- Every number is the mean over runs and instances within a circuit seed, then mean and standard deviation over five seeds.

## Ablation

On 14 boundary instances per margin (TV = 0.90, 0.97, 1.03, 1.10 times tau, found by bisection on the drift at p = 0.01,
400 runs each), five variants of the sequential test are compared: Hoeffding radius with uniform, polynomial
(alpha / (t (t + 1))) and naive (alpha at every look, i.e. repeated peeking) spending, and the asymptotic delta-method (Wald)
radius with naive and uniform spending. Outputs: share of runs that stopped on a wrong verdict (validity) and share that
reached a certified verdict (power).

## Robustness sweeps

- Noise: two-qubit depolarising probability 0 to 0.04 for a correct circuit and a bugged circuit (TV 0.13 noise-free), on
  the `layered` and `ghz` families, five seeds.
- Stability tolerance: delta from 0.003 to 0.07 across all 900 instances (phase diagram).
- Scale: 3 to 6 qubits, 80 batches, drift 0 to 1.2 rad, p = 0.005 and 0.02.

## Seeds and reproducibility

Five circuit seeds (angle draws); sampling streams are seeded per instance. `python experiments/run_all.py` rewrites
`results/` and `figures/`; `--quick` uses two seeds and tiny grids and writes to `results_quick/` and `figures_quick/`.
