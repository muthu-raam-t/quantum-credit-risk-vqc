"""
device.py
---------
``NoisyDevice`` bundles everything that stands in for "the chip" in Stages 6-9:
a transpiled, parameterized circuit + the Aer noise model + the hidden control
drift. Its public interface is deliberately experiment-shaped:

    probs = device.run(x, shots)      # commanded angles in -> measured distribution out
    p_ref = device.ideal_probs(x)     # noiseless, drift-free reference (the paper's
                                      # "simulated transpiled circuit", Fig. 10a)

and it counts how many circuit evaluations / shots every calibration method
spends, which is the cost axis of the Stage 6A-vs-6B comparison.
"""

import numpy as np
from qiskit_aer import AerSimulator
from qiskit.quantum_info import Statevector

from .config import SEED_SIMULATOR
from .metrics import counts_to_probs
from .noise_model import build_noise_model, ControlDrift
from .transpilation import (build_param_circuit, transpile_for_device, logical_to_physical,
                            parameter_names)


class NoisyDevice:
    def __init__(self, n, kind="gci", drift=None, noisy=True, seed=SEED_SIMULATOR,
                 initial_layout=None):
        self.n, self.kind = n, kind
        self.logical_qc, self.params = build_param_circuit(n, kind, measure=True)
        self.param_names = parameter_names(n, kind)
        self.tqc = transpile_for_device(self.logical_qc, n, initial_layout)
        self.n_bits = self.logical_qc.num_clbits
        self.n_physical = self.tqc.num_qubits
        self.phys = logical_to_physical(self.tqc, self.logical_qc.num_qubits)
        self.drift = drift if drift is not None else ControlDrift()
        self.noisy = noisy
        self.noise_model = build_noise_model(self.n_physical) if noisy else None
        self.sim = AerSimulator(noise_model=self.noise_model, seed_simulator=seed)
        self._seed = seed
        self._unitary_qc = self.logical_qc.remove_final_measurements(inplace=False)
        self.reset_counters()

    # ------------------------------------------------------------------ bookkeeping
    def reset_counters(self):
        self.n_evals = 0
        self.n_shots = 0

    # ------------------------------------------------------------------ circuits
    def bound_circuit(self, x):
        """Transpiled hardware circuit with the angles the chip would REALLY apply."""
        realised = self.drift.realise(x, self.n, self.kind, self.phys) if self.noisy else x
        return self.tqc.assign_parameters(dict(zip(self.params, realised)))

    # ------------------------------------------------------------------ execution
    def run_circuit(self, qc, shots, seed=None):
        self.n_evals += 1
        self.n_shots += shots
        s = seed if seed is not None else int(self._rng_seed())
        res = self.sim.run(qc, shots=shots, seed_simulator=s).result()
        return counts_to_probs(res.get_counts(), self.n_bits)

    def run(self, x, shots, seed=None):
        return self.run_circuit(self.bound_circuit(x), shots, seed)

    def run_many(self, xs, shots, seed=None):
        """Batch execution (one Aer call) -- used by grid sweeps."""
        circs = [self.bound_circuit(x) for x in xs]
        self.n_evals += len(circs)
        self.n_shots += shots * len(circs)
        s = seed if seed is not None else int(self._rng_seed())
        res = self.sim.run(circs, shots=shots, seed_simulator=s).result()
        return [counts_to_probs(res.get_counts(i), self.n_bits) for i in range(len(circs))]

    def ideal_probs(self, x):
        """Exact, noiseless, drift-free output distribution (statevector)."""
        qc = self._unitary_qc.assign_parameters(dict(zip(self.params, x)))
        return Statevector.from_instruction(qc).probabilities()

    def _rng_seed(self):
        self._seed = (self._seed * 1103515245 + 12345) % (2 ** 31)
        return self._seed

    # ------------------------------------------------------------------ info
    def summary(self):
        ops = dict(self.tqc.count_ops())
        return {"n_z_qubits": self.n, "kind": self.kind, "n_physical": self.n_physical,
                "logical_to_physical": self.phys, "transpiled_depth": self.tqc.depth(),
                "transpiled_gate_counts": ops, "noisy": self.noisy,
                "drift_per_logical_qubit": self.drift.describe(self.phys)}
