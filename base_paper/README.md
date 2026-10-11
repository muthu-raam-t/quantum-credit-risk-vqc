# Base paper pipeline (timed)

Reproduces the method of the base paper (Ahmad et al., IEEE TQE 2026) on the emulated noisy chip, with a timer on every stage.

## What it does
| Stage | What runs |
|---|---|
| 1 | Classical GCI (Vasicek) model, p0 = 0.25, rho = 0.027, LGD = $1000 |
| 2 | Quantum encoding PD(z) ~ sin^2(alpha z + beta) |
| 3 | Circuit design (Ry + CNOT loader, Ry / CRy asset qubit) |
| 4 | Classical training (parameter shift + Adam) |
| 5 | Transpilation (SABRE) |
| 6 | Calibration: manual coarse-to-fine grid sweep with the paper's ranges and steps |
| 7 | Execution: raw counts, no readout mitigation (as stated in the paper) |
| 8 | Post-processing: PD, expected loss, VaR |
| 9 | Hellinger fidelity and VaR check (no accept / reject gate) |
| Drift | Chip drifts; the grid sweep is repeated by hand |

## How to run
Open `base_paper.ipynb` with the `.venv` kernel and click Run All (about 15 s).
It uses the shared code in `../src/`, so the folder must stay inside the project.

## Outputs (written to this folder)
- `timing.json` - start time, end time, seconds and circuit runs for every stage, plus the total
- `results.json` - fidelity, PD, expected loss, VaR, calibration runs, drift recovery
