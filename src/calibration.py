"""
calibration.py
--------------
Stage 6 -- in-situ retuning of the commanded rotation angles against the noisy
device, so that the MEASURED distribution matches the noiseless reference.

Every method minimises the same black-box objective

    J(x) = H( p_device(x) , p_reference )          (Hellinger distance)

where p_device(x) is estimated from a finite number of shots. The methods never
see the noise model or the control drift -- only measured histograms.

6A  grid_sweep()        -- the base paper's procedure (Sec. IV-A/B/C): a coarse
                           degree-step sweep of one or two angles, then a fine
                           sweep around the best coarse point, other angles fixed.
6B  spsa()              -- Simultaneous Perturbation Stochastic Approximation
                           (Spall 1992). 2 circuit evaluations per iteration
                           REGARDLESS of how many angles are tuned.
6B  bayesian_opt()      -- Gaussian-process Bayesian optimisation with the
                           Expected-Improvement acquisition. Written from scratch
                           in NumPy (no extra dependency) so every step is visible.
"""

import itertools
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm as _norm

from .metrics import hellinger_distance


@dataclass
class CalibrationResult:
    method: str
    x_best: np.ndarray
    n_evals: int
    n_shots: int
    seconds: float
    history: list = field(default_factory=list)   # per-evaluation objective values
    extra: dict = field(default_factory=dict)

    def best_so_far(self):
        return np.minimum.accumulate(np.asarray(self.history))

    def to_dict(self):
        return {"method": self.method, "x_best": np.asarray(self.x_best).tolist(),
                "x_best_deg": np.rad2deg(np.asarray(self.x_best)).tolist(),
                "n_evals": int(self.n_evals), "n_shots": int(self.n_shots),
                "seconds": float(self.seconds), "history": [float(h) for h in self.history],
                **{k: v for k, v in self.extra.items() if k != "landscape"}}


def objective(device, reference, x, shots):
    return hellinger_distance(device.run(x, shots), reference)


# =============================================================================
# 6A -- baseline: coarse -> fine grid sweep (base paper)
# =============================================================================
def grid_sweep(device, reference, x0, indices, coarse_axes, fine_half_widths, fine_steps,
               shots):
    """Paper-style brute-force sweep.

    indices          : which entries of x are swept (all others stay at x0)
    coarse_axes      : list of 1-D arrays (radians) -- the coarse grid per swept index
    fine_half_widths : per index, half-width (radians) of the fine grid around the coarse optimum
    fine_steps       : per index, step (radians) of the fine grid
    """
    t0 = time.time()
    device.reset_counters()
    x0 = np.asarray(x0, dtype=float)
    history = []

    def evaluate(axes):
        pts = list(itertools.product(*axes))
        xs = []
        for p in pts:
            x = x0.copy()
            x[list(indices)] = p
            xs.append(x)
        probs = device.run_many(xs, shots)
        d = np.array([hellinger_distance(p, reference) for p in probs])
        history.extend(d.tolist())
        return xs, d, pts

    xs_c, d_c, pts_c = evaluate(coarse_axes)
    best_c = xs_c[int(np.argmin(d_c))]
    fine_axes = [np.arange(best_c[i] - hw, best_c[i] + hw + 1e-9, st)
                 for i, hw, st in zip(indices, fine_half_widths, fine_steps)]
    xs_f, d_f, pts_f = evaluate(fine_axes)
    x_best = xs_f[int(np.argmin(d_f))]

    return CalibrationResult(
        "6A grid sweep", x_best, device.n_evals, device.n_shots, time.time() - t0, history,
        extra={"landscape": {"coarse_points": np.array(pts_c), "coarse_distance": d_c,
                             "coarse_axes": [np.asarray(a) for a in coarse_axes],
                             "fine_points": np.array(pts_f), "fine_distance": d_f},
               "n_coarse": len(pts_c), "n_fine": len(pts_f)})


# =============================================================================
# 6B -- SPSA
# =============================================================================
def spsa(device, reference, x0, shots, n_iter=150, c=0.12, target_first_step=0.15,
         alpha=0.602, gamma=0.101, seed=0, average_last=0.25):
    """SPSA with Spall's standard gain sequences and automatic step-size calibration.

        a_k = a / (k + 1 + A)^alpha ,  c_k = c / (k + 1)^gamma
        g_k = [J(x + c_k D) - J(x - c_k D)] / (2 c_k) * D        (D_i = +/-1 at random)
        x_{k+1} = x_k - a_k g_k

    `a` is chosen so that the very first update moves the angles by roughly
    `target_first_step` radians (Spall's recommended calibration).
    The returned solution is the average of the last `average_last` fraction of
    iterates (iterate averaging suppresses the shot-noise jitter).
    """
    t0 = time.time()
    device.reset_counters()
    rng = np.random.default_rng(seed)
    x = np.asarray(x0, dtype=float).copy()
    d = len(x)
    A = 0.1 * n_iter

    # --- calibrate the gain a from a few gradient-magnitude samples (costs 2 evals each)
    mags, history = [], []
    for _ in range(4):
        delta = rng.choice([-1.0, 1.0], size=d)
        jp = objective(device, reference, x + c * delta, shots)
        jm = objective(device, reference, x - c * delta, shots)
        history += [jp, jm]
        mags.append(abs(jp - jm) / (2 * c))
    g0 = max(np.mean(mags), 1e-4)
    a = target_first_step * (A + 1) ** alpha / g0

    trajectory = []
    for k in range(n_iter):
        ak = a / (k + 1 + A) ** alpha
        ck = c / (k + 1) ** gamma
        delta = rng.choice([-1.0, 1.0], size=d)
        jp = objective(device, reference, x + ck * delta, shots)
        jm = objective(device, reference, x - ck * delta, shots)
        history += [jp, jm]
        ghat = (jp - jm) / (2 * ck) * delta
        x = x - ak * ghat
        trajectory.append(x.copy())

    k0 = int(len(trajectory) * (1 - average_last))
    x_best = np.mean(trajectory[k0:], axis=0)
    return CalibrationResult("6B SPSA", x_best, device.n_evals, device.n_shots,
                             time.time() - t0, history,
                             extra={"a": float(a), "c": c, "n_iter": n_iter,
                                    "trajectory_deg": np.rad2deg(np.array(trajectory)).tolist()})


