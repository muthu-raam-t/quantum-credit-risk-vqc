"""
transpilation.py
----------------
Stage 5 as a reusable module (the notebook 05_transpilation.ipynb remains the
narrated version). Also provides *parameterized* versions of the transpiled
circuits, which Stage 6 needs: a retuning loop evaluates the same hardware
circuit thousands of times with different commanded angles, so we transpile
ONCE with symbolic Parameters and only re-bind numbers afterwards -- exactly
what an experimentalist does when they keep the pulse schedule fixed and only
change pulse amplitudes.

Parameter vector convention used everywhere from Stage 6 onward
-----------------------------------------------------------------
kind="loader":  x = [theta_0, ..., theta_{n-1}]
kind="gci"   :  x = [theta_0, ..., theta_{n-1}, beta_tilde, alpha_tilde]
(asset gates: Ry(2*beta_tilde) on the asset qubit, then CRy(2*alpha_tilde*2^k)
controlled by z-register qubit k -- identical to Stage 3.)
"""

from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Parameter
from qiskit.transpiler import CouplingMap

from .config import (NATIVE_GATES, SEED_TRANSPILER, OPTIMIZATION_LEVEL, COUPLING_EDGES)


def coupling_map(n):
    return CouplingMap(COUPLING_EDGES[n])


def parameter_names(n, kind):
    names = [f"theta_{i}" for i in range(n)]
    if kind == "gci":
        names += ["beta_tilde", "alpha_tilde"]
    return names


def build_param_circuit(n, kind="gci", measure=True):
    """Logical (pre-transpilation) circuit with symbolic parameters.

    Returns (qc, params) where params is ordered exactly like `parameter_names`.
    """
    names = parameter_names(n, kind)
    params = [Parameter(nm) for nm in names]
    n_total = n + 1 if kind == "gci" else n
    qc = QuantumCircuit(n_total, n_total, name=f"{kind}_{n}q")

    for i in range(n):
        qc.ry(params[i], i)
    for i in range(1, n):
        qc.cx(0, i)                      # star entangler (base paper Fig. 1/3)

    if kind == "gci":
        beta_t, alpha_t = params[n], params[n + 1]
        asset = n
        qc.barrier()
        qc.ry(2 * beta_t, asset)
        for k in range(n):
            qc.cry(2 * alpha_t * (2 ** k), k, asset)

    if measure:
        qc.measure(range(n_total), range(n_total))
    return qc, params


def transpile_for_device(qc, n, initial_layout=None):
    """Same settings as 05_transpilation.ipynb: native {rz, sx, x, cz} gate set,
    SABRE layout + routing on the mock linear coupling map, optimisation level 1.

    initial_layout : optional list (logical qubit -> physical qubit). Used to run the
    stand-alone Gaussian loader on EXACTLY the physical qubits that hold the
    z-register inside the full GCI circuit -- the base paper likewise calibrated its
    loader on the same qubits (D3, A6) it later used for the GCI circuit.
    """
    return transpile(qc, coupling_map=coupling_map(n), basis_gates=NATIVE_GATES,
                     initial_layout=initial_layout,
                     layout_method=None if initial_layout else "sabre", routing_method="sabre",
                     optimization_level=OPTIMIZATION_LEVEL,
                     seed_transpiler=SEED_TRANSPILER)


def logical_to_physical(tqc, n_logical):
    """Initial layout of a transpiled circuit as a list: logical qubit i -> physical qubit."""
    layout = tqc.layout.initial_index_layout(filter_ancillas=True)
    return [int(layout[i]) for i in range(n_logical)]


def build_bound_gci_circuit(n, x):
    """Numeric version of the full GCI circuit (what Stage 5 transpiles)."""
    qc, params = build_param_circuit(n, "gci")
    return qc.assign_parameters(dict(zip(params, x)))
