"""
app_core.py
-----------
The engine behind the interactive app (app.py). One function, `analyse()`, runs
the whole pipeline for ONE borrower chosen by the user:

    inputs  : p0 (average default probability), rho (correlation to the economy),
              LGD (loss given default), VaR confidence, register size, calibration
              method, mitigation switches, drift scenario
    output  : default probability per economy state, overall default probability,
              loss distribution (PDF/CDF), expected loss, VaR, CVaR, Hellinger
              fidelity, ACCEPT / RE-CALIBRATE decision -- quantum and classical side by side

It reuses the project's modules unchanged. The only new idea is that the asset-qubit
angles (alpha~, beta~) are recomputed from the user's p0 and rho. The trained
economy-register angles (Stage 4) do NOT depend on p0 or rho -- the economy is
always N(0, 1) -- so they are loaded from results/trained_parameters.json.
"""

import time

import numpy as np

from . import config as C
from .calibration import score, hierarchical_calibration
from .device import NoisyDevice
from .gci_model import pd_given_z, monte_carlo_var
from .metrics import hellinger_fidelity
from .mitigation import assignment_matrix, apply_readout_mitigation, run_zne, ReadoutMitigatedDevice
from .noise_model import ControlDrift
from .pipeline_io import load_trained_params
from .postprocessing import credit_statistics, classical_joint_probs, z_grid
from .quantum_encoding import fit_linear_angle, register_adapted_params
from .stages import make_device, paper_grid_loader, paper_grid_gci

CALIBRATION_METHODS = ("none", "6A grid sweep (base paper)", "6B automated (this project)")


def commanded_angles(n, p0, rho):
    """Stage 2 + Stage 4 for a user-chosen borrower: x = [theta*, beta~, alpha~]."""
    alpha, beta, max_err, mean_err = fit_linear_angle(p0, rho, C.Z_MAX)
    a_t, b_t = register_adapted_params(n, alpha, beta, C.Z_MAX)
    theta = load_trained_params()[f"{n}_qubit"]["theta"]
    x = np.array(list(theta) + [b_t, a_t])
    encoding = {"alpha_deg": float(np.rad2deg(alpha)), "beta_deg": float(np.rad2deg(beta)),
                "alpha_tilde_deg": float(np.rad2deg(a_t)), "beta_tilde_deg": float(np.rad2deg(b_t)),
                "fit_max_error": max_err, "fit_mean_error": mean_err}
    return x, encoding


def calibrate(method, n, dev, M, ref, x_nom, seed=0):
    """Stage 6: return (calibrated angles, circuit runs spent)."""
    if method == CALIBRATION_METHODS[0]:
        return x_nom.copy(), 0
    ldev, lx0, lref = make_device(n, "loader", drift=dev.drift)
    LM = ReadoutMitigatedDevice(ldev, assignment_matrix(ldev))
    if method == CALIBRATION_METHODS[1]:
        g1 = paper_grid_loader(n, LM, lref, lx0)
        x_start = x_nom.copy()
        x_start[:n] = g1.x_best
        g2 = paper_grid_gci(n, M, ref, x_start)
        return np.asarray(g2.x_best), g1.n_evals + g2.n_evals
    h = hierarchical_calibration(M, ref, x_nom, LM, lref, C.SHOTS_CALIBRATION, seed=seed)
    return np.asarray(h.x_best), h.n_evals


def execute(dev, A, x, shots, use_rem, use_zne, seed=500):
    """Stage 7: run the circuit, optionally readout-mitigate and ZNE."""
    if use_zne:
        p, _ = run_zne(dev, x, shots, C.ZNE_SCALE_FACTORS, seed=seed, readout_A=A if use_rem else None)
        return p
    p = dev.run(x, shots, seed=seed)
    return apply_readout_mitigation(p, A) if use_rem else p