# =============================================================================
# 6B -- Bayesian optimisation (Gaussian process + Expected Improvement)
# =============================================================================
class _GP:
    """Zero-mean GP with an isotropic RBF kernel on inputs scaled to [0, 1]^d.
    Length-scale and noise level are picked by maximising the log marginal likelihood
    over a small grid (type-II maximum likelihood)."""

    def fit(self, X, y):
        self.X = X
        self.mu, self.sd = y.mean(), y.std() + 1e-12
        self.y = (y - self.mu) / self.sd
        best = -np.inf
        for ls in (0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 0.7):
            for noise in (1e-3, 1e-2, 5e-2):
                lml, cache = self._lml(ls, noise)
                if lml > best:
                    best, self.ls, self.noise, self.cache = lml, ls, noise, cache
        return self

    def _k(self, A, B, ls):
        d2 = ((A[:, None, :] - B[None, :, :]) ** 2).sum(-1)
        return np.exp(-0.5 * d2 / ls ** 2)

    def _lml(self, ls, noise):
        K = self._k(self.X, self.X, ls) + noise * np.eye(len(self.X))
        try:
            L = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            return -np.inf, None
        alpha = np.linalg.solve(L.T, np.linalg.solve(L, self.y))
        lml = -0.5 * self.y @ alpha - np.log(np.diag(L)).sum()
        return lml, (L, alpha)

    def predict(self, Xs):
        L, alpha = self.cache
        Ks = self._k(Xs, self.X, self.ls)
        mean = Ks @ alpha
        v = np.linalg.solve(L, Ks.T)
        var = np.clip(1.0 - (v ** 2).sum(0), 1e-12, None)
        return mean * self.sd + self.mu, np.sqrt(var) * self.sd


def bayesian_opt(device, reference, x0, shots, budget=40, half_width=np.deg2rad(45),
                 n_init=None, seed=0, xi=0.01):
    """GP-EI Bayesian optimisation inside the box  x0 +/- half_width  (per angle).

    1. Evaluate x0 plus a Latin-hypercube initial design.
    2. Repeat until `budget` evaluations: fit the GP to all (x, J) pairs, pick the
       candidate maximising Expected Improvement, evaluate it.
    3. Return the point with the lowest GP *posterior mean* among evaluated points
       (more robust to a lucky shot-noise draw than the raw minimum).
    """
    t0 = time.time()
    device.reset_counters()
    rng = np.random.default_rng(seed)
    x0 = np.asarray(x0, dtype=float)
    d = len(x0)
    lo, hi = x0 - half_width, x0 + half_width
    to_x = lambda u: lo + u * (hi - lo)
    n_init = n_init or max(2 * d + 2, 6)

    # Latin hypercube initial design (+ the nominal point at the centre)
    U = [np.full(d, 0.5)]
    perms = [rng.permutation(n_init - 1) for _ in range(d)]
    for i in range(n_init - 1):
        U.append(np.array([(perms[j][i] + rng.random()) / (n_init - 1) for j in range(d)]))
    U = np.array(U)
    y = np.array([objective(device, reference, to_x(u), shots) for u in U])
    history = y.tolist()

    gp = _GP()
    while len(y) < budget:
        gp.fit(U, y)
        best_idx = int(np.argmin(y))
        cand = np.vstack([rng.random((3000, d)),
                          np.clip(U[best_idx] + 0.05 * rng.standard_normal((1000, d)), 0, 1)])
        m, s = gp.predict(cand)
        imp = y.min() - m - xi * gp.sd
        z = imp / s
        ei = imp * _norm.cdf(z) + s * _norm.pdf(z)
        u_next = cand[int(np.argmax(ei))]
        y_next = objective(device, reference, to_x(u_next), shots)
        U = np.vstack([U, u_next])
        y = np.append(y, y_next)
        history.append(y_next)

    gp.fit(U, y)
    m, _ = gp.predict(U)
    x_best = to_x(U[int(np.argmin(m))])
    return CalibrationResult("6B Bayesian optimisation", x_best, device.n_evals,
                             device.n_shots, time.time() - t0, history,
                             extra={"length_scale": float(gp.ls), "n_init": int(n_init),
                                    "half_width_deg": float(np.rad2deg(half_width))})


