"""
stages.py
---------
The computational core of Stages 6-9, written as plain functions so that the
SAME code is used by

  * the narrated notebooks  (06_hardware_retuning.ipynb ... 09_var_fidelity_check.ipynb),
    which call these functions step by step and add explanation + plots, and
  * the headless runners    (scripts/run_stage06_*.py ... run_stage09_*.py),
    which call the `run_stageXX()` wrappers at the bottom.

Every stage reads the previous stage's JSON from results/ and writes its own.
"""

import numpy as np

from . import config as C
from .calibration import grid_sweep, spsa, bayesian_opt, score, hierarchical_calibration
from .device import NoisyDevice
from .metrics import hellinger_fidelity, hellinger_distance
from .mitigation import (assignment_matrix, apply_readout_mitigation, run_zne,
                         ReadoutMitigatedDevice)
from .noise_model import ControlDrift
from .pipeline_io import nominal_parameters, save_json, load_stage_output
from .postprocessing import credit_statistics, classical_joint_probs
from .gci_model import target_gaussian_histogram, monte_carlo_var

D = np.deg2rad


def config_snapshot():
    keys = ["P0", "RHO", "LGD", "Z_MAX", "CONFIDENCE", "NATIVE_GATES", "COUPLING_EDGES",
            "DEPOL_1Q", "DEPOL_2Q", "READOUT_ERRORS", "SHOTS_CALIBRATION", "SHOTS_FINAL_CHECK",
            "SPSA_ITERATIONS", "BO_BUDGET", "BO_SEARCH_HALF_WIDTH_DEG", "SHOTS_EXECUTION",
            "N_REPEATS", "ZNE_SCALE_FACTORS", "FIDELITY_THRESHOLD"]
    return {k: getattr(C, k) for k in keys}


# =============================================================================
# STAGE 6 -- hardware / noise-model retuning
# =============================================================================
def make_device(n, kind, drift=None):
    """Noisy device + nominal commanded parameters + noiseless reference distribution."""
    layout = None
    if kind == "loader":
        # calibrate the loader on the same physical qubits the GCI circuit uses for z
        layout = NoisyDevice(n, "gci", drift=drift).phys[:n]
    dev = NoisyDevice(n, kind, drift=drift, initial_layout=layout)
    x_nom = np.array(nominal_parameters(n))
    if kind == "loader":
        x_nom = x_nom[:n]
    reference = dev.ideal_probs(x_nom)
    return dev, x_nom, reference


def mitigated(dev):
    """Readout-calibrate a device and return (A, mitigation-aware wrapper)."""
    A = assignment_matrix(dev)
    return A, ReadoutMitigatedDevice(dev, A)


def paper_grid_loader(n, dev, ref, x_nom):
    """6A on the Gaussian loader, reproducing the paper's own sweep ranges/steps.

    2-qubit (Sec. IV-A): theta_0 fixed, theta_1 swept 90..450 deg in 21 deg steps,
                         then 1 deg steps around the best coarse point.
    3-qubit (Sec. IV-B): theta_0 fixed, theta_1 and theta_2 swept 90..450 deg in 36 deg
                         steps, then 7.5 deg (theta_1) / 14.5 deg (theta_2) fine steps.
    """
    if n == 2:
        return grid_sweep(dev, ref, x_nom, [1], [D(np.arange(90, 451, 21))],
                          [D(21)], [D(1)], C.SHOTS_CALIBRATION)
    return grid_sweep(dev, ref, x_nom, [1, 2],
                      [D(np.arange(90, 451, 36)), D(np.arange(90, 451, 36))],
                      [D(36), D(43.5)], [D(7.5), D(14.5)], C.SHOTS_CALIBRATION)


def paper_grid_gci(n, dev, ref, x_start):
    """6A on the full GCI circuit (Sec. IV-C / Table 3): the loader angles are taken from
    the loader sweep and frozen; the two asset-qubit gate angles -- the offset rotation
    Ry(2*beta) and the slope rotation CRy(2*alpha) -- are swept on a 2-D grid
    (coarse 10 deg x 3 deg, then fine 2 deg x 0.5 deg)."""
    b, a = x_start[n], x_start[n + 1]
    # the grid is defined on GATE angles (2*beta, 2*alpha) in degrees -> divide by 2
    return grid_sweep(dev, ref, x_start, [n, n + 1],
                      [b + D(np.arange(-60, 61, 10)) / 2, a + D(np.arange(-15, 16, 3)) / 2],
                      [D(10) / 2, D(3) / 2], [D(2) / 2, D(0.5) / 2], C.SHOTS_CALIBRATION)


