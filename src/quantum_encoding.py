"""
quantum_encoding.py
--------------------
Turns the classical PD(z) formula into rotation-angle parameters for a quantum gate.

Matches Stage 2 (02_quantum_encoding.ipynb): the linear approximation
PD(z) ~= sin^2(alpha*z + beta), and its register-adapted version
(alpha_tilde, beta_tilde) for a discretized n-qubit z-register.
"""

import numpy as np

from .gci_model import pd_given_z, discretize_z


def fit_linear_angle(p0, rho, z_max=3.0, n_fit_points=400):
    """Least-squares fit of theta(z) = arcsin(sqrt(PD(z))) ~= alpha*z + beta.

    Returns
    -------
    alpha, beta : float
        Slope and offset of the linear fit.
    max_abs_error, mean_abs_error : float
        Approximation error of sin^2(alpha*z+beta) vs. the true PD(z),
        evaluated on a dense grid over [-z_max, z_max].
    """
    z_fit = np.linspace(-z_max, z_max, n_fit_points)
    theta_targets = np.arcsin(np.sqrt(pd_given_z(z_fit, p0, rho)))
    alpha, beta = np.polyfit(z_fit, theta_targets, 1)

    pd_true = pd_given_z(z_fit, p0, rho)
    pd_approx = np.sin(alpha * z_fit + beta) ** 2
    abs_error = np.abs(pd_approx - pd_true)

    return alpha, beta, float(abs_error.max()), float(abs_error.mean())


def register_adapted_params(n_qubits, alpha, beta, z_max=3.0):
    """Fold the register's discretization grid into alpha, beta -> alpha_tilde, beta_tilde
    (matches the base paper's Eq. 4): so that
        alpha * z(b) + beta  ==  alpha_tilde * b + beta_tilde
    for every basis-state index b.
    """
    n_bins = 2 ** n_qubits
    slope = (2 * z_max) / (n_bins - 1)
    alpha_tilde = alpha * slope
    beta_tilde = beta - alpha * z_max
    return alpha_tilde, beta_tilde