# =============================================================================
# Scoring (not counted in any method's budget)
# =============================================================================
def score(device, reference, x, shots, seed=2024, repeats=3):
    """Hellinger fidelity of the device output at x vs the reference (mean over repeats)."""
    from .metrics import hellinger_fidelity
    n_e, n_s = device.n_evals, device.n_shots
    f = [hellinger_fidelity(device.run(x, shots, seed=seed + r), reference) for r in range(repeats)]
    device.n_evals, device.n_shots = n_e, n_s
    return float(np.mean(f)), float(np.std(f))


# =============================================================================
# 6B -- the full automated procedure used by the pipeline
# =============================================================================
class SubspaceDevice:
    """Expose only some entries of the parameter vector to an optimiser (the rest are
    frozen at x_full). Lets BO/SPSA work on e.g. just the two asset-qubit angles."""

    def __init__(self, device, x_full, indices):
        self.device, self.x_full, self.indices = device, np.asarray(x_full, float), list(indices)

    def _full(self, y):
        x = self.x_full.copy()
        x[self.indices] = y
        return x

    def run(self, y, shots, seed=None):
        return self.device.run(self._full(y), shots, seed)

    def reset_counters(self):
        self.device.reset_counters()

    @property
    def n_evals(self):
        return self.device.n_evals

    @property
    def n_shots(self):
        return self.device.n_shots


def hierarchical_calibration(gci_dev, gci_ref, x_start, loader_dev, loader_ref,
                             shots, loader_budget=40, asset_budget=30, refine_iter=60,
                             half_width=np.deg2rad(45), seed=0, loader_result=None):
    """6B -- automated, closed-loop version of the base paper's own workflow.

    Step 1  Bayesian optimisation of the z-register (loader) angles on the stand-alone
            loader circuit, on the same physical qubits           (paper: Sec. IV-A/B)
    Step 2  Bayesian optimisation of the two asset-qubit angles on the full GCI
            circuit, loader angles frozen at Step 1's result       (paper: Sec. IV-C)
    Step 3  short joint SPSA refinement of ALL angles together (captures the
            loader/asset cross-talk that a block-wise search cannot see)
    Step 4  verification: the Step-2 and Step-3 candidates are each measured with a
            high-shot run and the better one is kept (SPSA can overshoot)

    `loader_result` lets a caller reuse an already-computed Step 1.
    Returns a CalibrationResult whose `extra` holds the per-step breakdown.
    """
    t0 = time.time()
    n = len(loader_ref).bit_length() - 1
    x_start = np.asarray(x_start, dtype=float)
    steps, history = {}, []

    # Step 1 -- loader
    if loader_result is None:
        loader_result = bayesian_opt(loader_dev, loader_ref, x_start[:n], shots,
                                     budget=loader_budget, half_width=half_width, seed=seed)
    x1 = x_start.copy()
    x1[:n] = loader_result.x_best
    steps["step1_loader_bo"] = {"n_evals": loader_result.n_evals, "x_deg": np.rad2deg(x1).tolist()}
    history += loader_result.history

    # Step 2 -- asset angles
    sub = SubspaceDevice(gci_dev, x1, [n, n + 1])
    r2 = bayesian_opt(sub, gci_ref, x1[[n, n + 1]], shots, budget=asset_budget,
                      half_width=half_width, seed=seed)
    x2 = x1.copy()
    x2[[n, n + 1]] = r2.x_best
    steps["step2_asset_bo"] = {"n_evals": r2.n_evals, "x_deg": np.rad2deg(x2).tolist()}
    history += r2.history

    # Step 3 -- joint refinement
    r3 = spsa(gci_dev, gci_ref, x2, shots, n_iter=refine_iter, c=0.06,
              target_first_step=0.05, seed=seed)
    steps["step3_joint_spsa"] = {"n_evals": r3.n_evals, "x_deg": np.rad2deg(r3.x_best).tolist()}
    history += r3.history

    # Step 4 -- verification (cost counted)
    ver_shots = 4 * shots
    f2 = score(gci_dev, gci_ref, x2, ver_shots)[0]
    f3 = score(gci_dev, gci_ref, r3.x_best, ver_shots)[0]
    x_best = r3.x_best if f3 >= f2 else x2
    steps["step4_verification"] = {"n_evals": 6, "fidelity_step2": f2, "fidelity_step3": f3,
                                   "kept": "step3" if f3 >= f2 else "step2"}

    n_evals = loader_result.n_evals + r2.n_evals + r3.n_evals + 6
    n_shots = (loader_result.n_shots + r2.n_shots + r3.n_shots + 6 * ver_shots)
    return CalibrationResult("6B automated (BO -> BO -> SPSA)", x_best, n_evals, n_shots,
                             time.time() - t0, history, extra={"steps": steps})