def summarise_method(dev, ref, res, target=None):
    f, sd = score(dev, ref, res.x_best, C.SHOTS_FINAL_CHECK)
    d = res.to_dict()
    d.update({"fidelity": f, "fidelity_std": sd})
    if target is not None:
        p = dev.run(res.x_best, C.SHOTS_FINAL_CHECK, seed=99)
        d["fidelity_vs_target_gaussian"] = hellinger_fidelity(p, target)
    return d


def stage06_loader(n, verbose=True):
    """Part A -- Gaussian loader alone (paper Sec. IV-A / IV-B)."""
    log = print if verbose else (lambda *a, **k: None)
    dev, x0, ref = make_device(n, "loader")
    A, M = mitigated(dev)
    _, target = target_gaussian_histogram(n, C.Z_MAX)
    f_raw = score(dev, ref, x0, C.SHOTS_FINAL_CHECK)
    f0 = score(M, ref, x0, C.SHOTS_FINAL_CHECK)
    log(f"[{n}q loader] uncalibrated: F_H raw = {f_raw[0]:.4f}, with readout mitigation = {f0[0]:.4f}")
    g = paper_grid_loader(n, M, ref, x0)
    b = bayesian_opt(M, ref, x0, C.SHOTS_CALIBRATION, budget=C.BO_BUDGET["loader"],
                     half_width=D(C.BO_SEARCH_HALF_WIDTH_DEG))
    s = spsa(M, ref, x0, C.SHOTS_CALIBRATION, n_iter=C.SPSA_ITERATIONS)
    methods = {"grid_6A": summarise_method(M, ref, g, target),
               "bo_6B": summarise_method(M, ref, b, target),
               "spsa_ablation": summarise_method(M, ref, s, target)}
    for k, v in methods.items():
        log(f"   {k:14s}: F_H = {v['fidelity']:.4f}   circuit evaluations = {v['n_evals']:4d}")
    summary = {"device": dev.summary(), "x_nominal": x0.tolist(), "reference": ref.tolist(),
               "target_gaussian": target.tolist(), "assignment_matrix": A.tolist(),
               "uncalibrated": {"fidelity_raw": f_raw[0], "fidelity": f0[0], "fidelity_std": f0[1]},
               "methods": methods}
    return summary, {"device": dev, "M": M, "ref": ref, "x0": x0, "grid": g, "bo": b, "spsa": s}


def stage06_gci(n, loader_objs, verbose=True):
    """Part B -- full GCI circuit (paper Sec. IV-C)."""
    log = print if verbose else (lambda *a, **k: None)
    dev, x0, ref = make_device(n, "gci")
    A, M = mitigated(dev)
    f_raw = score(dev, ref, x0, C.SHOTS_FINAL_CHECK)
    f0 = score(M, ref, x0, C.SHOTS_FINAL_CHECK)
    log(f"[{n}q GCI]    uncalibrated: F_H raw = {f_raw[0]:.4f}, with readout mitigation = {f0[0]:.4f}")

    # 6A -- paper workflow: loader angles from the loader grid sweep, then asset grid
    x_start = x0.copy()
    x_start[:n] = loader_objs["grid"].x_best
    g = paper_grid_gci(n, M, ref, x_start)
    g.n_evals += loader_objs["grid"].n_evals        # full 6A cost = both sweeps
    g.n_shots += loader_objs["grid"].n_shots

    # 6B -- automated hierarchical calibration (reuses the loader BO from Part A)
    h = hierarchical_calibration(M, ref, x0, loader_objs["M"], loader_objs["ref"],
                                 C.SHOTS_CALIBRATION, loader_result=loader_objs["bo"])
    # ablations: one optimiser on all n+2 angles at once
    s = spsa(M, ref, x0, C.SHOTS_CALIBRATION, n_iter=C.SPSA_ITERATIONS)
    b = bayesian_opt(M, ref, x0, C.SHOTS_CALIBRATION, budget=C.BO_BUDGET["gci"],
                     half_width=D(C.BO_SEARCH_HALF_WIDTH_DEG))
    methods = {"grid_6A": summarise_method(M, ref, g), "auto_6B": summarise_method(M, ref, h),
               "joint_spsa_ablation": summarise_method(M, ref, s),
               "joint_bo_ablation": summarise_method(M, ref, b)}
    for k, v in methods.items():
        log(f"   {k:20s}: F_H = {v['fidelity']:.4f}   circuit evaluations = {v['n_evals']:4d}")
    summary = {"device": dev.summary(), "x_nominal": x0.tolist(), "reference": ref.tolist(),
               "assignment_matrix": A.tolist(),
               "uncalibrated": {"fidelity_raw": f_raw[0], "fidelity": f0[0], "fidelity_std": f0[1]},
               "methods": methods}
    params = {"uncalibrated": x0.tolist(), "grid_6A": np.asarray(g.x_best).tolist(),
              "auto_6B": np.asarray(h.x_best).tolist()}
    return summary, params, {"device": dev, "M": M, "ref": ref, "x0": x0, "grid": g, "auto": h,
                             "spsa": s, "bo": b}


