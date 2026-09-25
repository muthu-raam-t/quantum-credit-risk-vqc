"""
metrics.py
----------
Distances between probability distributions.

The base paper's headline metric is the *Hellinger fidelity* [37] between the
hardware distribution and the simulated one (Sec. IV-C, F_H = 98.9%). We use the
same definition as ``qiskit.quantum_info.hellinger_fidelity``:

    BC(p, q)  = sum_i sqrt(p_i * q_i)          (Bhattacharyya coefficient)
    H(p, q)   = sqrt(1 - BC)                   (Hellinger distance, in [0, 1])
    F_H(p, q) = (1 - H^2)^2 = BC^2             (Hellinger fidelity, in [0, 1])
"""

import numpy as np


def _clean(p):
    p = np.clip(np.asarray(p, dtype=float), 0.0, None)
    s = p.sum()
    return p / s if s > 0 else p


def bhattacharyya(p, q):
    return float(np.sum(np.sqrt(_clean(p) * _clean(q))))


def hellinger_distance(p, q):
    return float(np.sqrt(max(0.0, 1.0 - bhattacharyya(p, q))))


def hellinger_fidelity(p, q):
    return float(bhattacharyya(p, q) ** 2)


def total_variation(p, q):
    return float(0.5 * np.sum(np.abs(_clean(p) - _clean(q))))


def counts_to_probs(counts, n_bits):
    """Qiskit counts dict -> probability vector indexed by the integer value of the
    bitstring (Qiskit's little-endian convention: clbit j is bit j of the index)."""
    p = np.zeros(2 ** n_bits)
    total = 0
    for key, c in counts.items():
        idx = int(key.replace(" ", ""), 2)
        p[idx] += c
        total += c
    return p / total
