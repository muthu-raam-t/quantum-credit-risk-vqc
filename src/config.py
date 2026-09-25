"""
config.py
---------
Single source of truth for every constant used by Stages 5-9 (and by the
master runner). Earlier stages (1-4) keep their own local constants exactly as
they were committed; the values here are identical to theirs.

Nothing in this file is "tuned to make results look good" -- the noise and
drift numbers are chosen to be in the same range as the base paper's hardware
(Sec. III / Table 1 / Sec. IV-C: ~5% readout error, ~99.5% single-qubit and
~97-98% two-qubit gate fidelities, 60 ns DRAG pulses with amplitude/phase
miscalibration).
"""

import os

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(ROOT_DIR, "results")
FIG_DIR = os.path.join(RESULTS_DIR, "figures")

# --------------------------------------------------------------------------
# Financial model (Stage 1) -- the base paper's hardware use case, Sec. IV-C
# --------------------------------------------------------------------------
P0 = 0.25          # baseline default probability p0
RHO = 0.027        # asset correlation rho
LGD = 1000         # loss given default ($)
Z_MAX = 3.0        # latent-factor grid spans [-Z_MAX, Z_MAX]
CONFIDENCE = 0.95  # VaR confidence level
REGISTER_SIZES = (2, 3)   # z-register sizes studied throughout the pipeline

# --------------------------------------------------------------------------
# Transpilation (Stage 5) -- identical to 05_transpilation.ipynb
# --------------------------------------------------------------------------
NATIVE_GATES = ["rz", "sx", "x", "cz"]
SEED_TRANSPILER = 7
OPTIMIZATION_LEVEL = 1
# Mock linear-chain devices, one physical qubit larger than the circuit needs.
COUPLING_EDGES = {
    2: [[0, 1], [1, 2], [2, 3]],          # 3-qubit GCI circuit -> 4-qubit line
    3: [[0, 1], [1, 2], [2, 3], [3, 4]],  # 4-qubit GCI circuit -> 5-qubit line
}

# --------------------------------------------------------------------------
# Noise model (Stage 6/7) -- the "noise-emulated backend"
# --------------------------------------------------------------------------
# Depolarizing error per native gate (rz is a virtual, error-free frame change,
# exactly as on the base paper's device, Sec. III).
DEPOL_1Q = 0.002    # sx / x   -> ~99.8% 1q gate fidelity
DEPOL_2Q = 0.015    # cz       -> ~98.5% 2q gate fidelity
# Per-PHYSICAL-qubit readout assignment errors [P(read 1 | prepared 0), P(read 0 | prepared 1)].
# 1->0 is larger than 0->1 because of T1 decay during the readout pulse. Average ~5%.
READOUT_ERRORS = [
    [0.030, 0.060],
    [0.025, 0.055],
    [0.035, 0.070],
    [0.020, 0.050],
    [0.030, 0.065],
]

# Coherent control miscalibration ("hidden drift"). Each PHYSICAL qubit's Ry
# pulse realises   theta_real = (1 + eps) * theta_commanded + delta
# i.e. an amplitude over/undershoot (eps) plus a small phase/offset error (delta).
# The retuning algorithms in Stage 6 NEVER read these numbers -- they only see
# measurement counts, exactly like an experimentalist in front of a real chip.
DRIFT_EPS = [0.12, -0.10, 0.14, -0.11, 0.10]
DRIFT_DELTA_DEG = [12.0, -15.0, 10.0, -12.0, 14.0]

# A second, different calibration state of the same chip ("the next day").
# Used only by Stage 9 to demonstrate the ACCEPT / RE-CALIBRATE loop.
DRIFT_EPS_DAY2 = [-0.10, 0.13, -0.12, 0.11, -0.09]
DRIFT_DELTA_DEG_DAY2 = [-14.0, 11.0, -13.0, 12.0, -10.0]

SEED_SIMULATOR = 1234

# --------------------------------------------------------------------------
# Retuning (Stage 6)
# --------------------------------------------------------------------------
SHOTS_CALIBRATION = 4000        # shots per circuit evaluation inside a retuning loop
SHOTS_FINAL_CHECK = 20000       # shots used to score a finished calibration
SPSA_ITERATIONS = 150           # 2 circuit evaluations per iteration
BO_BUDGET = {"loader": 40, "gci": 70}  # total circuit evaluations for Bayesian Optimisation
BO_SEARCH_HALF_WIDTH_DEG = 45.0  # BO searches commanded angle +/- this around the nominal value

# --------------------------------------------------------------------------
# Execution / mitigation (Stage 7)
# --------------------------------------------------------------------------
SHOTS_EXECUTION = 20000
N_REPEATS = 20                  # independent repetitions -> error bars (paper used 100)
ZNE_SCALE_FACTORS = [1, 3, 5]   # global unitary folding  U (U^dag U)^k

# --------------------------------------------------------------------------
# Acceptance test (Stage 9)
# --------------------------------------------------------------------------
FIDELITY_THRESHOLD = 0.97       # Hellinger fidelity (6B + readout mitigation) vs. ideal reference needed to ACCEPT
MAX_RECALIBRATION_ROUNDS = 3
