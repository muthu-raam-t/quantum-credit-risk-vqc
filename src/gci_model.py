"""
gci_model.py
------------
The classical Gaussian Conditional-Independence (GCI) / Vasicek credit-risk model.

This module has NO quantum code in it at all -- it is pure classical math,
matching Stage 1 (01_classical_gci_model.ipynb). Every other stage that needs
PD(z), the discretized target Gaussian, or a classical VaR benchmark imports
from here rather than redefining these functions.
"""

import numpy as np
from scipy.stats import norm


def pd_given_z(z, p0, rho):
    """Gaussian Conditional-Independence / Vasicek conditional default probability.

    PD(z) = Phi( (Phi^-1(p0) - sqrt(rho) * z) / sqrt(1 - rho) )

    Parameters
    ----------
    z : float or np.ndarray
        Latent systematic risk factor value(s).
    p0 : float
        Baseline (unconditional) default probability.
    rho : float
        Asset correlation to the systematic factor.
    """
    numerator = norm.ppf(p0) - np.sqrt(rho) * z
    denominator = np.sqrt(1 - rho)
    return norm.cdf(numerator / denominator)


def discretize_z(n_qubits, z_max=3.0):
    """Map the 2^n_qubits basis states to grid points in [-z_max, z_max].

    Returns
    -------
    z_grid : np.ndarray, shape (2**n_qubits,)
        The latent-factor value associated with each basis-state index b.
    """
    n_bins = 2 ** n_qubits
    b = np.arange(n_bins)
    return -z_max + (2 * z_max) * b / (n_bins - 1)


def target_gaussian_histogram(n_qubits, z_max=3.0):
    """The discretized standard-normal target histogram for an n-qubit z-register.

    Returns
    -------
    z_grid : np.ndarray
    p_target : np.ndarray
        Normalized probability mass at each grid point (sums to 1).
    """
    z_grid = discretize_z(n_qubits, z_max)
    raw = np.exp(-(z_grid ** 2) / 2)
    p_target = raw / raw.sum()
    return z_grid, p_target


def discrete_grid_var(n_qubits, p0, rho, lgd=1000, z_max=3.0, confidence=0.95):
    """Method A (paper-faithful): classical loss distribution & VaR, built directly
    from the same discretized z-grid the quantum register represents.
    """
    z_grid, p_z = target_gaussian_histogram(n_qubits, z_max)
    pd_z = pd_given_z(z_grid, p0, rho)

    p_no_default = np.sum(p_z * (1 - pd_z))
    p_default = np.sum(p_z * pd_z)

    unique_losses = np.array([0, lgd])
    pdf = np.array([p_no_default, p_default])
    cdf = np.cumsum(pdf)

    var_index = np.searchsorted(cdf, confidence)
    var = unique_losses[var_index]
    return unique_losses, pdf, cdf, var


def monte_carlo_var(p0, rho, lgd=1000, n_trials=2_000_000, confidence=0.95, seed=42):
    """Method B (added sanity check, not in the paper): continuous Monte Carlo VaR."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n_trials)
    pd_z = pd_given_z(z, p0, rho)

    u = rng.uniform(size=n_trials)
    defaulted = u < pd_z
    losses = np.where(defaulted, lgd, 0)

    unique_losses, counts = np.unique(losses, return_counts=True)
    pdf = counts / n_trials
    cdf = np.cumsum(pdf)

    var_index = np.searchsorted(cdf, confidence)
    var = unique_losses[var_index]
    return unique_losses, pdf, cdf, var
