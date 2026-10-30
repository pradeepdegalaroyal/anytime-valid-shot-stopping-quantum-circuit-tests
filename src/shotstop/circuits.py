"""Small circuits under test, a drift-bug mutation, and exact noisy output distributions."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, depolarizing_error

FAMILIES = ("layered", "ghz", "qft")


@dataclass(frozen=True)
class CircuitSpec:
    """Hashable description of a circuit family member.

    Attributes:
        family: One of ``layered``, ``ghz`` or ``qft``.
        n: Number of qubits.
        angles: Rotation angles that parameterise the instance.
        depth: Number of rotation/entangler layers (``layered`` only).
    """

    family: str
    n: int
    angles: tuple[float, ...]
    depth: int = 3


def make_spec(family: str, n: int, seed: int, depth: int = 3) -> CircuitSpec:
    """Draw a reproducible random instance of a circuit family."""
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}")
    rng = np.random.default_rng(10_000 * (FAMILIES.index(family) + 1) + 97 * n + seed)
    count = n * depth if family == "layered" else n
    angles = rng.uniform(0.4, 1.3, size=count)
    return CircuitSpec(family, n, tuple(float(a) for a in angles), depth)


def build_circuit(spec: CircuitSpec, drift: float = 0.0) -> QuantumCircuit:
    """Build the circuit; ``drift`` is added to one rotation angle (the injected bug)."""
    n = spec.n
    angles = list(spec.angles)
    angles[(len(angles) // 2) % len(angles)] += drift
    qc = QuantumCircuit(n)
    if spec.family == "layered":
        for layer in range(spec.depth):
            for q in range(n):
                qc.ry(angles[layer * n + q], q)
            for q in range(n - 1):
                qc.cx(q, q + 1)
    elif spec.family == "ghz":
        qc.h(0)
        for q in range(n - 1):
            qc.cx(q, q + 1)
        for q in range(n):
            qc.ry(angles[q], q)
    else:  # qft on a product state, written with H and controlled-phase gates
        for q in range(n):
            qc.ry(angles[q], q)
        for j in range(n):
            qc.h(j)
            for k in range(j + 1, n):
                qc.cp(np.pi / 2 ** (k - j), k, j)
    return qc


def _noise_model(p: float) -> NoiseModel | None:
    if p <= 0:
        return None
    nm = NoiseModel(basis_gates=["ry", "h", "cx", "cp"])
    nm.add_all_qubit_quantum_error(depolarizing_error(p, 2), ["cx", "cp"])
    nm.add_all_qubit_quantum_error(depolarizing_error(p / 10.0, 1), ["ry", "h"])
    return nm


@lru_cache(maxsize=200_000)
def exact_distribution(spec: CircuitSpec, drift: float = 0.0, p: float = 0.0) -> np.ndarray:
    """Exact output distribution of the (mutated, noisy) circuit via density-matrix simulation.

    Two-qubit gates carry depolarising error ``p`` and one-qubit gates ``p / 10``.
    """
    qc = build_circuit(spec, drift)
    qc.save_probabilities()
    sim = AerSimulator(method="density_matrix", noise_model=_noise_model(p))
    probs = sim.run(qc, shots=1).result().data()["probabilities"]
    probs = np.clip(np.asarray(probs, dtype=float), 0.0, None)
    return probs / probs.sum()
