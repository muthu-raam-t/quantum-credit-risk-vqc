# Project Deep Dive — Equation · Code · Architecture

**Quantum Circuit-Based Adaptation for Credit Risk Analysis**
Base paper: Ahmad et al., *IEEE Transactions on Quantum Engineering*, vol. 7, 3103316, 2026

This guide explains the whole project from scratch. Every block of the architecture diagram (`images/quantum_architecture.png`) is explained as a **trio**:

| Part | What it tells you |
|---|---|
| **Equation** | what the maths says, with the paper's equation number |
| **Code** | the file and function that implements it, with the key lines |
| **Architecture** | where the block sits in the diagram, what it receives, what it passes on |
| **Why this, not others** | the design choice and the alternatives that were not taken |

Read it top to bottom once. By the end, every equation, every code file and every block of the diagram has been covered — the checklist in §9 proves it.

---

## Contents

- [§0 The project from scratch](#0-the-project-from-scratch)
- [§1 Map of the repository](#1-map-of-the-repository)
- [§2 Part A — Finance branch (Eq. 1–4)](#2-part-a--finance-branch-eq-14)
- [§3 Part A — Loader branch (Eq. 5–13, training)](#3-part-a--loader-branch-eq-513-training)
- [§4 Part A — Full circuit and transpilation (Eq. 14–17, SABRE)](#4-part-a--full-circuit-and-transpilation)
- [§5 Part B — The noisy device](#5-part-b--the-noisy-device)
- [§6 Part C — Calibration (6A vs 6B)](#6-part-c--calibration-6a-vs-6b)
- [§7 Part D — Execution and mitigation](#7-part-d--execution-and-mitigation)
- [§8 Parts E and F — Risk numbers and the closed loop](#8-parts-e-and-f--risk-numbers-and-the-closed-loop)
- [§9 Supporting files, end-to-end trace, and the "nothing left out" checklist](#9-supporting-files-end-to-end-trace-and-checklist)

---

## §0 The project from scratch

### 0.1 The business question
A bank lends **$1000** to a borrower. If the borrower **defaults** (does not repay), the bank loses that money — the **loss given default (LGD)**. The bank must report how bad its losses could get. The regulatory number is the **95 % Value at Risk (VaR)**: the loss that is *not exceeded* in 95 % of scenarios.

### 0.2 Why it is hard
Borrowers default **together** in a bad economy. So the default probability is not a fixed number — it depends on a hidden variable, "the state of the economy", called **z**. The standard model of this is the **Gaussian Conditional-Independence (GCI) model**, also called the **Vasicek model**. Banks evaluate it with **Monte Carlo**: simulate millions of economies and defaults, then read the 95 % point. Monte Carlo error shrinks only as 1/√N.

### 0.3 Why quantum
**Quantum Amplitude Estimation (QAE)** estimates the same quantities with error ∝ 1/N — a **quadratic speed-up**. But before QAE can work, the credit model must be **loaded** into a quantum circuit: a circuit whose measurements reproduce the joint distribution of (economy, default). That loading circuit is what the base paper — and this project — builds.

### 0.4 Why noise matters
Today's chips are **NISQ** (Noisy Intermediate-Scale Quantum): rotation pulses are miscalibrated, measurements misread bits, gates add noise, and qubits only talk to neighbours. A circuit trained on a perfect simulator gives the **wrong distribution** on a real chip.

### 0.5 What the base paper did and what this project does
| | Base paper | This project |
|---|---|---|
| Build the loading circuit, train it, transpile it | yes | yes (replicated) |
| Run on a noisy chip | real superconducting chip | emulated noisy device on a laptop |
| Fix the angles for the noisy chip | **by hand**, grid sweep | **automated**: Bayesian optimisation + SPSA |
| Error mitigation | none | readout mitigation + zero-noise extrapolation |
| When the chip drifts | redo by hand | detected and repaired automatically |

### 0.6 The pipeline in one sentence
**Finance model → encode it as qubit rotations → train a circuit to load the economy's bell curve → fit the circuit to the chip → make the noisy chip produce the right distribution (calibration + mitigation) → turn measurements into losses → compute VaR → check the result and recalibrate if needed.**

---

## §1 Map of the repository

### 1.1 Code files and which blocks they implement

| File | Role | Diagram part |
|---|---|---|
| `src/gci_model.py` | Vasicek PD(z), z-grid, target Gaussian, classical VaR baselines | A (Eq. 1, 10), E (reference) |
| `src/quantum_encoding.py` | fit PD(z) ≈ sin²(αz+β); register-adapt to α̃, β̃ | A (Eq. 2–4) |
| `src/vqc_circuit.py` | loader ansatz and full GCI circuit (Stage 3 version) | A (Eq. 5, 6, 12–13, full circuit) |
| `src/training.py` | circuit probabilities + the training loop | A (Eq. 8–9, 11) |
| `src/parameter_shift.py` | exact quantum gradients, MSE loss | A (parameter shift, Eq. 11) |
| `src/adam.py` | Adam optimiser | A (Adam) |
| `src/transpilation.py` | parameterised circuits + SABRE transpilation | A (full circuit, SABRE) |
| `src/noise_model.py` | depolarizing, readout, drift | B (Addition 1) |
| `src/device.py` | `NoisyDevice` — "the chip" | B (Addition 1), used by C–F |
| `src/metrics.py` | Hellinger distance/fidelity, counts → probabilities | B (Addition 2), E |
| `src/calibration.py` | grid sweep (6A), SPSA, Bayesian optimisation, 6B procedure | C (6A, Addition 3) |
| `src/mitigation.py` | readout mitigation, ZNE, mitigation-aware wrapper | B (Addition 2), D (Additions 5–6) |
| `src/postprocessing.py` | bitstrings → loss PDF/CDF, VaR, CVaR, classical joint | E (post-processing, Addition 7) |
| `src/stages.py` | orchestration of stages 6–9 | C, D, E, F |
| `src/report.py` | writes `results/FINAL_REPORT.md` | output |
| `src/config.py` | every setting in one place | all |
| `src/pipeline_io.py` | finds and saves stage outputs | all |
| `run_pipeline.py`, `main.ipynb` | run every stage in order | all |
| `scripts/run_stage0X_*.py` | headless runner per stage | all |
| `00_…09_*.ipynb` | narrated notebook per stage | all |
| `images/build_quantum_diagram.py` | draws the architecture diagram | documentation |

### 1.2 The diagram's six parts

| Part | Name | Blocks |
|---|---|---|
| A | Replication | Eq. 1–17, parameter shift, Adam, full GCI circuit, SABRE |
| B | Noisy device | Addition 1 (device), Addition 2 (objective) |
| C | Calibration | Eq. 14–17 side branch, 6A grid sweep, Addition 3 (6B), calibrated angles |
| D | Execution + mitigation | Additions 4, 5, 6, corrected distribution |
| E | Risk numbers | post-processing, Addition 7, VaR + Hellinger |
| F | Closed loop | Addition 8 (fidelity gate), ACCEPT, RE-CALIBRATE |

---

## §2 Part A — Finance branch (Eq. 1–4)

> **Flow of this branch:** Eq. 1 → Eq. 2 → Eq. 3 → Eq. 4 → asset gates of the full circuit.
> It turns the bank's default formula into quantum gates.

### 2.1 Eq. 1 — Vasicek / GCI conditional default probability

**Equation (paper Eq. 1)**

$$
\mathrm{PD}(z) = \Phi\!\left(\frac{\Phi^{-1}(p_0) - \sqrt{\rho}\,z}{\sqrt{1-\rho}}\right)
$$

- **z** — the economy, z ~ N(0, 1). Negative = recession.
- **p₀ = 0.25** — the borrower's average default probability.
- **ρ = 0.027** — how strongly the borrower depends on the economy.
- **Φ** — standard normal CDF; **Φ⁻¹** — its inverse.

**What it does:** gives the default probability *in a given economy*. With the project's parameters: PD(−3) ≈ 0.427, PD(0) ≈ 0.247, PD(+3) ≈ 0.118. Bad economy → more defaults.

**Code** — `src/gci_model.py → pd_given_z`
```python
def pd_given_z(z, p0, rho):
    numerator = norm.ppf(p0) - np.sqrt(rho) * z      # Φ⁻¹(p0) − √ρ·z
    denominator = np.sqrt(1 - rho)                    # √(1−ρ)
    return norm.cdf(numerator / denominator)          # Φ( … )
```
Used in Stage 1 (`01_classical_gci_model.ipynb`), by `quantum_encoding.fit_linear_angle` (to fit Eq. 2), and by `postprocessing.classical_joint_probs` (the classical reference in Stage 9).

**Architecture** — first block of the **Finance branch** (Part A, top left).
- **Receives:** p₀, ρ from `config.py`.
- **Passes:** the PD(z) curve → Eq. 2.
- **Used again at the end:** Addition 7 and the Hellinger check compare the quantum result against this formula.

**Why this, not others**
- *Vasicek / GCI* is the basis of the **Basel IRB** capital formula and the paper's model. Alternatives — multi-factor models, t-copulas, CreditRisk+ — capture fatter tails but need more risk factors (more qubits) and are not what the paper tests.
- *One factor* keeps the circuit at 3–4 qubits, small enough to run with realistic noise on a laptop.

---

### 2.2 Eq. 10 and the z-grid — discretising the economy (Stage 1)

This block belongs to the loader branch in the diagram, but its code lives with Eq. 1, so it is explained here.

**Equation (paper Eq. 10)**

$$
z(b) = -z_{\max} + \frac{2 z_{\max}}{2^n - 1}\, b, \qquad
p^\star_b \propto \exp\!\left(-\frac{(z(b)-\mu)^2}{2\sigma^2}\right),\quad \mu=0,\ \sigma=1,\ z_{\max}=3
$$

**What it does:** an n-qubit register has 2ⁿ outcomes b = 0 … 2ⁿ−1. Each b is assigned one economy value z(b) between −3 and +3, and a target probability from the bell curve. 2 qubits → 4 bins at z = −3, −1, +1, +3. 3 qubits → 8 bins.

**Code** — `src/gci_model.py`
```python
def discretize_z(n_qubits, z_max=3.0):
    b = np.arange(2 ** n_qubits)
    return -z_max + (2 * z_max) * b / (2 ** n_qubits - 1)      # z(b)

def target_gaussian_histogram(n_qubits, z_max=3.0):
    z_grid = discretize_z(n_qubits, z_max)
    raw = np.exp(-(z_grid ** 2) / 2)                          # bell curve
    return z_grid, raw / raw.sum()                            # normalise → p*
```
The same file also builds the **classical baselines** used at the end:
- `discrete_grid_var` — "Method A": loss distribution on the same grid the circuit uses (paper-faithful).
- `monte_carlo_var` — "Method B": 2 million continuous Monte Carlo draws (an extra sanity check added in this project).

Result (Stage 1): P(L ≤ 0) ≈ 0.75, expected loss ≈ $250, VaR₀.₉₅ = $1000.

**Architecture** — first block of the **Loader branch** (Part A, top right).
- **Receives:** register size n, z_max.
- **Passes:** the target histogram p* → held until Eq. 11 (the dashed line on the right of the diagram).

**Why this, not others**
- *±3 standard deviations* cover 99.7 % of the normal distribution; a wider grid wastes bins on near-zero probabilities, a narrower one cuts off the recession tail that drives credit losses.
- *Evenly spaced grid* makes z(b) linear in b — which is exactly what makes Eq. 4 possible.

---

### 2.3 Eq. 2 and Eq. 3 — default probability as a qubit rotation

**Equations (paper Eq. 2, 3)**

$$
\mathrm{PD}(z) \equiv P_1 = \sin^2(\alpha z + \beta) \qquad\Longrightarrow\qquad R_y\big(2(\alpha z + \beta)\big)
$$

**What it does:** an Ry(2φ) rotation on |0⟩ gives P(1) = sin²φ exactly. If φ = αz + β, the probability of measuring |1⟩ on the asset qubit equals PD(z). So "the borrower defaults" ≡ "the asset qubit is measured as 1".

α and β are found by a straight-line fit of arcsin(√PD(z)) against z:
- α = −0.0605 rad (−3.47°), β = 0.524 rad (30.03°)
- maximum error of sin²(αz+β) vs Vasicek over [−3, 3]: **0.0065**, mean error **0.0025**

**Code** — `src/quantum_encoding.py → fit_linear_angle`
```python
z_fit = np.linspace(-z_max, z_max, n_fit_points)
theta_targets = np.arcsin(np.sqrt(pd_given_z(z_fit, p0, rho)))   # exact angle per z
alpha, beta = np.polyfit(z_fit, theta_targets, 1)                 # best straight line
pd_approx = np.sin(alpha * z_fit + beta) ** 2                     # check the fit
```
Stage 2 notebook: `02_quantum_encoding.ipynb`; figure `stage02_quantum_encoding_fit_validation.png`.

**Architecture** — Finance branch, blocks 2 and 3.
- **Receives:** the PD(z) curve from Eq. 1.
- **Passes:** α, β → the rotation angle 2(αz + β) → Eq. 4.

**Why this, not others**
- *Exact angle per bin* (arcsin √PD(z_b) for each b separately) would be perfectly accurate but needs a multi-controlled rotation for **every** bin — 2ⁿ expensive gates. The linear form needs only **n + 1** simple gates (see Eq. 4).
- *Higher-order fits* (quadratic in z) would need products of qubits — more two-qubit gates, more noise. The linear error (< 0.007) is already far below hardware noise.
- *Ry* (not Rx or Rz) because Ry keeps amplitudes real and directly sets P(1) = sin².

---

### 2.4 Eq. 4 — register-indexed asset gates

**Equation (paper Eq. 4)**

$$
R_y\big(2(\tilde\alpha\,b + \tilde\beta)\big), \qquad \tilde\alpha = \alpha\cdot\frac{2z_{\max}}{2^n-1}, \qquad \tilde\beta = \beta - \alpha z_{\max}
$$

**What it does:** the circuit holds the bin index b, not z. Substituting z(b) into αz + β gives α̃b + β̃. Since b is written in binary, b = Σₖ 2ᵏ qₖ, the angle splits into:
- one plain rotation **Ry(2β̃)** on the asset qubit (the baseline), plus
- one **controlled-Ry(2α̃·2ᵏ)** per z-qubit k (adds the z-dependent part only when that bit is 1).

Values: β̃ = 40.42° for both registers; α̃ = −6.93° (2-qubit), −2.97° (3-qubit).

**Code** — `src/quantum_encoding.py → register_adapted_params`
```python
slope = (2 * z_max) / (2 ** n_qubits - 1)
alpha_tilde = alpha * slope
beta_tilde = beta - alpha * z_max
```
and the gates themselves — `src/vqc_circuit.py → build_gci_circuit` (Stage 3):
```python
qc.ry(2 * beta_tilde, asset_qubit)                       # baseline rotation
for k in range(n_z_qubits):
    qc.cry(2 * alpha_tilde * (2 ** k), k, asset_qubit)   # one controlled-Ry per bit
```

**Architecture** — last block of the Finance branch.
- **Receives:** α, β (Eq. 3).
- **Passes:** the asset-qubit gates (α̃, β̃) → **FULL GCI CIRCUIT**.

**Why this, not others**
- *Binary decomposition* gives n + 1 gates. A lookup-table approach (one multi-controlled rotation per bin) gives 2ⁿ gates, each needing many CNOTs after transpilation.
- *Controlled on the basis bits* means there is no interference: P(default, z_b) = P(z_b)·PD(z_b) exactly. The asset qubit cannot disturb the economy distribution.

---

## §3 Part A — Loader branch (Eq. 5–13, training)

> **Flow of this branch:** Eq. 10 (target) · Eq. 5 → Eq. 6 → Eq. 12–13 → Eq. 8–9 → Eq. 11 → parameter shift → Adam → trained angles θ*.
> It trains the z-register so that measuring it gives the economy's bell curve.

### 3.1 Eq. 5 — how many qubits

**Equation (paper Eq. 5)**

$$
N_{\text{qubits}} = N_{\text{assets}} + \sum_{k=1}^{N_{\text{risk}}} n_k
$$

**What it does:** one qubit per asset plus nₖ qubits per risk factor. Here: 1 asset + one factor with n = 2 or 3 → **3 or 4 qubits**. For 2 assets and 2 factors it would be at least 6.

**Code** — `src/vqc_circuit.py → build_gci_circuit`
```python
n_total = n_z_qubits + 1        # Eq. 5 with one asset
asset_qubit = n_z_qubits        # the asset is the highest-index qubit
```
The register sizes studied are set in `src/config.py → REGISTER_SIZES = (2, 3)`.

**Architecture** — Loader branch, block 2. **Passes:** register size (n + 1 qubits) → Eq. 6.

**Why 2 and 3 qubits:** 2 is the paper's hardware case; 3 tests whether the methods scale and needs no more than a laptop. More bins give a finer economy but deeper circuits — more noise.

---

### 3.2 Eq. 6 — the state the loader must prepare

**Equation (paper Eq. 6)**

$$
|\psi(\theta)\rangle = \sum_{b=0}^{2^n-1} \sqrt{p_b(\theta)}\;|b\rangle
$$

**What it does:** defines the goal. Measuring returns b with probability |amplitude|² = p_b. So the amplitudes must be the **square roots** of the bin probabilities.

**Code** — no single line "implements" a goal; it is realised by the ansatz in §3.3 and checked by `training.probabilities_from_theta` (§3.4).

**Architecture** — Loader branch, block 3. **Passes:** the goal state → Eq. 12–13 (the gates that build it).

---

### 3.3 Eq. 12 and Eq. 13 — the loader ansatz (Ry + CNOT)

**Equations (paper Eq. 12, 13)**

$$
R_Y(\theta) = \begin{bmatrix}\cos\frac{\theta}{2} & -\sin\frac{\theta}{2}\\ \sin\frac{\theta}{2} & \cos\frac{\theta}{2}\end{bmatrix}
$$

After Ry(θ₀) ⊗ Ry(θ₁) on |00⟩, the amplitudes are [c₀c₁, c₀s₁, s₀c₁, s₀s₁] (c = cos(θ/2), s = sin(θ/2)). The CNOT(0 → 1) then **swaps the |10⟩ and |11⟩ amplitudes** (Eq. 13): [c₀c₁, c₀s₁, s₀s₁, s₀c₁]. With θ₀ = 90° this gives a symmetric distribution that, for the right θ₁, is bell-shaped: small at |00⟩ and |11⟩, large at |01⟩ and |10⟩.

For 3 qubits (paper Fig. 3): add Ry(θ₂) on qubit 2 and a second CNOT(0 → 2) — the **star** entangler.

**Code** — `src/vqc_circuit.py → build_ansatz`
```python
thetas = [Parameter(f"theta_{i}") for i in range(n_z_qubits)]
for i in range(n_z_qubits):
    qc.ry(thetas[i], i)                  # Eq. 12 on every qubit
if entangler == "star":
    for i in range(1, n_z_qubits):
        qc.cx(0, i)                      # Eq. 13: CNOT from qubit 0 to each other qubit
```
Figures: `stage03_circuit_2q_register.png`, `stage03_circuit_3q_register.png`.

**Architecture** — Loader branch, block 4 ("Eq. 12, 13 – Ry matrix + CNOT").
- **Passes:** amplitudes as functions of θ → Eq. 8–9.
- **Side output:** the same amplitude formulas are analysed in Eq. 14–17 (§4.1).

**Why this, not others**
- *Ry only* — real amplitudes are enough for a probability distribution; Rx/Rz would add complex phases that do nothing for the histogram.
- *Star vs chain entangler* — the star is the **paper's** design (Figs. 1–3), so it is kept for a faithful replication. Stage 4 also tried a **chain** (CNOT 0→1, 1→2): for 3 qubits the chain reaches a lower loss (0.0018 vs 0.0488). The star's 3-parameter, symmetric form caps the 3-qubit fidelity at ≈ 0.78 against the ideal Gaussian. This is reported as a limitation and future work.
- *Shallow (one layer)* — every extra layer adds CNOTs, and CNOTs are the noisiest gates on NISQ hardware.

---

### 3.4 Eq. 8 and Eq. 9 — the circuit's histogram

**Equations (paper Eq. 8, 9)**

$$
p_b(\theta) = \big|\langle b \mid \psi(\theta)\rangle\big|^2, \qquad b \in \{0,\dots,3\}\ \text{(2 qubits)},\ \{0,\dots,7\}\ \text{(3 qubits)}
$$

**What it does:** gives the output histogram the circuit produces for any choice of angles.

**Code** — `src/training.py → probabilities_from_theta`
```python
qc, thetas = build_ansatz(n_z_qubits, entangler=entangler)
bound = qc.assign_parameters(dict(zip(thetas, theta_values)))   # put numbers into θ
return Statevector.from_instruction(bound).probabilities()      # |⟨b|ψ⟩|² for every b
```

**Architecture** — Loader branch, block 5 ("Circuit histogram"). **Passes:** p(θ) → Eq. 11.

**Why exact statevector, not shots:** training happens on a perfect simulator (as in the paper). Exact probabilities remove shot noise, so the optimiser sees the true loss. Shots and noise come later, in Part B.

---

### 3.5 Eq. 11 — the training loss

**Equation (paper Eq. 11)**

$$
\mathcal{L}(\theta) = \sum_{b=0}^{2^n-1} \big(p_b(\theta) - p^\star_b\big)^2
$$

**What it does:** one number measuring how far the circuit's histogram (Eq. 8–9) is from the target bell curve (Eq. 10). Training makes it small.

**Code** — `src/parameter_shift.py → mse_loss`
```python
def mse_loss(p, target):
    return float(np.sum((p - target) ** 2))
```

**Architecture** — Loader branch, block 6 ("MSE loss"). This is where the **two inputs meet**: p(θ) from Eq. 8–9 and p* from Eq. 10 (the dashed arrow). **Passes:** the loss → parameter-shift gradient.

**Why MSE, not KL divergence or Hellinger:** it is the paper's choice; it has simple, smooth gradients and is never infinite (KL blows up when a bin is 0). Hellinger is used later for *evaluation*, where the paper reports it.

---

### 3.6 Parameter-shift rule — exact quantum gradients

**Equation (paper, unnumbered; derived in `00_overview.ipynb`)**

$$
\frac{\partial p_b}{\partial \theta_i} = \frac{p_b(\theta_i + \tfrac{\pi}{2}) - p_b(\theta_i - \tfrac{\pi}{2})}{2},
\qquad
\frac{\partial \mathcal{L}}{\partial \theta_i} = \sum_b 2\,(p_b - p^\star_b)\,\frac{\partial p_b}{\partial \theta_i}
$$

**What it does:** gives the **exact** derivative of the loss for each angle, using the circuit itself evaluated at two shifted angles. The second formula is the chain rule applied to Eq. 11.

**Code** — `src/parameter_shift.py → gradient`
```python
for i in range(n_params):
    shifted_plus  = theta.copy(); shifted_plus[i]  += np.pi / 2
    shifted_minus = theta.copy(); shifted_minus[i] -= np.pi / 2
    dp_dtheta_i = (prob_fn(shifted_plus) - prob_fn(shifted_minus)) / 2   # shift rule
    grad[i] = np.sum(2 * (p_current - target) * dp_dtheta_i)            # chain rule on Eq. 11
```
`00_overview.ipynb` verifies it against finite differences (`stage00_parameter_shift_verification.png`).

**Architecture** — Loader branch, block 7. **Passes:** gradients ∂L/∂θ → Adam.

**Why this, not others**
- *Backpropagation* is impossible through a real quantum device — you only see measurement results.
- *Finite differences* (shift by a tiny ε) are only approximate and, with shot noise, very noisy because the difference is tiny. The shift rule uses a large π/2 shift and is **exact** for rotation gates.
- Cost: 2 circuit runs per parameter per step — fine for 2–3 parameters.

---

### 3.7 Adam — the optimiser

**Equation (paper, unnumbered; ref. 28)**

$$
m \leftarrow \beta_1 m + (1-\beta_1) g,\quad v \leftarrow \beta_2 v + (1-\beta_2) g^2,\quad
\hat m = \frac{m}{1-\beta_1^t},\ \hat v = \frac{v}{1-\beta_2^t},\quad
\theta \leftarrow \theta - \eta\,\frac{\hat m}{\sqrt{\hat v} + \epsilon}
$$

**What it does:** moves the angles downhill. m is a running average of the gradient (momentum), v a running average of its square (per-parameter step-size scaling); the hats correct the bias from starting at zero.

**Code** — `src/adam.py → AdamOptimizer.step`
```python
self.m = self.beta1 * self.m + (1 - self.beta1) * grad
self.v = self.beta2 * self.v + (1 - self.beta2) * grad ** 2
m_hat = self.m / (1 - self.beta1 ** self.t)
v_hat = self.v / (1 - self.beta2 ** self.t)
return theta - self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
```
Settings: η = 0.15, β₁ = 0.9, β₂ = 0.999, 150 iterations. `00_overview.ipynb` demonstrates it on a toy problem (`stage00_adam_training_demo.png`).

**Architecture** — Loader branch, last block. **Passes:** trained angles θ* → **FULL GCI CIRCUIT**.

**Why this, not others:** the paper chose Adam (citing a comparison of optimisers for variational algorithms). Plain gradient descent needs a hand-tuned step size and oscillates; derivative-free methods (COBYLA, Nelder-Mead) ignore the exact gradients already available.

---

### 3.8 The training loop that ties §3.4–3.7 together

**Code** — `src/training.py → train_gaussian_loader`
```python
theta = rng.uniform(0, np.pi, size=n_z_qubits)            # random start
optimizer = AdamOptimizer(n_params=n_z_qubits, lr=lr)
for _ in range(n_iterations):
    grad, p_current = gradient(prob_fn, theta, target)    # §3.6 (uses §3.4)
    loss_history.append(mse_loss(p_current, target))      # §3.5
    theta = optimizer.step(theta, grad)                   # §3.7
```

**Result (Stage 4, `04_classical_training.ipynb`):**
| Register | Trained angles θ* | Final loss | Note |
|---|---|---|---|
| 2-qubit | 90.0°, 195.4° | 2 × 10⁻⁸ | reproduces the 4-bin Gaussian essentially exactly |
| 3-qubit (star) | 90.0°, 55.0°, 131.0° | 0.049 | ansatz expressivity limit (≈ 0.78 Hellinger fidelity vs ideal Gaussian) |
| 3-qubit (chain, comparison only) | 90.0°, 70.1°, 208.7° | 0.0018 | better, but not the paper's design |

Saved to `results/trained_parameters.json`. Figures: `stage04_training_convergence.png`, `stage04_topology_comparison.png`.

---

## §4 Part A — Full circuit and transpilation

### 4.1 Eq. 14–17 — symmetry conditions (side branch)

**Equations (paper Eq. 14–17)**

$$
\theta_0 = \pm\frac{(2n_0+1)\pi}{2}, \qquad \frac{\pi}{2} < \theta_1 < \frac{3\pi}{2}\ \ \text{(Eq. 15)}, \qquad \theta_2 = 2\pi n_2 \pm \theta_1\ \ \text{(Eq. 16)}, \qquad \frac{\pi}{2} < \theta_2 < \frac{5\pi}{2}\ \ \text{(Eq. 17)}
$$

**What it does:** from the amplitude formulas of Eq. 12–13, these say *which* angles give a symmetric bell (P₀₀ = P₁₁, P₀₁ = P₁₀, centre heavier than edges). θ₀ = 90° gives the symmetry; θ₁ in (90°, 270°) gives the bell; θ₁ near 90°/270°/450° gives a flat distribution; outside, the shape is inverted. That is why the paper fixes θ₀ = 90° and sweeps θ₁ from 90° to 450°.

**Code** — not a function of its own: the conditions become the **6A sweep ranges** in `src/stages.py → paper_grid_loader`:
```python
if n == 2:                                    # Eq. 15 range, paper's 21° then 1° steps
    return grid_sweep(dev, ref, x_nom, [1], [D(np.arange(90, 451, 21))], [D(21)], [D(1)], ...)
return grid_sweep(dev, ref, x_nom, [1, 2],    # Eq. 15 + 17 ranges, 36° then 7.5° / 14.5°
                  [D(np.arange(90, 451, 36)), D(np.arange(90, 451, 36))], ...)
```
Figure: `stage06_theta1_sweep_2q.png` reproduces the paper's Fig. 5 (periodic concave → flat → inverted pattern).

**Architecture** — dashed **side branch** at the start of Part C. **Receives:** amplitude formulas (Eq. 12–13). **Passes:** search ranges → **6A only**. Not used by 6B or by any other block.

**Why only a side branch:** the conditions are a guide for a human sweeping angles by hand. The automated 6B does not need them — it searches ±45° around the trained angles and lets the data decide.

---

### 4.2 FULL GCI CIRCUIT — where the two branches meet

**No new equation** — this block **composes** the loader (θ*, Eq. 6/12/13) and the asset gates (Eq. 4).

**What it does:** one circuit on n + 1 qubits. Each shot produces one bitstring = one correlated scenario: the **right n bits** are the economy bin b, the **left bit** is default (1) or not (0). Because the asset rotations are controlled on the z-bits, P(default, z_b) = P(z_b)·PD(z_b).

**Code** — two versions with the same structure:
- `src/vqc_circuit.py → build_gci_circuit` (Stage 3): loader angles are parameters, asset angles are numbers.
- `src/transpilation.py → build_param_circuit` (Stage 6 onward): **asset angles are parameters too**, because calibration has to tune them.
```python
for i in range(n):
    qc.ry(params[i], i)                         # loader Ry(θ_i)
for i in range(1, n):
    qc.cx(0, i)                                 # star CNOTs
if kind == "gci":
    beta_t, alpha_t = params[n], params[n + 1]
    qc.ry(2 * beta_t, asset)                    # Eq. 4 baseline
    for k in range(n):
        qc.cry(2 * alpha_t * (2 ** k), k, asset)   # Eq. 4 slope
```
The parameter vector used everywhere from Stage 6 on is **x = [θ₀ … θₙ₋₁, β̃, α̃]** — called the *commanded angles*. Its nominal value (trained θ* + fitted α̃, β̃) comes from `src/pipeline_io.py → nominal_parameters`.

**Architecture** — the beige **FULL GCI CIRCUIT** box. **Receives:** asset gates (Finance branch) + θ* (Loader branch). **Passes:** the logical circuit → SABRE.

**Why rebuild it in `transpilation.py`:** the Stage 3 version bakes α̃, β̃ in as fixed numbers. Calibration must be able to change them, so Stage 6 needs them as symbolic Parameters. It also allows the circuit to be transpiled **once** and only re-bind numbers thousands of times.

---

### 4.3 SABRE transpilation

**No equation** — a routing algorithm (paper, unnumbered; ref. 38).

**What it does:** real chips (1) only run a few **native gates** — here `rz`, `sx`, `x`, `cz` — and (2) only let **neighbouring** qubits interact. Transpilation rewrites every Ry, CNOT and controlled-Ry into native gates and inserts SWAPs where non-neighbours must interact. **SABRE** (SWAP-based Bidirectional heuristic search) chooses the qubit placement and SWAPs that keep the circuit shortest.

**Code** — `src/transpilation.py → transpile_for_device`
```python
return transpile(qc, coupling_map=coupling_map(n), basis_gates=NATIVE_GATES,
                 initial_layout=initial_layout,
                 layout_method=None if initial_layout else "sabre", routing_method="sabre",
                 optimization_level=OPTIMIZATION_LEVEL, seed_transpiler=SEED_TRANSPILER)
```
Settings in `src/config.py`: `NATIVE_GATES = ["rz", "sx", "x", "cz"]`, linear coupling maps (`COUPLING_EDGES`), optimisation level 1, seed 7.
`logical_to_physical` reads which physical qubit each logical qubit landed on — needed because the drift (§5) is different per physical qubit.
Narrated in `05_transpilation.ipynb`; headless in `scripts/run_stage05_transpilation.py`.

**Result:**
| Register | Depth | CZ gates (decomposition only → with routing) |
|---|---|---|
| 2-qubit | 6 → 33 | 5 → 8 |
| 3-qubit | 8 → 56 | 8 → 14 |

**Architecture** — last block of Part A. **Receives:** the logical circuit. **Passes:** the hardware circuit → Addition 1.

**Why this, not others**
- *CZ as the two-qubit gate* — the paper's chip uses CZ.
- *Linear coupling map* — the most restrictive common topology, so connectivity costs are visible.
- *SABRE vs trivial layout* — a trivial layout ignores connectivity and needs more SWAPs; SABRE is the paper's choice and Qiskit's default heuristic.
- **Key insight:** transpilation optimises *structure* only. It knows nothing about how noisy each gate is — which is exactly why Part B and C exist.

---

## §5 Part B — The noisy device

> **Flow:** hardware circuit → Addition 1 (noisy device) → measured distribution → Addition 2 (objective) → the number calibration minimises.

### 5.1 Addition 1 — the noise-emulated device

**Equations (this project's addition; models the paper's Sec. V error sources)**

$$
\text{Depolarizing: } \rho \to (1-p)\,\rho + p\,\frac{I}{d}, \qquad
\text{Readout: } \begin{bmatrix}1-p_{01} & p_{01}\\ p_{10} & 1-p_{10}\end{bmatrix}, \qquad
\text{Drift: } \theta_{\text{real}} = (1+\varepsilon_q)\,\theta + \delta_q
$$

| Error | Value | What it does physically |
|---|---|---|
| Depolarizing | p = 0.2 % on `sx`, `x`; 1.5 % on `cz`; `rz` error-free (virtual) | gates slowly randomise the state |
| Readout | 2–7 % per physical qubit, P(1→0) > P(0→1) | measurement misreads bits (decay during readout) |
| Drift | ε up to ±14 %, δ up to ±15°, different per physical qubit | pulses over/under-rotate every Ry |

**What it does:** turns the ideal circuit into a realistic noisy one. Its output depends on the commanded angles x, but the chip applies distorted angles. The drift values are **hidden**: no calibration method reads them.

**Code**
`src/noise_model.py → build_noise_model` (incoherent noise):
```python
nm.add_all_qubit_quantum_error(depolarizing_error(depol_1q, 1), ["sx", "x"])
nm.add_all_qubit_quantum_error(depolarizing_error(depol_2q, 2), ["cz"])
for q in range(n_physical):
    p01, p10 = readout_errors[q]
    nm.add_readout_error(ReadoutError([[1 - p01, p01], [p10, 1 - p10]]), [q])
```
`src/noise_model.py → ControlDrift.realise` (coherent drift):
```python
x[i] = (1 + self.eps[q]) * x[i] + self.delta[q]              # loader angle on physical qubit q
x[n] = (1 + self.eps[qa]) * x[n] + self.delta[qa] / 2        # asset baseline (offset on 2β̃)
x[n + 1] = (1 + self.eps[qa]) * x[n + 1]                     # asset slope: scale only
```
`src/device.py → NoisyDevice` bundles it all into "the chip":
```python
def bound_circuit(self, x):
    realised = self.drift.realise(x, self.n, self.kind, self.phys)   # chip distorts angles
    return self.tqc.assign_parameters(dict(zip(self.params, realised)))

def run(self, x, shots, seed=None):          # angles in → measured histogram out
    return self.run_circuit(self.bound_circuit(x), shots, seed)

def ideal_probs(self, x):                    # noiseless, drift-free reference
    return Statevector.from_instruction(qc_bound).probabilities()
```
It also counts circuit runs and shots (`n_evals`, `n_shots`) — the cost axis of the 6A vs 6B comparison.

**Result:** the trained angles drop from fidelity 1.00 to **0.88 / 0.92** (raw, 2q / 3q). Figure: `stage06_problem_uncalibrated.png`.

**Architecture** — Part B, Addition 1. **Receives:** hardware circuit (SABRE) + commanded angles. **Passes:** measured distribution p_dev(x) → Addition 2.

**Why this, not others**
- *Emulated chip vs real IBM hardware:* reproducible, free, unlimited runs, and the same three error sources the paper names. A real device is listed as future work; the calibration code would run unchanged against it because it only needs counts.
- *Drift on commanded angles:* the paper's chip sets rotation angles by pulse amplitude, so an amplitude error is literally a scale error ε on θ. It is the error the paper's manual retuning fixes, so it must be present for calibration to mean anything.
- *Qiskit's built-in "fake" backends* contain depolarizing and readout noise but no hidden drift, so retuning would have little to fix.

---

### 5.2 Addition 2 — the calibration objective

**Equation (this project's addition)**

$$
J(x) = H\big(p_{\text{dev}}(x),\ p_{\text{ref}}\big), \qquad H(p,q) = \sqrt{1 - \sum_i \sqrt{p_i\, q_i}}, \qquad F_H = (1 - H^2)^2
$$

- **p_dev(x)** — device histogram at commanded angles x, from 4 000 shots, readout-corrected.
- **p_ref** — noiseless output of the trained circuit (the paper's "simulated transpiled circuit", Fig. 10a).
- **H** — Hellinger distance (0 = identical); **F_H** — Hellinger fidelity (1 = identical), the paper's metric.

**What it does:** turns "does the output look right?" into one number an algorithm can minimise.

**Code**
`src/metrics.py`:
```python
def bhattacharyya(p, q):       return float(np.sum(np.sqrt(_clean(p) * _clean(q))))
def hellinger_distance(p, q):  return float(np.sqrt(max(0.0, 1.0 - bhattacharyya(p, q))))
def hellinger_fidelity(p, q):  return float(bhattacharyya(p, q) ** 2)
```
`src/calibration.py → objective`:
```python
def objective(device, reference, x, shots):
    return hellinger_distance(device.run(x, shots), reference)
```
`src/mitigation.py → ReadoutMitigatedDevice` makes calibration **mitigation-aware**: every histogram the optimiser sees is readout-corrected first.
```python
def run(self, x, shots, seed=None):
    return apply_readout_mitigation(self.device.run(x, shots, seed), self.A)
```
`src/metrics.py → counts_to_probs` converts Qiskit's count dictionaries into probability vectors.

**Architecture** — Part B, Addition 2. **Receives:** p_dev(x). **Passes:** the number to minimise → **both** 6A and 6B ("J(x) feeds BOTH methods").

**Why this, not others**
- *Hellinger vs KL divergence:* KL is infinite when a bin is empty — common with shots. Hellinger is bounded and symmetric.
- *Hellinger vs total variation:* both work; Hellinger is the paper's reporting metric, so optimising it makes results directly comparable.
- *Readout-corrected data:* if angles were tuned on raw counts, they would partly absorb the readout error — and readout mitigation (Stage 7) would then correct it a second time.

---

## §6 Part C — Calibration (6A vs 6B)

> **Flow:** J(x) → **6A** (paper) and **6B** (ours), side by side → calibrated angles x*.
> Both receive the same objective; they differ only in **how they search**.

### 6.1 6A — the paper's grid sweep

**Procedure (paper Sec. IV-A, IV-B, IV-C / Table 3)** — evaluate J on a grid, keep the minimum, then a finer grid around it.

| Circuit | Swept | Coarse | Fine |
|---|---|---|---|
| 2-qubit loader | θ₁ (θ₀ fixed) | 90°–450°, 21° | ±21°, 1° |
| 3-qubit loader | θ₁, θ₂ (θ₀ fixed) | 90°–450°, 36° each | ±36° 7.5° / ±43.5° 14.5° |
| full circuit | 2β̃, 2α̃ (loader angles from the loader sweep) | ±60° 10° / ±15° 3° | ±10° 2° / ±3° 0.5° |

**Code** — `src/calibration.py → grid_sweep`
```python
xs_c, d_c, pts_c = evaluate(coarse_axes)                     # coarse grid
best_c = xs_c[int(np.argmin(d_c))]
fine_axes = [np.arange(best_c[i] - hw, best_c[i] + hw + 1e-9, st)
             for i, hw, st in zip(indices, fine_half_widths, fine_steps)]
xs_f, d_f, pts_f = evaluate(fine_axes)                       # fine grid around the best
x_best = xs_f[int(np.argmin(d_f))]
```
The paper's exact ranges are set in `src/stages.py → paper_grid_loader` and `paper_grid_gci`.

**Result:** F_H = **0.939 / 0.957** using **347 / 477** circuit runs (2q / 3q). Cross-check: the 2-qubit sweep moves θ₁ from 195° to ≈ 234° — the paper measured 237° and 224° on its real qubit pairs. Figures: `stage06_asset_landscape.png` (the paper's Table 3 as a heat-map), `stage06_loader_landscape_3q.png`.

**Architecture** — Part C, left box "6A – paper – GRID SWEEP". **Receives:** J(x) + Eq. 14–17 ranges. **Passes:** calibrated angles x* (6A version).

**Why it falls short:** θ₀ is never tuned, so drift on the first qubit can never be corrected; and the number of grid points grows exponentially with the number of angles.

---

### 6.2 Addition 3 — 6B automated calibration

6B has three ingredients: Bayesian optimisation, SPSA, and the procedure that combines them.

#### (a) Bayesian optimisation (BO)

**Equations (this project's addition)**

Gaussian process with an RBF kernel on inputs scaled to [0, 1]ᵈ:
$$
k(u, u') = \exp\!\left(-\frac{\lVert u - u'\rVert^2}{2\ell^2}\right), \qquad
\mu(u) = k_*^{\top}(K + \sigma_n^2 I)^{-1} y, \qquad
\sigma^2(u) = 1 - k_*^{\top}(K + \sigma_n^2 I)^{-1} k_*
$$
Expected Improvement (choose the next point to measure):
$$
\mathrm{EI}(u) = (J^* - \mu - \xi)\,\Phi(z) + \sigma\,\varphi(z), \qquad z = \frac{J^* - \mu - \xi}{\sigma}
$$

**What it does:** builds a smooth model of J from every point measured so far — a prediction μ and an uncertainty σ everywhere — and measures next where improvement is most likely: low predicted J (exploit) or high uncertainty (explore).

**Code** — `src/calibration.py → _GP` and `bayesian_opt`
```python
class _GP:
    def fit(self, X, y):            # picks length-scale ℓ and noise by max marginal likelihood
    def predict(self, Xs):          # returns μ and σ (Cholesky solve)

# inside bayesian_opt:
gp.fit(U, y)
m, s = gp.predict(cand)                                   # cand = 4000 candidate points
imp = y.min() - m - xi * gp.sd
z = imp / s
ei = imp * _norm.cdf(z) + s * _norm.pdf(z)                # Expected Improvement
u_next = cand[int(np.argmax(ei))]                         # measure the best candidate next
```
Starts from the nominal point plus a Latin-hypercube design; the final answer is the evaluated point with the lowest **posterior mean** (robust to one lucky shot-noise draw). Written in NumPy from scratch so every step is visible.

#### (b) SPSA — Simultaneous Perturbation Stochastic Approximation

**Equations (this project's addition)**
$$
\hat g_k = \frac{J(x_k + c_k\Delta_k) - J(x_k - c_k\Delta_k)}{2c_k}\,\Delta_k,\quad \Delta_{k,i} \in \{-1, +1\},
\qquad x_{k+1} = x_k - a_k\,\hat g_k
$$
$$
a_k = \frac{a}{(k+1+A)^{0.602}}, \qquad c_k = \frac{c}{(k+1)^{0.101}}
$$

**What it does:** estimates the **whole** gradient from **two** measurements per step, whatever the number of angles, by perturbing all angles at once in random ± directions.

**Code** — `src/calibration.py → spsa`
```python
delta = rng.choice([-1.0, 1.0], size=d)                    # random ± direction
jp = objective(device, reference, x + ck * delta, shots)
jm = objective(device, reference, x - ck * delta, shots)
ghat = (jp - jm) / (2 * ck) * delta                        # gradient estimate
x = x - ak * ghat                                          # step
```
The gain a is set automatically so the first step moves the angles by ≈ 0.15 rad; the answer is the average of the last 25 % of iterates (averages out shot-noise jitter).

#### (c) The 6B procedure — hierarchical BO → BO → SPSA → verify

**Code** — `src/calibration.py → hierarchical_calibration` (with `SubspaceDevice` exposing only some angles to an optimiser)
```python
# Step 1 — BO on loader angles, stand-alone loader circuit, same physical qubits (40 runs)
loader_result = bayesian_opt(loader_dev, loader_ref, x_start[:n], shots, budget=loader_budget, ...)
# Step 2 — BO on the two asset angles, full circuit, loader frozen (30 runs)
sub = SubspaceDevice(gci_dev, x1, [n, n + 1])
r2 = bayesian_opt(sub, gci_ref, x1[[n, n + 1]], shots, budget=asset_budget, ...)
# Step 3 — SPSA refinement of ALL angles together (60 iterations)
r3 = spsa(gci_dev, gci_ref, x2, shots, n_iter=refine_iter, c=0.06, target_first_step=0.05)
# Step 4 — verification: re-measure both candidates with 4× shots, keep the better
x_best = r3.x_best if f3 >= f2 else x2
```
Orchestrated per register by `src/stages.py → stage06_loader` and `stage06_gci`, which also run the **ablations** (one SPSA, one BO on all angles at once). Narrated in `06_hardware_retuning.ipynb`; headless in `scripts/run_stage06_hardware_retuning.py`. Output: `results/stage06_retuning.json`.

**Result (full GCI circuit):**
| Register | Method | Circuit runs | F_H |
|---|---|---|---|
| 2-qubit | uncalibrated | 0 | 0.923 |
| 2-qubit | 6A grid | 347 | 0.939 |
| 2-qubit | **6B automated** | **204** | **0.982** |
| 2-qubit | ablation: joint SPSA / joint BO | 308 / 70 | 0.982 / 0.973 |
| 3-qubit | uncalibrated | 0 | 0.910 |
| 3-qubit | 6A grid | 477 | 0.957 |
| 3-qubit | **6B automated** | **204** | **0.994** |
| 3-qubit | ablation: joint SPSA / joint BO | 308 / 70 | 0.947 / 0.964 |

Figures: `stage06_convergence_gci.png` (key novelty figure), `stage06_cost_vs_quality.png`, `stage06_gci_distributions.png`.

**Architecture** — Part C, right box "6B – ADDITION 3". **Receives:** J(x); when called from the closed loop, also the current angles as a starting point (the arrow coming back from RE-CALIBRATE). **Passes:** calibrated angles x* (6B version).

**Why this, not others**
- *Grid search:* cost explodes with the number of angles (that is 6A).
- *Random search:* no learning from past points.
- *Parameter-shift on the device:* 2 runs **per angle** per step, and the gradient is noisy with shots; SPSA needs 2 runs per step in total.
- *Nelder-Mead / COBYLA:* sensitive to shot noise, many evaluations in 4–5 dimensions.
- *BO alone* plateaus (0.964 for 3q); *SPSA alone* from a poor start converges slowly (0.947 for 3q). **BO places the angles globally with few runs; SPSA refines them locally** — together 0.994.
- *Hierarchical (loader first, then asset)* mirrors the paper's own workflow and splits a 5-D problem into 3-D + 2-D problems that BO handles well.

---

### 6.3 CALIBRATED ANGLES x*

**No equation** — the output of calibration.

**What it does:** the angles actually sent to the device from now on. Three sets are saved for comparison: **uncalibrated** (trained, as-is), **grid_6A**, **auto_6B**.

**Code** — `src/stages.py → stage06_gci` builds the dictionary, `save_stage06` writes it to `results/stage06_retuning.json`:
```python
params = {"uncalibrated": x0.tolist(), "grid_6A": np.asarray(g.x_best).tolist(),
          "auto_6B": np.asarray(h.x_best).tolist()}
```

**Architecture** — beige box "CALIBRATED ANGLES x*". **Passes:** → Addition 4 (execution).

---

## §7 Part D — Execution and mitigation

> **Flow:** x* → Addition 4 (repeated execution) → Addition 5 (readout mitigation) → [optional Addition 6, ZNE] → corrected distribution.

### 7.1 Addition 4 — repeated execution

**Statistics (this project's addition)** — each variant is run **20 independent times × 20 000 shots**; report the mean and standard deviation. Shot noise on a probability near 0.25 is √(p(1−p)/N) ≈ 0.3 % at 20 000 shots.

**What it does:** turns single numbers into numbers with error bars, so "6B beats 6A" is statistically demonstrated.

**Code** — `src/stages.py → execute_variants`, settings `N_REPEATS = 20`, `SHOTS_EXECUTION = 20000` in `src/config.py`.
```python
for r in range(n_repeats):
    s = seed0 + 1000 * r                                   # independent seed per repetition
    p_unc = dev.run(x_unc, shots, seed=s)
    runs["noisy_uncalibrated"].append(p_unc)
    runs["uncalibrated_REM"].append(apply_readout_mitigation(p_unc, A))
    runs["6A_grid_REM"].append(apply_readout_mitigation(dev.run(x_6a, shots, seed=s + 1), A))
    runs["6B_auto_REM"].append(apply_readout_mitigation(dev.run(x_6b, shots, seed=s + 2), A))
    runs["6B_auto_REM_ZNE"].append(run_zne(dev, x_6b, shots, ..., readout_A=A)[0])
```
The six variants are listed in `VARIANT_DESCRIPTIONS`. Narrated in `07_run_on_backend.ipynb`; output `results/stage07_execution.json`.

**Architecture** — Part D, Addition 4. **Receives:** x*. **Passes:** raw measured histograms → Addition 5.

**Why 20 × 20 000:** large enough to resolve the small ZNE gains (≈ 0.001–0.016); the whole stage still runs in ~15 s. The paper used 100 hardware repetitions — on a simulator, 20 already give stable error bars.

---

### 7.2 Addition 5 — readout error mitigation (REM)

**Equation (this project's addition)**

$$
A_{is} = P(\text{read } i \mid \text{prepared } s), \qquad \mathbf{m} \approx A\,\mathbf{p}_{\text{true}}, \qquad
\hat{\mathbf p} = \arg\min_{\mathbf p \ge 0}\ \lVert A\mathbf p - \mathbf m\rVert_2 \ \ (\text{then normalise})
$$

**What it does:** measures how the readout scrambles every basis state, then "un-scrambles" measured histograms.

**Code** — `src/mitigation.py`
```python
def assignment_matrix(device, shots=20000, seed=77):
    for s in range(2 ** n_bits):                    # prepare every basis state |s⟩
        for q_phys, c in meas:
            if (s >> c) & 1:
                qc.x(q_phys)                         # on the SAME physical qubits the circuit uses
        ...
    A = np.column_stack([...])                       # column s = what |s⟩ is read as

def apply_readout_mitigation(p_measured, A):
    p, _ = nnls(A, np.asarray(p_measured, dtype=float))   # non-negative least squares
    return p / p.sum()
```
`split_measurements` finds which physical qubit each classical bit is measured from. Figure: `stage07_assignment_matrices.png`.

**Result:** on its own it cannot fix drift (uncalibrated + REM: 0.92 / 0.91); after 6B retuning: **0.982 / 0.995**.

**Architecture** — Part D, Addition 5. **Receives:** raw histograms. **Passes:** readout-corrected distribution → ZNE (optional) or straight to the corrected distribution (deployed pipeline — the dashed bypass in the diagram).

**Why this, not others**
- *Plain inverse A⁻¹m* can give negative "probabilities"; NNLS keeps a valid distribution.
- *Full matrix vs per-qubit (tensored) matrix:* with 3–4 measured bits the full 16×16 matrix is cheap and also captures correlated readout errors.
- The paper applied **no** readout mitigation (its Sec. VI lists it as future work).

---

### 7.3 Addition 6 — zero-noise extrapolation (ZNE), optional

**Equation (this project's addition)**

$$
U \;\to\; U\,(U^\dagger U)^k, \qquad \lambda = 2k + 1 \in \{1, 3, 5\}, \qquad
p_i(\lambda) \approx a_i + b_i\,\lambda \;\;\Rightarrow\;\; p_i(0) \approx a_i
$$

**What it does:** U†U is the identity, so the folded circuit computes the same thing, but the hardware executes λ times as many noisy gates. Fitting each probability against λ and reading the value at λ = 0 estimates what a noise-free device would give.

**Code** — `src/mitigation.py`
```python
def fold_circuit(bound_tqc, scale):
    folded = body_nb.copy()
    inv = body_nb.inverse()
    for _ in range((scale - 1) // 2):
        folded.compose(inv, inplace=True)        # U†
        folded.compose(body_nb, inplace=True)    # U
    ...
    return transpile(folded, basis_gates=NATIVE_GATES, optimization_level=0)   # level 0: don't cancel U†U

def zne_extrapolate(scales, prob_list, order=1):
    coeffs = np.polyfit(scales, P, order)        # linear fit per outcome
    p0 = np.clip(coeffs[-1], 0, None)            # value at λ = 0
    return p0 / p0.sum()
```
`run_zne` runs the folded circuits, readout-mitigates each, and extrapolates. Figure: `stage07_zne_extrapolation.png`.

**Result:** 0.982 → **0.998** (2q), 0.995 → **0.996** (3q), at up to 1 + 3 + 5 = 9× the gate time.

**Architecture** — Part D, Addition 6, **optional** (yellow, dashed). The deployed pipeline bypasses it. **Passes:** extrapolated distribution → corrected distribution.

**Why this, not others**
- *Global folding vs local (gate-by-gate) folding:* global is simpler and keeps the exact same qubits and couplings.
- *Linear vs quadratic (Richardson) extrapolation:* with only three noisy points, a quadratic fit amplifies shot noise; linear is more stable.
- *Why optional:* the gain is real but small after retuning, it costs 9× gate time, and it does not reliably improve the **risk numbers** (it brings expected loss closer to the reference for the 2-qubit register but overshoots it for the 3-qubit register: $261 → $230 vs a reference of $254).

---

### 7.4 CORRECTED DISTRIBUTION p(default, z)

**No equation** — the final measured probability of every (default bit, economy bin) outcome.

**Code** — the `mean_probs` of each variant in `results/stage07_execution.json`.

**Architecture** — beige box. **Passes:** → post-processing. Everything financial is computed from this one distribution.

---

## §8 Parts E and F — Risk numbers and the closed loop

> **Flow:** corrected distribution → post-processing → Addition 7 → VaR & Hellinger → Addition 8 (fidelity gate) → ACCEPT, or RE-CALIBRATE → back to 6B.

### 8.1 Post-processing (paper Sec. IV-C)

**Equations (paper, unnumbered)**

For every outcome index i with probability pᵢ:
$$
b = i \bmod 2^n \ (\text{right } n \text{ bits} = \text{economy bin}), \qquad d = \lfloor i/2^n \rfloor\ (\text{left bit} = \text{default})
$$
$$
P(Z = z_b) \mathrel{+}= p_i, \qquad \text{loss}_i = d \cdot \mathrm{LGD}
$$
$$
F(L) = \sum_{L' \le L} P(L'), \qquad \mathbb{E}[L] = \sum_L L\,P(L)
$$

**What it does:** turns bitstrings into money. Qiskit writes bitstrings little-endian, so the asset qubit (highest index) is the **leftmost** character — exactly the paper's layout.

**Code** — `src/postprocessing.py`
```python
def decompose(probs, n, n_assets=1):
    for idx, p in enumerate(probs):
        b = idx & (n_z - 1)          # rightmost n bits → latent factor index
        d = idx >> n                 # leftmost bits     → default indicators
        joint[d, b] += p

def credit_statistics(probs, n, lgd=LGD, ...):
    p_z = joint.sum(axis=0)                                  # P(Z = z_b)
    scenario_loss = ... n_defaults * lgd ...                 # loss per scenario
    pdf = [scenario_prob[scenario_loss == L].sum() for L in unique_losses]
    cdf = np.cumsum(pdf)
    expected_loss = np.sum(unique_losses * pdf)
```
Written for any number of asset bits. Orchestrated by `src/stages.py → postprocess_register`; narrated in `08_classical_postprocessing.ipynb`; output `results/stage08_postprocessing.json`.

**Result:** noiseless P(L ≤ 0) = 0.748 / 0.746 and P(L ≤ 1000) = 1 — the paper's Fig. 10. Figure: `stage08_loss_cdf.png`.

**Architecture** — Part E, first block. **Receives:** corrected distribution. **Passes:** loss PDF/CDF + joint p(default, z) → Addition 7.

---

### 8.2 Addition 7 — conditional-default check + four fidelities

**Equation (this project's addition)**

$$
P(\text{default} \mid z_b) = \frac{p(1, b)}{P(Z = z_b)}
$$

**What it does:** recovers the default curve **from the measurements** and compares it with Vasicek (Eq. 1) — testing the *financial model*, not just a histogram. Four fidelities separate the error sources:

| Fidelity | Compares | Shortfall means |
|---|---|---|
| vs ideal | full distribution vs noiseless circuit | hardware error left (**used for ACCEPT**) |
| vs classical joint | vs P(z_b)·PD(z_b) from Eq. 1 + Eq. 10 | hardware + modelling error |
| loss distribution | P(L=0), P(L=1000) vs classical | error in default probability |
| z-marginal | economy bins vs target Gaussian | loader quality |

**Code**
`src/postprocessing.py → credit_statistics` (conditional PD) and `classical_joint_probs` (the classical reference built from Eq. 1 + Eq. 10):
```python
cond_pd = joint[1:].sum(axis=0) / p_z                 # P(default | z_b)

out[: 2 ** n] = p_z * (1 - pd)                         # classical: no default
out[2 ** n:] = p_z * pd                                # classical: default
```
`src/stages.py → fidelity_table` computes all four fidelities for every variant and repetition. Figures: `stage08_conditional_pd.png`, `stage08_latent_marginal.png`, `stage09_fidelity_summary.png`.

**Architecture** — Part E, Addition 7. Note the arrow "compared against Eq. 1 again" — **the finance model both starts and closes the chain**. **Passes:** CDF + distributions → VaR & Hellinger.

---

### 8.3 VaR and Hellinger fidelity

**Equations (paper, unnumbered; Hellinger ref. 37)**

$$
\mathrm{VaR}_{0.95} = \min\{L : F(L) \ge 0.95\}, \qquad \mathrm{CVaR} = \mathbb{E}[L \mid L \ge \mathrm{VaR}], \qquad F_H = \Big(\sum_i \sqrt{p_i q_i}\Big)^2
$$

**Code** — `src/postprocessing.py → value_at_risk`, `conditional_var`; `src/metrics.py → hellinger_fidelity`.
```python
def value_at_risk(unique_losses, cdf, confidence=CONFIDENCE):
    idx = int(np.searchsorted(np.asarray(cdf) - 1e-12, confidence))
    return float(unique_losses[min(idx, len(unique_losses) - 1)])
```

**Result:** VaR₀.₉₅ = **$1000** for every variant — the paper's value.

**Architecture** — Part E, last block. **Passes:** fidelity F_H → Addition 8.

**Why fidelity, not VaR, decides:** with one asset the loss is $0 or $1000 and P(L = 0) ≈ 0.75 < 0.95, so **any** distribution with default probability above 5 % gives VaR = $1000 — even the uncalibrated circuit. The paper says the same: the real result is reproducing the *distribution* the VaR is computed from.

---

### 8.4 Addition 8 — the fidelity gate and the closed loop

**Rule (this project's addition)**

$$
F_H(\text{6B + REM}) \ge 0.97 \;\Rightarrow\; \text{ACCEPT}, \qquad \text{otherwise} \;\Rightarrow\; \text{RE-CALIBRATE (re-run 6B from the current angles)}
$$

**What it does:** closes the loop. A real chip drifts; the system checks itself and repairs itself.

**Code** — `src/stages.py`
```python
def acceptance_check(fidelity, threshold=C.FIDELITY_THRESHOLD):
    return "ACCEPT" if fidelity >= threshold else "RE-CALIBRATE"

def recalibration_loop(n, x_start, drift, ...):
    for r in range(max_rounds + 1):
        f, sd = score(M, ref, x, C.SHOTS_FINAL_CHECK)
        decision = acceptance_check(f, threshold)
        if decision == "ACCEPT" or r == max_rounds:
            break
        h = hierarchical_calibration(M, ref, x, ML, lref, C.SHOTS_CALIBRATION, seed=r + 1)  # back to 6B
        x = np.asarray(h.x_best)
```
The **drift event** uses a completely new miscalibration (`DRIFT_EPS_DAY2`, `DRIFT_DELTA_DEG_DAY2` in `src/config.py`) — "the chip the next day". Orchestrated by `run_stage09`; narrated in `09_var_fidelity_check.ipynb`; output `results/stage09_final_report.json` and `results/FINAL_REPORT.md`.

**Result:**
- Today's chip: 0.982 / 0.995 → **ACCEPT**.
- Drift event: yesterday's angles give **0.528 / 0.676** → RE-CALIBRATE → 6B re-runs itself (204 runs) → **0.972 / 0.992** → ACCEPT. A manual 6A re-sweep would cost 347 / 477 runs.

Figure: `stage09_recalibration_loop.png`.

**Architecture** — Part F: the diamond "F_H ≥ 0.97 ?", the ACCEPT box, the RE-CALIBRATE box, and the long arrow on the right going **back to 6B** — the only backward arrow in the project.

**Why 0.97:** close to the paper's 98.9 % hardware result while leaving room for shot noise; configurable in `src/config.py`. **Why 6B + REM is the deployed pipeline (not + ZNE):** one circuit per estimate; ZNE costs up to 9× gate time for a small, inconsistent gain.

---

## §9 Supporting files, end-to-end trace, and checklist

### 9.1 Supporting files (the glue)

| File | What it does | Why it exists |
|---|---|---|
| `src/config.py` | every constant: p₀, ρ, LGD, gate set, coupling maps, noise values, drift (day 1 and day 2), shot counts, optimiser budgets, threshold | change one number in one place; every stage stays consistent |
| `src/pipeline_io.py` | `load_encoding_params`, `load_trained_params`, `nominal_parameters`, `save_json`, `save_fig`, `load_stage_output` | each stage finds the previous stage's output; falls back to recomputing if missing |
| `src/stages.py` | the computational core of Stages 6–9 (`run_stage06` … `run_stage09` plus the step functions) | notebooks and scripts call the **same** code, so they always give identical results |
| `src/report.py` | `write_final_report` builds `results/FINAL_REPORT.md` from the JSON outputs | one-page summary for the reader |
| `run_pipeline.py` | runs notebooks 00 → 09 in order (`--from`, `--to`, `--mode scripts`) | one command reproduces everything |
| `main.ipynb` | calls `run_pipeline.run_all`, then shows the headline tables and figures | the demo for the professor |
| `scripts/run_stage01…09_*.py` | one headless runner per stage | fast runs without notebook outputs |
| `00_overview.ipynb` | problem, gaps, VQC, parameter-shift verification, Adam demo | the "why" before the "how" |
| `01…09_*.ipynb` | narrated version of each stage, with plots | learning and presenting |
| `images/build_quantum_diagram.py` | draws `images/quantum_architecture.png` | the architecture diagram stays in sync with the project |
| `requirements.txt` | qiskit, qiskit-aer, numpy, scipy, matplotlib, pylatexenc, jupyter, ipykernel, nbclient, nbformat | reproducible environment |

### 9.2 One run, end to end — following the numbers

1. **Eq. 1:** p₀ = 0.25, ρ = 0.027 → PD(−3) = 0.427, PD(+3) = 0.118.
2. **Eq. 10:** 2-qubit grid z = −3, −1, +1, +3 → target ≈ [0.009, 0.491, 0.491, 0.009].
3. **Eq. 2–3:** α = −3.47°, β = 30.03°, fit error < 0.007.
4. **Eq. 4:** α̃ = −6.93°, β̃ = 40.42° → Ry(80.8°) + CRy(−13.9°) + CRy(−27.7°).
5. **Eq. 5–13 + training:** θ* = [90°, 195.4°], loss 2 × 10⁻⁸.
6. **Full circuit + SABRE:** 3 logical qubits → depth 33, 8 CZ on a 4-qubit line.
7. **Addition 1:** on the noisy chip the trained angles give F_H = 0.88.
8. **Addition 2 + 6A:** grid sweep → 0.939 in 347 runs (θ₁ → ≈ 234°, as in the paper).
9. **Addition 3 (6B):** BO → BO → SPSA → 0.982 in 204 runs.
10. **Additions 4–5:** 20 × 20 000 shots + REM → 0.982 ± 0.002.
11. **Addition 6 (optional):** ZNE → 0.998.
12. **Post-processing:** P(L ≤ 0) ≈ 0.73–0.75, expected loss ≈ $245–273 (classical $250), VaR = $1000.
13. **Addition 7:** recovered P(default | z) follows the Vasicek curve again.
14. **Addition 8:** 0.982 ≥ 0.97 → ACCEPT. After a drift event: 0.528 → recalibrate → 0.972 → ACCEPT.

### 9.3 "Nothing left out" checklist

**Every equation**
| Equation | Section |
|---|---|
| Eq. 1 Vasicek PD | §2.1 |
| Eq. 2, 3 sin² encoding, Ry rotation | §2.3 |
| Eq. 4 register-adapted asset gates | §2.4 |
| Eq. 5 qubit count | §3.1 |
| Eq. 6 loader state | §3.2 |
| Eq. 8, 9 Born probabilities | §3.4 |
| Eq. 10 target Gaussian, z-grid | §2.2 |
| Eq. 11 MSE loss | §3.5 |
| Eq. 12, 13 Ry matrix, CNOT | §3.3 |
| Eq. 14–17 symmetry conditions | §4.1 |
| Parameter-shift rule | §3.6 |
| Adam | §3.7 |
| SABRE | §4.3 |
| Noise model (depolarizing, readout, drift) | §5.1 |
| Hellinger distance / fidelity, J(x) | §5.2, §8.3 |
| Grid sweep | §6.1 |
| Gaussian process, Expected Improvement | §6.2 (a) |
| SPSA | §6.2 (b) |
| Shot-noise standard error | §7.1 |
| Assignment matrix, NNLS | §7.2 |
| Folding, linear extrapolation | §7.3 |
| Post-processing, CDF, expected loss | §8.1 |
| Conditional PD | §8.2 |
| VaR, CVaR | §8.3 |
| Acceptance rule | §8.4 |

**Every code file**
| File | Section |
|---|---|
| `gci_model.py` | §2.1, §2.2 |
| `quantum_encoding.py` | §2.3, §2.4 |
| `vqc_circuit.py` | §2.4, §3.1, §3.3, §4.2 |
| `training.py` | §3.4, §3.8 |
| `parameter_shift.py` | §3.5, §3.6 |
| `adam.py` | §3.7 |
| `transpilation.py` | §4.2, §4.3 |
| `noise_model.py` | §5.1 |
| `device.py` | §5.1 |
| `metrics.py` | §5.2, §8.3 |
| `calibration.py` | §6.1, §6.2 |
| `mitigation.py` | §5.2, §7.2, §7.3 |
| `postprocessing.py` | §8.1, §8.2, §8.3 |
| `stages.py` | §4.1, §6, §7.1, §8.2, §8.4, §9.1 |
| `report.py`, `config.py`, `pipeline_io.py` | §9.1 |
| `run_pipeline.py`, `main.ipynb`, `scripts/`, notebooks | §9.1 |
| `images/build_quantum_diagram.py` | §9.1 |

**Every architecture block**
| Block | Section |
|---|---|
| Finance branch: Eq. 1, 2, 3, 4 | §2 |
| Loader branch: Eq. 10, 5, 6, 12–13, 8–9, 11, parameter shift, Adam | §2.2, §3 |
| FULL GCI CIRCUIT | §4.2 |
| SABRE TRANSPILATION | §4.3 |
| Addition 1 — noise-emulated device | §5.1 |
| Addition 2 — calibration objective | §5.2 |
| Eq. 14–17 side branch | §4.1 |
| 6A grid sweep | §6.1 |
| 6B — Addition 3 | §6.2 |
| CALIBRATED ANGLES x* | §6.3 |
| Addition 4 — repeated execution | §7.1 |
| Addition 5 — readout mitigation | §7.2 |
| Addition 6 — ZNE (optional) | §7.3 |
| CORRECTED DISTRIBUTION | §7.4 |
| Sec. IV-C post-processing | §8.1 |
| Addition 7 — conditional-default check | §8.2 |
| VaR & Hellinger fidelity | §8.3 |
| F_H ≥ 0.97 gate, ACCEPT, RE-CALIBRATE | §8.4 |
| Execution environment | §5.1 (emulated chip), §9.1 |

---

*Everything in this guide refers to code and results in this repository. All results come from a simulator with an emulated noise model, not a physical quantum processor.*
