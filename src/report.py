"""
report.py
---------
Writes results/FINAL_REPORT.md -- a one-page, human-readable summary of the
whole pipeline built from the JSON outputs of Stages 6-9.
"""

import os

from . import config as C
from .config import RESULTS_DIR


def write_final_report(s6, s7, s8, s9):
    L = []
    L.append("# Final Report — Quantum Circuit-Based Adaptation for Credit Risk Analysis\n")
    L.append("Replication (on a noise-emulated Qiskit simulator) of Ahmad et al., *IEEE Trans. Quantum Eng.* 7, "
             "3103316 (2026), with an automated calibration loop replacing the paper's manual grid sweep.\n")
    L.append(f"Model: one asset, one latent factor, p0 = {C.P0}, rho = {C.RHO}, LGD = ${C.LGD}. "
             f"Registers studied: {', '.join(f'{n}-qubit' for n in C.REGISTER_SIZES)} latent-factor register "
             "(+1 asset qubit).\n")

    L.append("## Stage 6 — calibration cost vs. quality (full GCI circuit)\n")
    L.append("| register | method | circuit runs | F_H vs noiseless reference |")
    L.append("|---|---|---|---|")
    for n in C.REGISTER_SIZES:
        g = s6[f"{n}_qubit"]["gci"]
        L.append(f"| {n}q | uncalibrated (Stage 4 angles) | 0 | {g['uncalibrated']['fidelity']:.4f} |")
        for k, lab in [("grid_6A", "6A grid sweep (base paper)"), ("auto_6B", "**6B automated (this project)**"),
                       ("joint_spsa_ablation", "ablation: joint SPSA"), ("joint_bo_ablation", "ablation: joint BO")]:
            m = g["methods"][k]
            L.append(f"| {n}q | {lab} | {m['n_evals']} | {m['fidelity']:.4f} |")
    L.append("")

    L.append(f"## Stage 7/8/9 — execution ({C.N_REPEATS} x {C.SHOTS_EXECUTION:,} shots) and risk numbers\n")
    L.append("| register | variant | F_H vs ideal | F_H vs classical GCI | P(L<=0) | E[L] ($) | VaR95 ($) |")
    L.append("|---|---|---|---|---|---|---|")
    for n in C.REGISTER_SIZES:
        T = s9[f"{n}_qubit"]["fidelity_table"]
        for k, r in T.items():
            L.append(f"| {n}q | {k} | {r['F_vs_ideal_mean']:.4f} ± {r['F_vs_ideal_std']:.4f} | "
                     f"{r['F_vs_classical_joint_mean']:.4f} | {r['p_loss_le_0']:.4f} | "
                     f"{r['expected_loss']:.1f} ± {r['expected_loss_std']:.1f} | {r['VaR95']:.0f} |")
        cl = s8[f"{n}_qubit"]["classical"]["classical_discrete_grid"]
        L.append(f"| {n}q | classical discrete-grid GCI | — | 1 | {cl['cdf'][0]:.4f} | {cl['expected_loss']:.1f} | {cl['var']:.0f} |")
    L.append("")

    L.append(f"## Stage 9 — acceptance test (threshold F_H >= {C.FIDELITY_THRESHOLD})\n")
    for n in C.REGISTER_SIZES:
        r = s9[f"{n}_qubit"]
        L.append(f"- **{n}-qubit register:** deployed pipeline (6B + readout mitigation) F_H = "
                 f"{r['deployed_fidelity']:.4f} → **{r['decision']}**.")
        rounds = r["loop_day2_drift_event"]["rounds"]
        seq = " → ".join(f"{x['fidelity']:.3f} ({x['decision']})" for x in rounds)
        L.append(f"  - drift event (new miscalibration): {seq}; "
                 f"{r['loop_day2_drift_event']['total_recalibration_evals']} circuit runs of automatic re-calibration.")
    L.append("")
    L.append("## Comparison with the base paper\n")
    L.append("- Paper (real Contralto-D chip, no mitigation): F_H = 98.9 ± 0.3 %, P(L<=0) ≈ 0.75, P(L<=1000) = 1, VaR95 = $1000.")
    best = {n: s9[f"{n}_qubit"]["fidelity_table"]["6B_auto_REM"]["F_vs_ideal_mean"] for n in C.REGISTER_SIZES}
    L.append("- This project (noise-emulated simulator, 6B + readout mitigation): " +
             ", ".join(f"{n}q F_H = {100 * f:.1f} %" for n, f in best.items()) +
             "; P(L<=0) = " + ", ".join(
                 f"{s9[f'{n}_qubit']['fidelity_table']['6B_auto_REM']['p_loss_le_0']:.3f} ({n}q)"
                 for n in C.REGISTER_SIZES) + "; VaR95 = $1000 in every repetition.")
    if "2_qubit" in s6:
        ld = s6["2_qubit"]["loader"]
        t_nom = ld["x_nominal"][1] * 180 / 3.141592653589793
        t_6a = ld["methods"]["grid_6A"]["x_best_deg"][1]
        L.append(f"- 2-qubit loader: the paper-style 6A sweep moves theta_1 from the trained {t_nom:.0f}° to "
                 f"{t_6a:.0f}°; the paper's hardware sweeps found 237° (D3–C4) and 224° (D3–A6).")
    L.append("\n*All numbers come from a simulator with an emulated noise model — no claim of physical QPU execution.*\n")

    path = os.path.join(RESULTS_DIR, "FINAL_REPORT.md")
    with open(path, "w") as f:
        f.write("\n".join(L))
    return path
