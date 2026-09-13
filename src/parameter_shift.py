"""
parameter_shift.py
-------------------
The parameter-shift rule for computing EXACT gradients of a parameterized quantum
circuit's Born-rule probabilities, with no backpropagation and no approximation.

This module is intentionally generic -- it has no knowledge of the GCI model,
the ansatz's specific gate structure, or credit risk at all. It operates purely
on a user-supplied `prob_fn(theta) -> np.ndarray of probabilities`, so it can be
reused for any Ry-rotation-based variational circuit, not just this project's.

Matches the math derived in 00_overview.ipynb SS3.2 and applied in
04_classical_training.ipynb.
"""

import numpy as np


def gradient(prob_fn, theta, target):
    """Full gradient of the MSE loss  L(theta) = sum_b (p_b(theta) - target_b)^2
    with respect to every component of theta, via the parameter-shift rule.

    Parameters
    ----------
    prob_fn : callable
        prob_fn(theta_vector) -> np.ndarray of Born-rule probabilities.
        Every parameter in `theta` must correspond to a gate of the form
        exp(-i*theta*P/2) with P a Pauli generator (e.g. Ry, Rx, Rz) for the
        shift rule to be exact.
    theta : np.ndarray, shape (n_params,)
    target : np.ndarray
        Target probability distribution, same shape as prob_fn's output.

    Returns
    -------
    grad : np.ndarray, shape (n_params,)
    p_current : np.ndarray
        Probabilities at the (unshifted) current theta -- returned alongside the
        gradient since computing it is already needed and callers usually want
        the current loss too.

    Cost: 2 * n_params circuit evaluations (plus 1 for p_current).
    """
    n_params = len(theta)
    p_current = prob_fn(theta)
    grad = np.zeros(n_params)

    for i in range(n_params):
        shifted_plus = theta.copy()
        shifted_plus[i] += np.pi / 2
        shifted_minus = theta.copy()
        shifted_minus[i] -= np.pi / 2

        p_plus = prob_fn(shifted_plus)
        p_minus = prob_fn(shifted_minus)
        dp_dtheta_i = (p_plus - p_minus) / 2

        grad[i] = np.sum(2 * (p_current - target) * dp_dtheta_i)

    return grad, p_current


def mse_loss(p, target):
    """Convenience: mean-squared-error style loss (sum of squared differences)."""
    return float(np.sum((p - target) ** 2))
