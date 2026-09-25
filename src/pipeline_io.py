"""
pipeline_io.py
--------------
Small helpers that let every stage find the outputs of the stages before it.

Stages 1-5 were written as stand-alone notebooks that save their artefacts in the
repository root (e.g. ``trained_parameters.json``), while the ``scripts/`` runners
save into ``results/`` with ``stageXX_`` names. The loaders below accept either,
and fall back to recomputing from ``src/`` if neither exists -- so any notebook
from Stage 6 onward can also be run on its own.
"""

import json
import os

import matplotlib.pyplot as plt

from .config import ROOT_DIR, RESULTS_DIR, FIG_DIR, P0, RHO, Z_MAX, REGISTER_SIZES


def _first_existing(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(obj, filename):
    """Save to results/<filename> and return the path."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, filename)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=_json_default)
    return path


def _json_default(o):
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Not JSON serialisable: {type(o)}")


def save_fig(fig, filename, dpi=150):
    """Save a matplotlib figure to results/figures/<filename>."""
    os.makedirs(FIG_DIR, exist_ok=True)
    path = os.path.join(FIG_DIR, filename)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path


def results_path(filename):
    return os.path.join(RESULTS_DIR, filename)


# --------------------------------------------------------------------------
# Upstream artefacts
# --------------------------------------------------------------------------
def load_encoding_params():
    """alpha_tilde / beta_tilde per register size (Stage 2)."""
    path = _first_existing([
        os.path.join(RESULTS_DIR, "quantum_encoding_params.json"),
        os.path.join(ROOT_DIR, "quantum_encoding_params.json"),
        os.path.join(RESULTS_DIR, "stage02_encoding_params.json"),
    ])
    if path is not None:
        return load_json(path)

    from .quantum_encoding import fit_linear_angle, register_adapted_params
    alpha, beta, max_err, mean_err = fit_linear_angle(P0, RHO, Z_MAX)
    enc = {"continuous_fit": {"alpha": alpha, "beta": beta, "z_max": Z_MAX,
                              "max_abs_error": max_err, "mean_abs_error": mean_err},
           "register_adapted": {}}
    for n in REGISTER_SIZES:
        a_t, b_t = register_adapted_params(n, alpha, beta, Z_MAX)
        enc["register_adapted"][f"{n}_qubit"] = {"alpha_tilde": a_t, "beta_tilde": b_t}
    return enc


def load_trained_params():
    """Trained z-register angles per register size (Stage 4)."""
    path = _first_existing([
        os.path.join(RESULTS_DIR, "trained_parameters.json"),
        os.path.join(ROOT_DIR, "trained_parameters.json"),
        os.path.join(RESULTS_DIR, "stage04_trained_parameters.json"),
    ])
    if path is not None:
        return load_json(path)

    print("Stage 4 output not found -- re-training the loaders (takes ~1 min).")
    from .gci_model import target_gaussian_histogram
    from .training import train_gaussian_loader
    out = {}
    for n in REGISTER_SIZES:
        _, target = target_gaussian_histogram(n, Z_MAX)
        theta, _, final_p, final_loss = train_gaussian_loader(n, target, n_iterations=150,
                                                              lr=0.15, seed=0)
        out[f"{n}_qubit"] = {"theta": theta.tolist(), "final_loss": final_loss,
                             "final_p": final_p.tolist(), "entangler_topology": "star"}
    return out


def nominal_parameters(n):
    """The noiseless, 'as-designed' commanded parameter vector for the full GCI circuit:
    [theta_0 .. theta_{n-1}, beta_tilde, alpha_tilde]  (Stages 2 + 4)."""
    enc = load_encoding_params()["register_adapted"][f"{n}_qubit"]
    theta = load_trained_params()[f"{n}_qubit"]["theta"]
    return list(theta) + [enc["beta_tilde"], enc["alpha_tilde"]]


def load_stage_output(filename):
    path = results_path(filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found -- run the previous stage first "
            f"(or `python run_pipeline.py`).")
    return load_json(path)


def close(fig):
    plt.close(fig)
