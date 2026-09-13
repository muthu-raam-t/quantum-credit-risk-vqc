"""
vqc_circuit.py
--------------
Builds the actual Qiskit circuits: the trainable Gaussian-loading ansatz
(z-register) and the full GCI circuit (ansatz + fixed asset-qubit encoder).

Matches Stage 3 (03_circuit_design.ipynb).
"""

from qiskit import QuantumCircuit
from qiskit.circuit import Parameter


def build_ansatz(n_z_qubits, entangler="star"):
    """The Gaussian-loading block only: Ry(theta_i) on each register qubit,
    then an entangler pattern. No asset qubit, no measurement.

    Parameters
    ----------
    entangler : {"star", "chain"}
        "star"  -- every CNOT is controlled by qubit 0 (matches the base paper's Fig. 1/3).
        "chain" -- CNOT(0,1), CNOT(1,2), ... a linear chain (see Stage 4's expressivity
                   comparison -- not used in the main pipeline, kept for reference).
    """
    qc = QuantumCircuit(n_z_qubits)
    thetas = [Parameter(f"theta_{i}") for i in range(n_z_qubits)]
    for i in range(n_z_qubits):
        qc.ry(thetas[i], i)

    if entangler == "star":
        for i in range(1, n_z_qubits):
            qc.cx(0, i)
    elif entangler == "chain":
        for i in range(n_z_qubits - 1):
            qc.cx(i, i + 1)
    else:
        raise ValueError(f"Unknown entangler pattern: {entangler}")

    return qc, thetas


def build_gci_circuit(n_z_qubits, alpha_tilde, beta_tilde,
                       entangler="star", add_measurement=True, add_barrier=True):
    """Full GCI circuit: the trainable ansatz (block 1) plus the fixed,
    analytically-derived asset-qubit encoder (block 2), using the n+1-gate
    binary-decomposition trick derived in Stage 2.

    Returns
    -------
    qc : QuantumCircuit
    thetas : list[Parameter]
        The trainable z-register rotation-angle parameters.
    """
    n_total = n_z_qubits + 1
    asset_qubit = n_z_qubits

    ansatz, thetas = build_ansatz(n_z_qubits, entangler=entangler)

    qc = QuantumCircuit(n_total, n_total, name=f"GCI_{n_z_qubits}q_register")
    qc.compose(ansatz, qubits=range(n_z_qubits), inplace=True)

    if add_barrier:
        qc.barrier()

    qc.ry(2 * beta_tilde, asset_qubit)
    for k in range(n_z_qubits):
        qc.cry(2 * alpha_tilde * (2 ** k), k, asset_qubit)

    if add_measurement:
        qc.measure(range(n_total), range(n_total))

    return qc, thetas