def analyse(p0=C.P0, rho=C.RHO, lgd=C.LGD, confidence=C.CONFIDENCE, n=2,
            method=CALIBRATION_METHODS[2], use_rem=True, use_zne=False,
            drift_event=False, auto_recalibrate=False, shots=20000,
            threshold=C.FIDELITY_THRESHOLD):
    t0 = time.time()

    # ---- Stages 1-4: borrower -> commanded angles ------------------------------
    x_nom, encoding = commanded_angles(n, p0, rho)

    # ---- Stage 5-6: transpiled circuit on the noisy chip (today's calibration) --
    dev = NoisyDevice(n, "gci")
    ref = dev.ideal_probs(x_nom)                       # what a perfect chip would give
    A = assignment_matrix(dev)
    M = ReadoutMitigatedDevice(dev, A)
    x_cal, runs = calibrate(method, n, dev, M, ref, x_nom)

    # ---- optional drift event: the chip changes after calibration ---------------
    loop_log = []
    run_dev, run_A = dev, A
    if drift_event:
        run_dev = NoisyDevice(n, "gci", drift=ControlDrift(C.DRIFT_EPS_DAY2, C.DRIFT_DELTA_DEG_DAY2))
        run_A = assignment_matrix(run_dev)

    # ---- Stage 7: execute -------------------------------------------------------
    p_dev = execute(run_dev, run_A, x_cal, shots, use_rem, use_zne)
    fid = hellinger_fidelity(p_dev, ref)
    decision = "ACCEPT" if fid >= threshold else "RE-CALIBRATE"
    loop_log.append({"round": 0, "fidelity": fid, "decision": decision})

    # ---- Stage 9 closed loop: re-run 6B on the drifted chip ---------------------
    recal_runs = 0
    if decision == "RE-CALIBRATE" and auto_recalibrate:
        RM = ReadoutMitigatedDevice(run_dev, run_A)
        for r in range(1, C.MAX_RECALIBRATION_ROUNDS + 1):
            x_cal, used = calibrate(CALIBRATION_METHODS[2], n, run_dev, RM, ref, x_cal, seed=r)
            recal_runs += used
            p_dev = execute(run_dev, run_A, x_cal, shots, use_rem, use_zne, seed=500 + r)
            fid = hellinger_fidelity(p_dev, ref)
            decision = "ACCEPT" if fid >= threshold else "RE-CALIBRATE"
            loop_log.append({"round": r, "fidelity": fid, "decision": decision})
            if decision == "ACCEPT":
                break

    # ---- Stage 8: bitstrings -> money -------------------------------------------
    q = credit_statistics(p_dev, n, lgd=lgd, confidence=confidence)
    ideal = credit_statistics(ref, n, lgd=lgd, confidence=confidence)
    cl_probs = classical_joint_probs(n, p0, rho)
    cl = credit_statistics(cl_probs, n, lgd=lgd, confidence=confidence)
    ul, pdf, cdf, mc_var = monte_carlo_var(p0, rho, lgd, n_trials=500_000, confidence=confidence)

    zz = np.linspace(-C.Z_MAX, C.Z_MAX, 200)
    return {
        "inputs": {"p0": p0, "rho": rho, "lgd": lgd, "confidence": confidence, "n": n,
                   "method": method, "use_rem": use_rem, "use_zne": use_zne,
                   "drift_event": drift_event, "shots": shots},
        "encoding": encoding,
        "z_grid": z_grid(n).tolist(),
        "pd_curve": {"z": zz.tolist(), "pd": pd_given_z(zz, p0, rho).tolist()},
        "probs": {"quantum": np.asarray(p_dev).tolist(), "ideal": np.asarray(ref).tolist(),
                  "classical": np.asarray(cl_probs).tolist()},
        "quantum": q, "ideal": ideal, "classical": cl,
        "monte_carlo": {"unique_losses": ul.tolist(), "cdf": cdf.tolist(), "var": float(mc_var),
                        "expected_loss": float((ul * pdf).sum())},
        "fidelity_vs_ideal": fid,
        "fidelity_vs_classical": hellinger_fidelity(p_dev, cl_probs),
        "decision": decision, "threshold": threshold, "loop": loop_log,
        "calibration_runs": runs, "recalibration_runs": recal_runs,
        "angles_deg": {"nominal": np.rad2deg(x_nom).tolist(), "used": np.rad2deg(x_cal).tolist()},
        "seconds": time.time() - t0,
    }
