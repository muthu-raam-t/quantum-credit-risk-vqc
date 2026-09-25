"""
Stage 5 runner: Transpilation.

Rebuilds the trained GCI circuits (Stage 4 angles + Stage 2 asset parameters),
transpiles them to the native {rz, sx, x, cz} gate set with SABRE layout/routing
on the mock linear coupling maps, and saves the circuits (QPY) and their metrics.
Mirrors 05_transpilation.ipynb.

Usage:
    python scripts/run_stage05_transpilation.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import qiskit.qpy as qpy
from qiskit import transpile

from src import config as C
from src.pipeline_io import nominal_parameters, save_json, results_path
from src.transpilation import build_bound_gci_circuit, transpile_for_device, coupling_map


def main():
    circuits, meta = [], {}
    for n in C.REGISTER_SIZES:
        qc = build_bound_gci_circuit(n, nominal_parameters(n))
        decomp = transpile(qc, basis_gates=C.NATIVE_GATES, optimization_level=C.OPTIMIZATION_LEVEL,
                           seed_transpiler=C.SEED_TRANSPILER)
        tqc = transpile_for_device(qc, n)
        circuits.append(tqc)
        meta[f"{n}_qubit"] = {
            "original_depth": qc.depth(), "original_gate_counts": dict(qc.count_ops()),
            "decomposition_only_depth": decomp.depth(),
            "decomposition_only_cz": decomp.count_ops().get("cz", 0),
            "transpiled_depth": tqc.depth(), "transpiled_gate_counts": dict(tqc.count_ops()),
            "extra_cz_from_routing": tqc.count_ops().get("cz", 0) - decomp.count_ops().get("cz", 0),
            "coupling_map_edges": [list(e) for e in coupling_map(n).get_edges()],
            "native_gates": C.NATIVE_GATES,
        }
        print(f"[{n}-qubit register] depth {qc.depth()} -> {tqc.depth()}, "
              f"CZ: {decomp.count_ops().get('cz', 0)} (decomposition) -> {tqc.count_ops().get('cz', 0)} (+SABRE routing)")

    os.makedirs(C.RESULTS_DIR, exist_ok=True)
    with open(results_path("stage05_transpiled_circuits.qpy"), "wb") as f:
        qpy.dump(circuits, f)
    print(f"Saved -> {save_json(meta, 'stage05_transpilation.json')}")


if __name__ == "__main__":
    main()
