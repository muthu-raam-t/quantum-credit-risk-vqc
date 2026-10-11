# Proposed work pipeline (timed)

The same pipeline as the base paper, with this project's additions, and a timer on every stage.

## What it does
| Stage | What runs | Change from base paper |
|---|---|---|
| 1-5 | Classical model, encoding, circuit, training, transpilation | Same |
| 6a | Readout-mitigation setup (assignment matrices) | Add-on |
| 6 | Automated calibration: Bayesian optimisation -> Bayesian optimisation -> SPSA -> verify | Add-on |
| 7 | Execution with readout-error mitigation | Add-on |
| 7b | Zero-noise extrapolation (noise x1, x3, x5; the x1 point reuses the Stage 7 runs; 5 repeats) | Add-on |
| 8 | Post-processing: PD, expected loss, VaR | Same |
| 9 | Fidelity gate: >= 0.97 ACCEPT, otherwise RE-CALIBRATE | Add-on |
| Drift | Drift is detected automatically and calibration re-runs until ACCEPT | Add-on |

## Shots (identical in both pipelines)
- every calibration circuit run: 4000 shots (readout setup in the proposed work uses the same 4000)
- every execution circuit run: 20000 shots, 20 repeats
- fidelity check after a drift: 20000 shots

## How to run
Open `proposed_work.ipynb` with the `.venv` kernel and click Run All (about 25 s).
Set `USE_ZNE = False` in the second cell to skip zero-noise extrapolation.
`ZNE_REPEATS = 5` sets how many times the ZNE step is repeated (each run uses 20000 shots).
`BATCH = True` sends independent circuits (Bayesian-optimisation start points, the SPSA +/- pair,
verification repeats, ZNE circuits) to the simulator in one call. The circuits, shots and
algorithm are unchanged; only the number of separate simulator calls goes down.
It uses the shared code in `../src/`, so the folder must stay inside the project.

## Outputs (written to this folder)
- `timing.json` - start time, end time, seconds and circuit runs for every stage, plus the total
- `results.json` - fidelity, decision, PD, expected loss, VaR, calibration runs, drift recovery

## Comparison
After running both pipelines, run `../comparison.ipynb` for the side-by-side tables and charts.
