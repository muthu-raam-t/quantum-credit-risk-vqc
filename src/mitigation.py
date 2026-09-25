"""
mitigation.py
-------------
Two standard error-mitigation techniques, benchmarked in Stage 7 on top of the
retuned circuits (the base paper applies neither -- Sec. VI lists readout
mitigation as future work, Sec. V discusses ZNE as an alternative):

1. Readout-error mitigation (REM) -- "matrix inversion" / assignment-matrix method.
   Prepare every computational basis state |s>, measure, and build
       A[i, s] = P(read i | prepared s).
   A measured distribution m satisfies m ~= A p_true, so p_true is recovered by
   solving the non-negative least-squares problem  min ||A p - m||, p >= 0,
   then renormalising. (NNLS instead of a plain inverse keeps p a valid distribution.)

2. Zero-Noise Extrapolation (ZNE) -- global unitary folding.
   U  ->  U (U^dag U)^k  implements the same logical operation but multiplies the
   number of noisy gates by the scale factor lambda = 2k + 1. Measuring at
   lambda = 1, 3, 5 and fitting each probability linearly in lambda, the value at
   lambda = 0 estimates the zero-noise result (Richardson / linear extrapolation).
   Folding is done on the already-transpiled hardware circuit, so the folded
   circuits use exactly the same physical qubits and couplings.
"""

import itertools

import numpy as np
from qiskit import QuantumCircuit, transpile
from scipy.optimize import nnls

from .config import NATIVE_GATES


# =============================================================================
# helpers: split a transpiled circuit into its unitary part and its measurements
# =============================================================================
def split_measurements(qc):
    body = QuantumCircuit(*qc.qregs, *qc.cregs)
    meas = []
    for inst in qc.data:
        if inst.operation.name == "measure":
            meas.append((qc.find_bit(inst.qubits[0]).index, qc.find_bit(inst.clbits[0]).index))
        else:
            body.append(inst.operation, inst.qubits, inst.clbits)
    return body, meas


# =============================================================================
# Readout-error mitigation
# =============================================================================
def assignment_matrix(device, shots=20000, seed=77):
    """Calibrate A on the SAME physical qubits the device's circuit is measured on."""
    body, meas = split_measurements(device.tqc)
    n_bits = device.n_bits
    circs = []
    for s in range(2 ** n_bits):
        qc = QuantumCircuit(device.n_physical, n_bits)
        for q_phys, c in meas:
            if (s >> c) & 1:
                qc.x(q_phys)
        for q_phys, c in meas:
            qc.measure(q_phys, c)
        circs.append(transpile(qc, basis_gates=NATIVE_GATES, optimization_level=0))
    from .metrics import counts_to_probs
    res = device.sim.run(circs, shots=shots, seed_simulator=seed).result()
    A = np.column_stack([counts_to_probs(res.get_counts(i), n_bits) for i in range(len(circs))])
    return A


def apply_readout_mitigation(p_measured, A):
    p, _ = nnls(A, np.asarray(p_measured, dtype=float))
    s = p.sum()
    return p / s if s > 0 else p


# =============================================================================
# Zero-noise extrapolation
# =============================================================================
def fold_circuit(bound_tqc, scale):
    """Global folding U -> U (U^dag U)^k with scale = 2k+1, re-expressed in the native
    gate set WITHOUT any optimisation (optimisation would cancel U^dag U)."""
    if scale % 2 != 1:
        raise ValueError("scale factors must be odd integers (1, 3, 5, ...)")
    body, meas = split_measurements(bound_tqc)
    body_nb = QuantumCircuit(*body.qregs, *body.cregs)
    for inst in body.data:
        if inst.operation.name != "barrier":
            body_nb.append(inst.operation, inst.qubits, inst.clbits)
    folded = body_nb.copy()
    inv = body_nb.inverse()
    for _ in range((scale - 1) // 2):
        folded.barrier()
        folded.compose(inv, inplace=True)
        folded.barrier()
        folded.compose(body_nb, inplace=True)
    for q, c in meas:
        folded.measure(q, c)
    return transpile(folded, basis_gates=NATIVE_GATES, optimization_level=0)


def zne_extrapolate(scales, prob_list, order=1):
    """Fit each outcome probability as a polynomial in the scale factor and evaluate at 0."""
    scales = np.asarray(scales, dtype=float)
    P = np.asarray(prob_list, dtype=float)            # shape (n_scales, n_outcomes)
    coeffs = np.polyfit(scales, P, order)             # (order+1, n_outcomes)
    p0 = coeffs[-1]
    p0 = np.clip(p0, 0, None)
    return p0 / p0.sum()


def run_zne(device, x, shots, scales=(1, 3, 5), seed=None, readout_A=None):
    """Execute folded circuits at every scale (optionally readout-mitigating each), extrapolate."""
    bound = device.bound_circuit(x)
    probs = []
    for i, lam in enumerate(scales):
        p = device.run_circuit(fold_circuit(bound, lam), shots,
                               seed=None if seed is None else seed + 101 * i)
        if readout_A is not None:
            p = apply_readout_mitigation(p, readout_A)
        probs.append(p)
    return zne_extrapolate(scales, probs), probs


class ReadoutMitigatedDevice:
    """Wraps a NoisyDevice so that every measured distribution is readout-mitigated
    before anyone sees it. Handing THIS object to a calibration routine gives
    'mitigation-aware calibration': the angles are tuned to fix only what readout
    mitigation cannot (coherent drift, gate noise), so the two corrections do not
    double-count the readout error."""

    def __init__(self, device, A):
        self.device, self.A = device, A

    def __getattr__(self, name):
        return getattr(self.device, name)

    def run(self, x, shots, seed=None):
        return apply_readout_mitigation(self.device.run(x, shots, seed), self.A)

    def run_many(self, xs, shots, seed=None):
        return [apply_readout_mitigation(p, self.A) for p in self.device.run_many(xs, shots, seed)]

    def reset_counters(self):
        self.device.reset_counters()

    @property
    def n_evals(self):
        return self.device.n_evals

    @n_evals.setter
    def n_evals(self, v):
        self.device.n_evals = v

    @property
    def n_shots(self):
        return self.device.n_shots

    @n_shots.setter
    def n_shots(self, v):
        self.device.n_shots = v
