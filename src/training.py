"""
training.py
------------
Orchestrates parameter_shift.py + adam.py + vqc_circuit.py to train the
Gaussian-loading ansatz against a target distribution.

This is the only module that "knows about" all three pieces at once -- it is
intentionally the thin glue layer, not where the algorithms themselves live.
Matches Stage 4 (04_classical_training.ipynb).
"""

import numpy as np
from qiskit.quantum_info import Statevector

from .vqc_circuit import build_ansatz
from .parameter_shift import gradient, mse_loss
from .adam import AdamOptimizer


def probabilities_from_theta(n_z_qubits, theta_values, entangler="star"):
    """Exact Born-rule probabilities of the ansatz-only circuit at a given theta."""
    qc, thetas = build_ansatz(n_z_qubits, entangler=entangler)
    bound = qc.assign_parameters(dict(zip(thetas, theta_values)))
    return Statevector.from_instruction(bound).probabilities()


def train_gaussian_loader(n_z_qubits, target, n_iterations=150, lr=0.15,
                           seed=0, entangler="star"):
    """Trains the n_z_qubits-register ansatz to match `target` via parameter-shift
    gradients + Adam.

    Returns
    -------
    theta : np.ndarray
        Final trained parameters.
    loss_history : list[float]
    final_p : np.ndarray
    final_loss : float
    """
    rng = np.random.default_rng(seed)
    theta = rng.uniform(0, np.pi, size=n_z_qubits)
    optimizer = AdamOptimizer(n_params=n_z_qubits, lr=lr)

    prob_fn = lambda th: probabilities_from_theta(n_z_qubits, th, entangler=entangler)

    loss_history = []
    for _ in range(n_iterations):
        grad, p_current = gradient(prob_fn, theta, target)
        loss_history.append(mse_loss(p_current, target))
        theta = optimizer.step(theta, grad)

    final_p = prob_fn(theta)
    final_loss = mse_loss(final_p, target)
    return theta, loss_history, final_p, final_loss