def stage06_for_register(n, verbose=True):
    loader_summary, loader_objs = stage06_loader(n, verbose)
    gci_summary, params, gci_objs = stage06_gci(n, loader_objs, verbose)
    return {"loader": loader_summary, "gci": gci_summary, "calibrated_parameters": params,
            "_objects": {"loader": loader_objs, "gci": gci_objs}}


def save_stage06(results):
    clean = {"config": config_snapshot(),
             "note": "all calibration methods see only readout-mitigated measurement "
                     "histograms; the hidden drift values stored under device/drift are "
                     "for transparency only and are never read by any method"}
    for n, r in results.items():
        clean[f"{n}_qubit"] = {k: v for k, v in r.items() if k != "_objects"}
    return save_json(clean, "stage06_retuning.json")


def run_stage06(verbose=True):
    results = {n: stage06_for_register(n, verbose) for n in C.REGISTER_SIZES}
    path = save_stage06(results)
    if verbose:
        print(f"Saved -> {path}")
    return results


# =============================================================================
# STAGE 7 -- execution on the noise-emulated backend (+ mitigation)
# =============================================================================
VARIANT_DESCRIPTIONS = {
    "ideal_noiseless": "Stage-4 angles, exact noiseless simulation (the paper's Fig. 10a reference)",
    "noisy_uncalibrated": "Stage-4 angles on the noisy device, raw counts (no correction at all)",
    "uncalibrated_REM": "Stage-4 angles + readout-error mitigation only (no retuning)",
    "6A_grid_REM": "angles from the 6A manual grid sweep (base paper) + readout mitigation",
    "6B_auto_REM": "angles from the 6B automated calibration (this project) + readout mitigation",
    "6B_auto_REM_ZNE": "6B angles + readout mitigation + zero-noise extrapolation",
}


def execute_variants(n, params, dev=None, n_repeats=None, shots=None, seed0=500, verbose=True):
    """Run every variant N_REPEATS times with independent shot seeds."""
    log = print if verbose else (lambda *a, **k: None)
    n_repeats = n_repeats or C.N_REPEATS
    shots = shots or C.SHOTS_EXECUTION
    if dev is None:
        dev = NoisyDevice(n, "gci")
    x_unc = np.array(params["uncalibrated"])
    x_6a = np.array(params["grid_6A"])
    x_6b = np.array(params["auto_6B"])
    ref = dev.ideal_probs(x_unc)
    A = assignment_matrix(dev)

    runs = {k: [] for k in VARIANT_DESCRIPTIONS}
    for r in range(n_repeats):
        s = seed0 + 1000 * r
        runs["ideal_noiseless"].append(ref)
        p_unc = dev.run(x_unc, shots, seed=s)
        runs["noisy_uncalibrated"].append(p_unc)
        runs["uncalibrated_REM"].append(apply_readout_mitigation(p_unc, A))
        runs["6A_grid_REM"].append(apply_readout_mitigation(dev.run(x_6a, shots, seed=s + 1), A))
        runs["6B_auto_REM"].append(apply_readout_mitigation(dev.run(x_6b, shots, seed=s + 2), A))
        runs["6B_auto_REM_ZNE"].append(run_zne(dev, x_6b, shots, C.ZNE_SCALE_FACTORS,
                                               seed=s + 3, readout_A=A)[0])
    variants = {}
    for k, lst in runs.items():
        arr = np.array(lst)
        f = [hellinger_fidelity(p, ref) for p in arr]
        variants[k] = {"description": VARIANT_DESCRIPTIONS[k],
                       "mean_probs": arr.mean(0).tolist(), "std_probs": arr.std(0).tolist(),
                       "repeat_probs": arr.tolist(),
                       "fidelity_vs_ideal_mean": float(np.mean(f)),
                       "fidelity_vs_ideal_std": float(np.std(f))}
        log(f"  [{n}q] {k:20s} F_H vs ideal = {np.mean(f):.4f} +/- {np.std(f):.4f}")
    return {"device": dev.summary(), "reference_ideal": ref.tolist(),
            "assignment_matrix": A.tolist(), "shots": shots, "n_repeats": n_repeats,
            "zne_scale_factors": list(C.ZNE_SCALE_FACTORS),
            "commanded_parameters": {k: np.asarray(v).tolist() for k, v in params.items()},
            "variants": variants}


