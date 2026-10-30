# Research gap: when may a shot-based circuit test stop?

## State of the art

Quantum software engineering (QSE) has produced surveys of functional testing for quantum circuits, covering assertions,
mutation, metamorphic and differential testing (Andrews et al., 2026, digital object identifier (DOI) 10.1109/MDAT.2026.3698368),
and a mapping study whose dominant technique is statistics on repeated measurements (García de la Barrera et al., 2023,
DOI 10.1002/smr.2419). Two recent papers expose what such tests cost. Kim et al. (2027, DOI 10.1016/j.jss.2026.113106)
ran the Qiskit Terra test suite 10,000 times per release and found flaky tests whose failure probability has a median of
9e-4, so that "thousands to tens of thousands of executions" are needed to see them with confidence. Ishikawa and Saito
(2027, DOI 10.1016/j.infsof.2026.108361) treat shots as a purchasable resource and search for cost-reliability trade-offs
over services. On the formal side, Bocci et al. (2027, DOI 10.1016/j.jlamp.2026.101174) define IncrementalExecution: run a
fixed circuit in batches and halt once extra shots no longer change the cumulative output distribution. They prove
termination and eventual stabilisation, and they state that finite-time statistical certification would need
confidence-sequence or concentration machinery that the framework does not supply.

The landmark papers fix the constraints. Leymann and Barzen (2020, DOI 10.1088/2058-9565/abae7d) argue that noise and
readout decide whether an implementation executes successfully, and Corcoles et al. (2020, DOI 10.1109/JPROC.2019.2954005)
describe benchmarking and error mitigation on noisy intermediate-scale quantum (NISQ) systems.

## Related work

| Paper | Year | Role | What it does | What it does NOT cover |
|---|---|---|---|---|
| Bocci et al., DOI 10.1016/j.jlamp.2026.101174 | 2027 | recent | Formal semantics of batch execution that stops when the output distribution is stable | An error guarantee for the stopped verdict; any noise or tolerance model |
| Kim et al., DOI 10.1016/j.jss.2026.113106 | 2027 | recent | Dynamic flakiness census of Qiskit Terra; Wilson intervals for rerun budgets | A stopping rule that controls the flaky-verdict rate |
| Ishikawa and Saito, DOI 10.1016/j.infsof.2026.108361 | 2027 | recent | Shot allocation across quantum services, cost versus reliability | Per-test early stopping; verdict error control |
| Andrews et al., DOI 10.1109/MDAT.2026.3698368 | 2026 | recent | Survey of functional testing and validation of quantum circuits | Quantitative shot budgets for the statistical oracles it lists |
| Zhang and Chen, DOI 10.1007/978-3-032-30693-7_17 | 2027 | recent | Semantics-first verification of a Shor oracle; shows a control-law violation that a trivial check missed | Statistical (shot-based) detection of such violations |
| Cipollini et al., DOI 10.1016/j.future.2026.108699 | 2026 | recent | Three ways to share a quantum processing unit (QPU) in high-performance computing (HPC) clusters | How many shots each hybrid job really needs |
| Leymann and Barzen, DOI 10.1088/2058-9565/abae7d | 2020 | landmark | Factors (depth, connectivity, readout) that decide NISQ executability | Test-oracle statistics |
| Corcoles et al., DOI 10.1109/JPROC.2019.2954005 | 2020 | landmark | Benchmarking, error mitigation and application outlook for near-term systems | Pass/fail decision rules for software tests |
| Quetschlich et al., DOI 10.22331/q-2023-07-20-1062 | 2023 | landmark | Cross-level benchmark suite of up to 130-qubit circuits | A protocol for deciding that a benchmark circuit executed correctly with few shots |
| Gill et al., DOI 10.1002/spe.3039 | 2022 | landmark | Taxonomy and open challenges for quantum computing, with decoherence as a main obstacle | Concrete testing procedures |
| García de la Barrera et al., DOI 10.1002/smr.2419 | 2023 | review | Mapping study; statistics on repeated measurements is a leading testing technique | Sequential designs; tolerance of hardware noise |
| Verma and Rahwani, DOI 10.1007/978-3-032-30963-1_32 | 2027 | adjacent | Simulation scaling on GPU and container clusters, up to 25 qubits | Statistical cost of validating simulated or real outputs |

## The gap

Recent work agrees that a quantum test is a random experiment that must be repeated, and it agrees that repetitions are
expensive (Kim et al.; Ishikawa and Saito). The only published early-stopping rule, stability-based halting (Bocci et al.),
has no stated error rate, and its authors say so. The standard shot-based oracle in the testing literature, a goodness-of-fit
assertion against the ideal distribution, tests exact equality and therefore rejects a correct circuit as soon as hardware
noise is non-zero and the shot count is large. Nobody has measured how often a stability rule commits a wrong verdict,
nor what a rule with a guarantee would cost, on circuits whose noise-free and noisy behaviour is known exactly.

**Hypotheses (falsifiable).** A circuit is correct when the total variation (TV) distance between its true noisy output
distribution and the ideal one is at most a tolerance tau = 0.10, and buggy otherwise. On four-qubit circuits, simulated with
exact density-matrix noise:

- H1: a stability-based stopping rule commits a wrong verdict on more than 5% of runs for circuits whose TV lies within
  25% of tau, while an anytime-valid sequential test (confidence interval for TV against tau, error level 0.05) commits fewer
  than 5%.
- H2: the sequential test reaches clear verdicts with fewer shots than the stability rule.
- H3: the chi-square assertion declares correct noisy circuits buggy in more than 50% of runs once the two-qubit depolarising
  probability reaches 0.005.

**Success metric.** The probability of a wrong committed verdict near tau, the share of runs that end without a certified
verdict (abstain), and shots used, each as mean and standard deviation over five circuit seeds.

**Novelty in one sentence.** This work turns the stability stopping rule of IncrementalExecution into a test with a
finite-sample error bound, and it measures, against exact noisy output distributions, where the stability rule fails and
what the guarantee costs in shots as qubits grow.

## Scale of the claim

All results are simulations (3-6 qubits, exact density matrices, multinomial shot sampling). No hardware was used, and no
quantum advantage is claimed or relevant.
