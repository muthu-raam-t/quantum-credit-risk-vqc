"""
Stage 2 runner: Quantum Encoding.

Fits alpha, beta (PD(z) ~= sin^2(alpha*z+beta)) and derives the register-adapted
alpha_tilde, beta_tilde for both the 2-qubit and 3-qubit z-registers.
Mirrors 02_quantum_encoding.ipynb.

Usage:
    python scripts/run_stage02_quantum_encoding.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.quantum_encoding import fit_linear_angle, register_adapted_params

P0, RHO, Z_MAX = 0.25, 0.027, 3.0
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    alpha, beta, max_err, mean_err = fit_linear_angle(P0, RHO, Z_MAX)
    print(f"alpha = {alpha:.6f}, beta = {beta:.6f}")
    print(f"max abs error = {max_err:.5f}, mean abs error = {mean_err:.5f}\n")

    encoding_params = {
        "continuous_fit": {"alpha": alpha, "beta": beta, "z_max": Z_MAX,
                            "max_abs_error": max_err, "mean_abs_error": mean_err},
        "register_adapted": {},
    }

    for n_qubits in (2, 3):
        a_tilde, b_tilde = register_adapted_params(n_qubits, alpha, beta, Z_MAX)
        encoding_params["register_adapted"][f"{n_qubits}_qubit"] = {
            "alpha_tilde": a_tilde, "beta_tilde": b_tilde,
        }
        print(f"[{n_qubits}-qubit register] alpha_tilde={a_tilde:.6f}  beta_tilde={b_tilde:.6f}")

    out_path = os.path.join(RESULTS_DIR, "stage02_encoding_params.json")
    with open(out_path, "w") as f:
        json.dump(encoding_params, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
