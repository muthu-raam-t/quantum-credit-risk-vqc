"""
Stage 4 runner: Classical Training.

Trains the 2-qubit and 3-qubit Gaussian-loading ansatze against the Stage 1
target histograms, using src/training.py (parameter-shift + Adam).
Mirrors 04_classical_training.ipynb.

Usage:
    python scripts/run_stage04_classical_training.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.gci_model import target_gaussian_histogram
from src.training import train_gaussian_loader

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
Z_MAX = 3.0


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results = {}

    for n_qubits in (2, 3):
        _, target = target_gaussian_histogram(n_qubits, Z_MAX)
        theta, loss_history, final_p, final_loss = train_gaussian_loader(
            n_qubits, target, n_iterations=150, lr=0.15, seed=0, entangler="star"
        )
        print(f"=== {n_qubits}-qubit z-register (star topology) ===")
        print(f"  trained theta = {theta}")
        print(f"  final loss    = {final_loss:.8f}")
        print(f"  final p       = {final_p}")
        print(f"  target p      = {target}\n")

        results[f"{n_qubits}_qubit"] = {
            "theta": theta.tolist(), "final_loss": final_loss,
            "final_p": final_p.tolist(), "entangler_topology": "star",
        }

    out_path = os.path.join(RESULTS_DIR, "stage04_trained_parameters.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()
