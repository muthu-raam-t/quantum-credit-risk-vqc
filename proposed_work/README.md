# Proposed work pipeline (timed)

The same pipeline as the base paper, with this project's additions, and a timer on every stage.

## What it does
| Stage | What runs | Change from base paper |
|---|---|---|
| 1-5 | Classical model, encoding, circuit, training, transpilation | Same |
| 6 | Automated calibration: Bayesian optimisation -> Bayesian optimisation -> SPSA -> verify, with readout mitigation | Add-on |
| 7 | Execution with readout-error mitigation | Add-on |
| 7b | Zero-noise extrapolation (noise x1, x3, x5) | Add-on |
| 8 | Post-processing: PD, expected loss, VaR | Same |
| 9 | Fidelity gate: >= 0.97 ACCEPT, otherwise RE-CALIBRATE | Add-on |
| Drift | Drift is detected automatically and calibration re-runs until ACCEPT | Add-on |

## How to run
Open `proposed_work.ipynb` with the `.venv` kernel and click Run All (about 25 s).
Set `USE_ZNE = False` in the second cell to skip zero-noise extrapolation.
It uses the shared code in `../src/`, so the folder must stay inside the project.

## Outputs (written to this folder)
- `timing.json` - start time, end time, seconds and circuit runs for every stage, plus the total
- `results.json` - fidelity, decision, PD, expected loss, VaR, calibration runs, drift recovery

## Comparison
After running both pipelines, run `../comparison.ipynb` for the side-by-side tables and charts.
