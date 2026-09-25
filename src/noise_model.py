"""
noise_model.py
--------------
The "noise-emulated backend" of Stages 6-7 (architecture box 7):

1. **Incoherent noise** -- a Qiskit Aer ``NoiseModel`` with depolarizing channels
   on every native gate and per-qubit readout bit-flip errors. This is the
   noise the base paper names explicitly (Sec. V: readout noise, depolarizing
   errors) and which mitigation techniques (Stage 7) target.

2. **Coherent control miscalibration ("drift")** -- the base paper's third
   error source (Sec. V: "phase-errors related to undershoot or overshoot of
   control pulses used to implement Ry rotations"), which it fixes by in-situ
   angle retuning. A real chip realises a commanded rotation theta as
   theta_real = (1 + eps_q) * theta + delta_q, with (eps_q, delta_q) different for
   every physical qubit q. We emulate this by distorting the commanded angles
   before they are bound into the transpiled circuit. The calibration
   algorithms never read eps/delta -- they only ever see measurement counts.
"""

import numpy as np
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

from .config import (DEPOL_1Q, DEPOL_2Q, READOUT_ERRORS, DRIFT_EPS, DRIFT_DELTA_DEG)


def build_noise_model(n_physical, depol_1q=DEPOL_1Q, depol_2q=DEPOL_2Q,
                      readout_errors=READOUT_ERRORS):
    nm = NoiseModel(basis_gates=["rz", "sx", "x", "cz"])
    nm.add_all_qubit_quantum_error(depolarizing_error(depol_1q, 1), ["sx", "x"])
    nm.add_all_qubit_quantum_error(depolarizing_error(depol_2q, 2), ["cz"])
    for q in range(n_physical):
        p01, p10 = readout_errors[q]
        nm.add_readout_error(ReadoutError([[1 - p01, p01], [p10, 1 - p10]]), [q])
    return nm


class ControlDrift:
    """Per-physical-qubit coherent rotation-angle miscalibration.

    Parameters
    ----------
    eps : list[float]         amplitude scale error per physical qubit
    delta_deg : list[float]   additive angle offset per physical qubit (degrees)
    """

    def __init__(self, eps=DRIFT_EPS, delta_deg=DRIFT_DELTA_DEG):
        self.eps = np.asarray(eps, dtype=float)
        self.delta = np.deg2rad(np.asarray(delta_deg, dtype=float))

    @classmethod
    def none(cls, n_physical=5):
        return cls([0.0] * n_physical, [0.0] * n_physical)

    def realise(self, x, n, kind, phys):
        """Map the COMMANDED parameter vector x to the angles the chip actually applies.

        phys : list  logical qubit -> physical qubit (initial SABRE layout)

        - theta_i drives an Ry on z-register qubit i            -> scale + offset
        - beta_tilde drives Ry(2*beta) on the asset qubit        -> scale + offset
          (offset applies to the full angle 2*beta, hence delta/2 on beta)
        - alpha_tilde drives controlled-Ry's on the asset qubit  -> scale only
          (a CRy is compiled as Ry(+a/2) CZ Ry(-a/2) CZ, so a constant offset cancels)
        """
        x = np.asarray(x, dtype=float).copy()
        for i in range(n):
            q = phys[i]
            x[i] = (1 + self.eps[q]) * x[i] + self.delta[q]
        if kind == "gci":
            qa = phys[n]
            x[n] = (1 + self.eps[qa]) * x[n] + self.delta[qa] / 2
            x[n + 1] = (1 + self.eps[qa]) * x[n + 1]
        return x

    def describe(self, phys):
        return [{"logical_qubit": i, "physical_qubit": int(q),
                 "eps": float(self.eps[q]), "delta_deg": float(np.rad2deg(self.delta[q]))}
                for i, q in enumerate(phys)]
