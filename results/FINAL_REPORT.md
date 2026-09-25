# Final Report — Quantum Circuit-Based Adaptation for Credit Risk Analysis

Replication (on a noise-emulated Qiskit simulator) of Ahmad et al., *IEEE Trans. Quantum Eng.* 7, 3103316 (2026), with an automated calibration loop replacing the paper's manual grid sweep.

Model: one asset, one latent factor, p0 = 0.25, rho = 0.027, LGD = $1000. Registers studied: 2-qubit, 3-qubit latent-factor register (+1 asset qubit).

## Stage 6 — calibration cost vs. quality (full GCI circuit)

| register | method | circuit runs | F_H vs noiseless reference |
|---|---|---|---|
| 2q | uncalibrated (Stage 4 angles) | 0 | 0.9225 |
| 2q | 6A grid sweep (base paper) | 347 | 0.9389 |
| 2q | **6B automated (this project)** | 204 | 0.9818 |
| 2q | ablation: joint SPSA | 308 | 0.9820 |
| 2q | ablation: joint BO | 70 | 0.9727 |
| 3q | uncalibrated (Stage 4 angles) | 0 | 0.9099 |
| 3q | 6A grid sweep (base paper) | 477 | 0.9570 |
| 3q | **6B automated (this project)** | 204 | 0.9943 |
| 3q | ablation: joint SPSA | 308 | 0.9469 |
| 3q | ablation: joint BO | 70 | 0.9637 |

## Stage 7/8/9 — execution (20 x 20,000 shots) and risk numbers

| register | variant | F_H vs ideal | F_H vs classical GCI | P(L<=0) | E[L] ($) | VaR95 ($) |
|---|---|---|---|---|---|---|
| 2q | ideal_noiseless | 1.0000 ± 0.0000 | 1.0000 | 0.7475 | 252.5 ± 0.0 | 1000 |
| 2q | noisy_uncalibrated | 0.8794 ± 0.0026 | 0.8802 | 0.8259 | 174.1 ± 3.1 | 1000 |
| 2q | uncalibrated_REM | 0.9218 ± 0.0027 | 0.9226 | 0.8347 | 165.3 ± 3.4 | 1000 |
| 2q | 6A_grid_REM | 0.9391 ± 0.0022 | 0.9394 | 0.7553 | 244.7 ± 2.8 | 1000 |
| 2q | 6B_auto_REM | 0.9819 ± 0.0016 | 0.9820 | 0.7271 | 272.9 ± 3.5 | 1000 |
| 2q | 6B_auto_REM_ZNE | 0.9983 ± 0.0007 | 0.9983 | 0.7419 | 258.1 ± 4.6 | 1000 |
| 2q | classical discrete-grid GCI | — | 1 | 0.7496 | 250.4 | 1000 |
| 3q | ideal_noiseless | 1.0000 ± 0.0000 | 0.7829 | 0.7456 | 254.4 ± 0.0 | 1000 |
| 3q | noisy_uncalibrated | 0.9189 ± 0.0018 | 0.7752 | 0.8093 | 190.7 ± 2.7 | 1000 |
| 3q | uncalibrated_REM | 0.9087 ± 0.0025 | 0.7473 | 0.8160 | 184.0 ± 2.9 | 1000 |
| 3q | 6A_grid_REM | 0.9564 ± 0.0015 | 0.7802 | 0.7375 | 262.5 ± 2.1 | 1000 |
| 3q | 6B_auto_REM | 0.9946 ± 0.0007 | 0.8149 | 0.7387 | 261.3 ± 3.6 | 1000 |
| 3q | 6B_auto_REM_ZNE | 0.9958 ± 0.0008 | 0.8000 | 0.7701 | 229.9 ± 4.2 | 1000 |
| 3q | classical discrete-grid GCI | — | 1 | 0.7500 | 250.0 | 1000 |

## Stage 9 — acceptance test (threshold F_H >= 0.97)

- **2-qubit register:** deployed pipeline (6B + readout mitigation) F_H = 0.9819 → **ACCEPT**.
  - drift event (new miscalibration): 0.528 (RE-CALIBRATE) → 0.972 (ACCEPT); 204 circuit runs of automatic re-calibration.
- **3-qubit register:** deployed pipeline (6B + readout mitigation) F_H = 0.9946 → **ACCEPT**.
  - drift event (new miscalibration): 0.676 (RE-CALIBRATE) → 0.992 (ACCEPT); 204 circuit runs of automatic re-calibration.

## Comparison with the base paper

- Paper (real Contralto-D chip, no mitigation): F_H = 98.9 ± 0.3 %, P(L<=0) ≈ 0.75, P(L<=1000) = 1, VaR95 = $1000.
- This project (noise-emulated simulator, 6B + readout mitigation): 2q F_H = 98.2 %, 3q F_H = 99.5 %; P(L<=0) = 0.727 (2q), 0.739 (3q); VaR95 = $1000 in every repetition.
- 2-qubit loader: the paper-style 6A sweep moves theta_1 from the trained 195° to 234°; the paper's hardware sweeps found 237° (D3–C4) and 224° (D3–A6).

*All numbers come from a simulator with an emulated noise model — no claim of physical QPU execution.*
