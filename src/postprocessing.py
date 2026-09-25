"""
postprocessing.py
-----------------
Stage 8 -- turning measured bitstrings into a credit-loss distribution, exactly
as described in the base paper (Sec. IV-C, paragraph "Finally, to assess ..."):

  * each bitstring is split into two logical parts -- the LEFTMOST bit(s) are the
    default indicators (asset qubits), the RIGHTMOST n bits are the latent factor Z;
  * the Z bits are converted to an integer index b -> P(Z = z_b) is accumulated;
  * whenever a default bit is 1, the outcome contributes to the marginal default
    probability and the LGD is added to that scenario's loss;
  * identical loss values are merged into a discrete PDF, whose cumulative sum is
    the CDF; the 95% VaR is read off the CDF.

With Qiskit's little-endian convention the asset qubit (index n) is the leftmost
character of the bitstring and the z-register qubits are the rightmost n
characters -- the same layout the paper describes.
"""

import numpy as np

from .config import LGD, Z_MAX, CONFIDENCE, P0, RHO
from .gci_model import discretize_z, target_gaussian_histogram, pd_given_z


def decompose(probs, n, n_assets=1):
    """Split an outcome distribution over (n_assets + n) bits.

    Returns
    -------
    joint : np.ndarray, shape (2**n_assets, 2**n)   P(default pattern d, Z index b)
    """
    probs = np.asarray(probs, dtype=float)
    n_z = 2 ** n
    joint = np.zeros((2 ** n_assets, n_z))
    for idx, p in enumerate(probs):
        b = idx & (n_z - 1)          # rightmost n bits  -> latent factor index
        d = idx >> n                 # leftmost bits     -> default indicators
        joint[d, b] += p
    return joint


def credit_statistics(probs, n, lgd=LGD, n_assets=1, confidence=CONFIDENCE):
    """Everything Stage 8/9 need from one outcome distribution."""
    joint = decompose(probs, n, n_assets)
    p_z = joint.sum(axis=0)                       # marginal P(Z = z_b)
    n_defaults = np.array([bin(d).count("1") for d in range(2 ** n_assets)])
    p_default = float(joint[n_defaults > 0].sum())
    with np.errstate(invalid="ignore", divide="ignore"):
        cond_pd = np.where(p_z > 0, joint[1:].sum(axis=0) / p_z, np.nan)

    # scenario losses -> merged PDF -> CDF
    scenario_loss = np.repeat((n_defaults * lgd)[:, None], 2 ** n, axis=1).ravel()
    scenario_prob = joint.ravel()
    unique_losses = np.unique(scenario_loss)
    pdf = np.array([scenario_prob[scenario_loss == L].sum() for L in unique_losses])
    cdf = np.cumsum(pdf)
    var = value_at_risk(unique_losses, cdf, confidence)
    return {
        "z_marginal": p_z.tolist(),
        "p_default": p_default,
        "conditional_pd": cond_pd.tolist(),
        "unique_losses": unique_losses.tolist(),
        "pdf": pdf.tolist(),
        "cdf": cdf.tolist(),
        "expected_loss": float(np.sum(unique_losses * pdf)),
        "var": float(var),
        "cvar": float(conditional_var(unique_losses, pdf, var)),
        "p_loss_le_0": float(cdf[0]),
    }


def value_at_risk(unique_losses, cdf, confidence=CONFIDENCE):
    """Smallest loss L with P(Loss <= L) >= confidence (same rule as Stage 1)."""
    idx = int(np.searchsorted(np.asarray(cdf) - 1e-12, confidence))
    idx = min(idx, len(unique_losses) - 1)
    return float(unique_losses[idx])


def conditional_var(unique_losses, pdf, var):
    """Expected loss given loss >= VaR (CVaR / expected shortfall on the discrete PDF)."""
    L, p = np.asarray(unique_losses), np.asarray(pdf)
    mask = L >= var
    return float((L[mask] * p[mask]).sum() / p[mask].sum()) if p[mask].sum() > 0 else float(var)


# =============================================================================
# Classical references, expressed as the SAME (n+1)-bit outcome distribution
# =============================================================================
def classical_joint_probs(n, p0=P0, rho=RHO, z_max=Z_MAX, linearized=None):
    """Classical GCI/Vasicek joint distribution over (default bit, Z index), laid out
    as a 2^(n+1) outcome vector with the same bit convention as the circuit.

    linearized : None -> exact Vasicek PD(z_b)  (the Stage 1 "Method A" baseline)
                 (alpha_tilde, beta_tilde) -> sin^2(alpha_tilde*b + beta_tilde) (Stage 2 encoding)
    """
    z_grid, p_z = target_gaussian_histogram(n, z_max)
    b = np.arange(2 ** n)
    if linearized is None:
        pd = pd_given_z(z_grid, p0, rho)
    else:
        a_t, b_t = linearized
        pd = np.sin(a_t * b + b_t) ** 2
    out = np.zeros(2 ** (n + 1))
    out[: 2 ** n] = p_z * (1 - pd)
    out[2 ** n:] = p_z * pd
    return out


def z_grid(n):
    return discretize_z(n, Z_MAX)