def run_stage07(verbose=True):
    s6 = load_stage_output("stage06_retuning.json")
    out = {"config": config_snapshot()}
    for n in C.REGISTER_SIZES:
        out[f"{n}_qubit"] = execute_variants(n, s6[f"{n}_qubit"]["calibrated_parameters"],
                                             verbose=verbose)
    path = save_json(out, "stage07_execution.json")
    if verbose:
        print(f"Saved -> {path}")
    return out


# =============================================================================
# STAGE 8 -- classical post-processing
# =============================================================================
def classical_references(n, enc_params):
    exact = classical_joint_probs(n)
    lin = classical_joint_probs(n, linearized=(enc_params["alpha_tilde"], enc_params["beta_tilde"]))
    ul, pdf, cdf, var = monte_carlo_var(C.P0, C.RHO, C.LGD, confidence=C.CONFIDENCE)
    return {
        "classical_discrete_grid": {"probs": exact.tolist(), **credit_statistics(exact, n)},
        "classical_linearized_encoding": {"probs": lin.tolist(), **credit_statistics(lin, n)},
        "classical_monte_carlo_continuous": {"unique_losses": ul.tolist(), "pdf": pdf.tolist(),
                                             "cdf": cdf.tolist(), "var": float(var),
                                             "expected_loss": float((ul * pdf).sum()),
                                             "p_default": float(pdf[-1])},
    }


def postprocess_register(n, s7_reg, enc_params):
    variants = {}
    for k, v in s7_reg["variants"].items():
        stats = credit_statistics(v["mean_probs"], n)
        reps = [credit_statistics(p, n) for p in v["repeat_probs"]]
        stats["expected_loss_std"] = float(np.std([r["expected_loss"] for r in reps]))
        stats["p_default_std"] = float(np.std([r["p_default"] for r in reps]))
        stats["repeat_cdf0"] = [r["p_loss_le_0"] for r in reps]
        stats["repeat_var"] = [r["var"] for r in reps]
        variants[k] = stats
    return {"variants": variants, "classical": classical_references(n, enc_params)}


def run_stage08(verbose=True):
    from .pipeline_io import load_encoding_params
    s7 = load_stage_output("stage07_execution.json")
    enc = load_encoding_params()["register_adapted"]
    out = {}
    for n in C.REGISTER_SIZES:
        out[f"{n}_qubit"] = postprocess_register(n, s7[f"{n}_qubit"], enc[f"{n}_qubit"])
        if verbose:
            for k, v in out[f"{n}_qubit"]["variants"].items():
                print(f"  [{n}q] {k:20s} P(L<=0) = {v['cdf'][0]:.4f}  EL = ${v['expected_loss']:.1f}"
                      f"  VaR95 = ${v['var']:.0f}")
    path = save_json(out, "stage08_postprocessing.json")
    if verbose:
        print(f"Saved -> {path}")
    return out


# =============================================================================
# STAGE 9 -- VaR & fidelity check, ACCEPT / RE-CALIBRATE loop
# =============================================================================
def fidelity_table(n, s7_reg, s8_reg):
    ref = np.array(s7_reg["reference_ideal"])
    classical = np.array(s8_reg["classical"]["classical_discrete_grid"]["probs"])
    cl_loss = np.array(s8_reg["classical"]["classical_discrete_grid"]["pdf"])
    cl_var = s8_reg["classical"]["classical_discrete_grid"]["var"]
    _, target_z = target_gaussian_histogram(n, C.Z_MAX)
    rows = {}
    for k, v in s7_reg["variants"].items():
        reps = np.array(v["repeat_probs"])
        f_ideal = [hellinger_fidelity(p, ref) for p in reps]
        f_class = [hellinger_fidelity(p, classical) for p in reps]
        st = s8_reg["variants"][k]
        f_loss = hellinger_fidelity(st["pdf"], cl_loss)
        f_z = hellinger_fidelity(st["z_marginal"], target_z)
        rows[k] = {
            "F_vs_ideal_mean": float(np.mean(f_ideal)), "F_vs_ideal_std": float(np.std(f_ideal)),
            "F_vs_classical_joint_mean": float(np.mean(f_class)),
            "F_vs_classical_joint_std": float(np.std(f_class)),
            "F_loss_distribution_vs_classical": float(f_loss),
            "F_z_marginal_vs_target_gaussian": float(f_z),
            "VaR95": st["var"], "VaR95_matches_classical": bool(st["var"] == cl_var),
            "VaR95_all_repeats_match": bool(all(v_ == cl_var for v_ in st["repeat_var"])),
            "expected_loss": st["expected_loss"], "expected_loss_std": st["expected_loss_std"],
            "p_loss_le_0": st["cdf"][0],
        }
    return rows


