# Quantum Circuit-Based Adaptation for Credit Risk Analysis

A from-scratch, stage-by-stage reproduction of a hardware-aware **Variational Quantum Circuit (VQC)** for loading a **Gaussian Conditional-Independence (GCI)** credit-risk uncertainty model — inspired by Ahmad et al., *IEEE Transactions on Quantum Engineering*, 2026 ([DOI: 10.1109/TQE.2026.3691176](https://doi.org/10.1109/TQE.2026.3691176)).

## What is this?

Banks estimate portfolio credit risk (Value at Risk, VaR) using Monte Carlo simulation over correlated default models. Quantum Amplitude Estimation (QAE) promises a quadratic speedup over this — but first requires an **uncertainty model loaded onto a quantum circuit**. This project builds, trains, and hardware-adapts exactly that circuit for a one-asset/one-risk-factor GCI model, and validates it against the classical baseline via Hellinger fidelity and VaR comparison.

📓 **Start here:** [`00_overview.ipynb`](./00_overview.ipynb) — full project introduction, problem statement, and algorithm map.

## Pipeline (9 stages)

1. Classical GCI model
2. Quantum encoding
3. Circuit design
4. Classical training (Adam + parameter-shift rule)
5. Transpilation (SABRE)
6. Hardware / noise-model retuning
7. Execution (simulator or QPU)
8. Classical post-processing
9. VaR & fidelity check

## Stack

Qiskit · NumPy · SciPy · Matplotlib · Jupyter

## Status

🚧 Rebuilding from scratch, stage by stage. See [`00_overview.ipynb`](./00_overview.ipynb) for details.
