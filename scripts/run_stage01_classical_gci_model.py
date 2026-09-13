"""
Stage 1 runner: Classical GCI Model.

Computes the classical Vasicek/GCI baseline (PD(z), discretized target
histograms, and two classical VaR benchmarks) and saves results/stage01_baseline.json
for later stages to consume. Mirrors 01_classical_gci_model.ipynb.

Usage:
    python scripts/run_stage01_classical_gci_model.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.gci_model import (
    pd_given_z, target_gaussian_histogram, discrete_grid_var, monte_carlo_var,
)

P0, RHO, LGD, Z_MAX = 0.25, 0.027, 1000, 3.0
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"p0 = {P0}, rho = {RHO}")
    print(f"PD(z=0) = {pd_given_z(0.0, P0, RHO):.4f}  (should be close to p0)\n")

    baseline = {"model_parameters": {"p0": P0, "rho": RHO, "lgd": LGD}, "z_grids": {}}

    for n_qubits in (2, 3):
        z_grid, p_target = target_gaussian_histogram(n_qubits, Z_MAX)
        baseline["z_grids"][f"{n_qubits}_qubit"] = {
            "z": z_grid.tolist(), "p_target": p_target.tolist(),
        }

        ul, pdf, cdf, var = discrete_grid_var(n_qubits, P0, RHO, LGD, Z_MAX)
        baseline.setdefault("method_A_discrete_grid_reference", {})[f"{n_qubits}_qubit"] = {
            "unique_losses": ul.tolist(), "pdf": pdf.tolist(),
            "cdf": cdf.tolist(), "var_95": float(var),
        }
        print(f"[{n_qubits}-qubit grid] Method A -- pdf={pdf}, VaR_95=${var}")

    ul, pdf, cdf, var = monte_carlo_var(P0, RHO, LGD)
    baseline["method_B_continuous_monte_carlo"] = {
        "unique_losses": ul.tolist(), "pdf": pdf.tolist(),
        "cdf": cdf.tolist(), "var_95": float(var),
    }
    print(f"\n[Continuous MC] Method B -- pdf={pdf}, VaR_95=${var}")

    out_path = os.path.join(RESULTS_DIR, "stage01_baseline.json")
    with open(out_path, "w") as f:
        json.dump(baseline, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