def acceptance_check(fidelity, threshold=C.FIDELITY_THRESHOLD):
    return "ACCEPT" if fidelity >= threshold else "RE-CALIBRATE"


def recalibration_loop(n, x_start, drift, threshold=C.FIDELITY_THRESHOLD,
                       max_rounds=C.MAX_RECALIBRATION_ROUNDS, verbose=True):
    """Closed loop of architecture boxes 9 -> RE-CALIBRATE -> 6B -> 7 -> 9.

    The deployed pipeline is '6B angles + readout mitigation'. Its Hellinger fidelity
    against the noiseless reference is measured on the (possibly drifted) device; if it
    is below `threshold`, Stage 6B is re-run automatically, warm-started from the
    current angles, and the check is repeated."""
    log = print if verbose else (lambda *a, **k: None)
    dev, x_nom, ref = make_device(n, "gci", drift=drift)
    ldev, _, lref = make_device(n, "loader", drift=drift)
    _, M = mitigated(dev)
    _, ML = mitigated(ldev)
    x = np.array(x_start, dtype=float)
    rounds, total_evals = [], 0
    for r in range(max_rounds + 1):
        f, sd = score(M, ref, x, C.SHOTS_FINAL_CHECK)
        decision = acceptance_check(f, threshold)
        rounds.append({"round": r, "fidelity": f, "fidelity_std": sd, "decision": decision,
                       "cumulative_calibration_evals": total_evals,
                       "x_deg": np.rad2deg(x).tolist()})
        log(f"  round {r}: F_H = {f:.4f}  ->  {decision}")
        if decision == "ACCEPT" or r == max_rounds:
            break
        h = hierarchical_calibration(M, ref, x, ML, lref, C.SHOTS_CALIBRATION, seed=r + 1)
        total_evals += h.n_evals
        log(f"     re-ran Stage 6B automatically ({h.n_evals} circuit evaluations)")
        x = np.asarray(h.x_best)
    return {"rounds": rounds, "final_parameters": x.tolist(),
            "accepted": rounds[-1]["decision"] == "ACCEPT",
            "total_recalibration_evals": total_evals, "drift": drift.describe(dev.phys)}


def run_stage09(verbose=True):
    s6 = load_stage_output("stage06_retuning.json")
    s7 = load_stage_output("stage07_execution.json")
    s8 = load_stage_output("stage08_postprocessing.json")
    out = {"config": config_snapshot(), "threshold": C.FIDELITY_THRESHOLD}
    for n in C.REGISTER_SIZES:
        key = f"{n}_qubit"
        table = fidelity_table(n, s7[key], s8[key])
        deployed = table["6B_auto_REM"]["F_vs_ideal_mean"]
        decision = acceptance_check(deployed)
        if verbose:
            print(f"[{n}q] deployed pipeline (6B + REM): F_H = {deployed:.4f} -> {decision}")
        x6b = s6[key]["calibrated_parameters"]["auto_6B"]
        day1 = recalibration_loop(n, x6b, ControlDrift(), verbose=verbose)
        if verbose:
            print(f"[{n}q] drift event (chip re-calibrated overnight, new miscalibration):")
        day2 = recalibration_loop(n, x6b, ControlDrift(C.DRIFT_EPS_DAY2, C.DRIFT_DELTA_DEG_DAY2),
                                  verbose=verbose)
        out[key] = {"fidelity_table": table, "deployed_pipeline": "6B_auto_REM",
                    "deployed_fidelity": deployed, "decision": decision,
                    "loop_day1": day1, "loop_day2_drift_event": day2,
                    "classical_var95": s8[key]["classical"]["classical_discrete_grid"]["var"],
                    "classical_mc_var95": s8[key]["classical"]["classical_monte_carlo_continuous"]["var"]}
    path = save_json(out, "stage09_final_report.json")
    from .report import write_final_report
    rpath = write_final_report(s6, s7, s8, out)
    if verbose:
        print(f"Saved -> {path}")
        print(f"Saved -> {rpath}")
    return out
