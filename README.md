# Quantum Circuit-Based Adaptation for Credit Risk Analysis

A from-scratch, stage-by-stage reproduction of a hardware-aware **Variational Quantum Circuit (VQC)** for loading a **Gaussian Conditional-Independence (GCI)** credit-risk uncertainty model — replicating Ahmad et al., *IEEE Transactions on Quantum Engineering*, 2026 ([DOI: 10.1109/TQE.2026.3691176](https://doi.org/10.1109/TQE.2026.3691176)) — on a noise-emulated Qiskit simulator, extended with an **automated closed-loop calibration** that replaces the paper's manual grid sweep.

*Team 16 — Quantum Computing & Algorithms (23AID302), School of Artificial Intelligence, Amrita Vishwa Vidyapeetham, Coimbatore. Faculty in charge: Snigdhatanu Acharya.*

## ▶ Quick start

```bash
pip install -r requirements.txt
python run_pipeline.py            # runs all stages 00 -> 09 (~4-6 min), saves every notebook with outputs
```
or open **`main.ipynb`** and run all cells — it executes the whole pipeline and shows the headline results.

```bash
python run_pipeline.py --from 6           # only stages 6-9 (after 1-5 have run once)
python run_pipeline.py --mode scripts     # headless: runs scripts/run_stageXX_*.py instead of notebooks
```

## Pipeline (9 stages — matches `images/architecture_flowchart.png`)

| # | Notebook | What happens |
|---|---|---|
| 0 | `00_overview.ipynb` | Problem statement, base-paper gaps, VQC / parameter-shift / Adam, novelty |
| 1 | `01_classical_gci_model.ipynb` | Vasicek/GCI baseline PD(z), discretised Gaussian targets, classical VaR |
| 2 | `02_quantum_encoding.ipynb` | PD(z) ≈ sin²(αz+β) → R<sub>y</sub> angles (α̃, β̃) |
| 3 | `03_circuit_design.ipynb` | z-register (R<sub>y</sub>+CNOT) + asset qubit (controlled-R<sub>y</sub>) |
| 4 | `04_classical_training.ipynb` | Train the loader with parameter-shift gradients + Adam |
| 5 | `05_transpilation.ipynb` | SABRE layout/routing to native `rz, sx, x, cz` on a linear coupling map |
| 6 | `06_hardware_retuning.ipynb` | Noisy device (depolarizing + readout + coherent drift). **6A** paper grid sweep vs **6B** automated BO → BO → SPSA calibration |
| 7 | `07_run_on_backend.ipynb` | 20 × 20 000-shot execution; readout-error mitigation and zero-noise extrapolation |
| 8 | `08_classical_postprocessing.ipynb` | Bitstrings → (default, z) → loss PDF → CDF (paper Fig. 10) |
| 9 | `09_var_fidelity_check.ipynb` | 95 % VaR, Hellinger fidelities, **ACCEPT / RE-CALIBRATE** loop incl. a drift event |

## Repository layout

```
main.ipynb              master notebook (runs everything, shows results)
run_pipeline.py         master script  (same, from the command line)
00_ ... 09_*.ipynb      one narrated notebook per stage
src/                    all reusable code
  gci_model.py            classical Vasicek/GCI model            (stage 1)
  quantum_encoding.py     sin^2 linearisation, alpha~/beta~      (stage 2)
  vqc_circuit.py          ansatz + full GCI circuit              (stage 3)
  parameter_shift.py, adam.py, training.py                       (stage 4)
  transpilation.py        SABRE transpilation, parameterised     (stage 5)
  noise_model.py          depolarizing + readout + control drift (stage 6)
  device.py               NoisyDevice: "the chip"                (stage 6/7)
  calibration.py          6A grid sweep, SPSA, Bayesian opt., 6B (stage 6)
  mitigation.py           readout mitigation, ZNE                (stage 7)
  postprocessing.py       bitstrings -> loss PDF/CDF/VaR         (stage 8)
  metrics.py              Hellinger fidelity / distance
  stages.py               the computational core of stages 6-9
  report.py               writes results/FINAL_REPORT.md
  config.py, pipeline_io.py
scripts/                headless runners, one per stage
results/                JSON outputs of stages 5-9, FINAL_REPORT.md, figures/
images/                 architecture diagram
```

## Headline results (see `results/FINAL_REPORT.md` for the full table)

- **Replication:** P(L ≤ 0) ≈ 0.75, P(L ≤ 1000) = 1, VaR<sub>95</sub> = $1000 (as in the paper's Fig. 10); the paper-style grid sweep moves the 2-qubit loader angle θ₁ to ≈234° (paper hardware: 224°–237°).
- **Novelty (Stage 6):** the automated 6B calibration reaches Hellinger fidelity ≈ 0.98 (2-qubit register) / ≈ 0.99 (3-qubit register) with 204 circuit runs, vs ≈ 0.94 / 0.96 for the paper's grid sweep with 347 / 477 runs.
- **Mitigation benchmark (Stage 7):** retuning fixes the coherent drift, readout mitigation the readout bias, ZNE part of the remaining gate noise.
- **Closed loop (Stage 9):** after a simulated drift event the fidelity drops to 0.5–0.7, the check fails, Stage 6B re-runs itself and the pipeline is accepted again.

> All results come from a simulator with an emulated noise model — no claim of physical QPU execution.

## Stack

Qiskit · Qiskit Aer · NumPy · SciPy · Matplotlib · Jupyter
