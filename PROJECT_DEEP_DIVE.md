# Project Deep Dive — Block by Block

**Quantum Circuit-Based Adaptation for Credit Risk Analysis**
Base paper: Ahmad et al., *IEEE Transactions on Quantum Engineering*, vol. 7, 3103316, 2026

This guide walks through the architecture diagram (`images/quantum_architecture.png`) **one block at a time, top to bottom**. For every block it answers the same questions, in plain words:

| Question | Where you find it |
|---|---|
| What does this block do? | **In simple words** |
| Why is it in the project? | **Why it is here** |
| What maths does it use? | **Equation** |
| What does it receive? | **Needs** |
| What does it hand to the next block? | **Passes on** |
| Which file and function implement it? | **Code** |
| Why this choice and not another? | **Why this, not something else** |
| What number did it produce? | **Result** |

Read §0 first — it is the whole project as one short story. Every block afterwards is one step of that story.

---

## Contents

- [§0 The project in plain words](#0-the-project-in-plain-words)
- [§1 How to read the diagram, and which file implements which block](#1-how-to-read-the-diagram-and-which-file-implements-which-block)
- [§2 Part A — Replication: Finance branch (Eq. 1–4)](#2-part-a--replication-finance-branch)
- [§3 Part A — Replication: Loader branch (Eq. 10, 5, 6, 12–13, 8–9, 11, parameter shift, Adam)](#3-part-a--replication-loader-branch)
- [§4 Part A — Full GCI circuit and SABRE transpilation](#4-part-a--full-gci-circuit-and-sabre-transpilation)
- [§5 Part B — Noisy device (Additions 1–2)](#5-part-b--noisy-device)
- [§6 Part C — Calibration (Eq. 14–17, 6A, 6B, calibrated angles)](#6-part-c--calibration)
- [§7 Part D — Execution and mitigation (Additions 4–6)](#7-part-d--execution-and-mitigation)
- [§8 Part E — Risk numbers (post-processing, Addition 7, VaR & Hellinger)](#8-part-e--risk-numbers)
- [§9 Part F — Closed loop (Addition 8) and the execution environment](#9-part-f--closed-loop)
- [§10 Supporting files, one run end to end, and the "nothing left out" checklist](#10-supporting-files-one-run-end-to-end-and-checklist)
- [§11 Glossary and likely questions](#11-glossary-and-likely-questions)

---

## §0 The project in plain words

### 0.1 The story in seven steps

1. **The bank's question.** A bank lends $1000. Will the borrower pay it back? That depends on the economy: in a recession the chance of default is about 43 %, in a boom about 12 %, on average 25 %. So 75 % of the time the bank loses $0 and 25 % of the time it loses $1000. Banks must report the worst-case loss they are 95 % sure not to exceed — the **95 % Value at Risk (VaR)**. Normally this is computed by simulating millions of random economies (Monte Carlo), which is slow: halving the error costs four times the work.

2. **Loaded dice made of qubits.** Instead of simulating, build a tiny quantum circuit that *behaves like loaded dice*:
   - **2 or 3 qubits = the economy dice.** Measuring them gives an economy bin (very bad … very good), with the middle bins most likely — a bell curve.
   - **1 qubit = the default coin.** Its bias depends on what the economy dice showed: a bad economy makes "default" more likely.

   Every run of the circuit is one possible future for the bank. A quantum algorithm (Amplitude Estimation) could read risk numbers from such a circuit with a quadratic speed-up — but only if the circuit is loaded correctly. That is what this project is about.

3. **Turn the knobs.** Each economy qubit has a rotation angle — a knob. A classical optimiser turns the knobs until the dice match the bell curve. This is training.

4. **Translate for the chip.** Real chips only understand a few basic operations and only let neighbouring qubits interact. The circuit is rewritten to follow those rules (transpilation).

5. **Real chips are faulty.** You set a knob to 90° and the chip actually turns it to about 101°; it sometimes reads 0 as 1; every operation adds a little randomness. So the dice come out wrong — even though training was perfect.

6. **Fix the knobs on the faulty chip.**
   - The base paper: a person turns the knobs **by hand**, one or two at a time, degree by degree.
   - This project: an **algorithm** turns all knobs automatically, looking only at what the chip outputs. Better result, fewer tries.

7. **Clean up, turn into money, and check.** Correct the misread measurements, turn the outcomes back into the bank's loss picture, compute VaR, and check the result is still at least 97 % right. If the chip drifts, recalibrate automatically.

### 0.2 The story mapped onto the project

| Simple idea | Real name | Stage | Diagram part |
|---|---|---|---|
| The bank's loss picture | GCI / Vasicek model, VaR | 1 | A |
| The default coin | sin² encoding, asset gates | 2–3 | A, finance branch |
| The economy dice | Gaussian loader (Ry + CNOT) | 3 | A, loader branch |
| Turning the knobs until it's right | Training: parameter shift + Adam | 4 | A, loader branch |
| Translating for the chip | SABRE transpilation | 5 | A |
| The faulty chip | Noise-emulated device | 6 | B |
| Hand-tuning vs auto-tuning | 6A grid sweep vs **6B BO → BO → SPSA** | 6 | C |
| Fixing misread results | Readout mitigation, ZNE | 7 | D |
| Turning results into money | Post-processing, loss CDF | 8 | E |
| "Is it still good?" | Fidelity gate, recalibration | 9 | F |

### 0.3 What the base paper did and what this project does

| | Base paper | This project |
|---|---|---|
| Build, train and transpile the circuit | yes | yes (replicated) |
| Run on a noisy chip | real superconducting chip (Contralto-D, 17 qubits) | emulated noisy device on a laptop |
| Fix the knobs for the noisy chip | **by hand**, grid sweep | **automated**: Bayesian optimisation + SPSA |
| Error mitigation | none | readout mitigation + zero-noise extrapolation |
| When the chip drifts | redo by hand | detected and repaired automatically |

---

## §1 How to read the diagram, and which file implements which block

### 1.1 Reading the diagram

- Each box receives something from the box above, does **one job**, and hands something to the box below. The small grey text on each arrow ("passes: …") says **what is handed over**.
- **Brown tag `BASE PAPER`** = replicated from the paper. **Green tag `OUR ADDITION`** = this project's novelty. **Yellow tag `OPTIONAL`** = an extra variant, not on the main path.
- The diagram has six parts, A to F. Part A has two columns that run side by side and meet at the **FULL GCI CIRCUIT**.
- Special arrows:
  - the **dashed arrow** on the right of Part A carries the target histogram p* down to Eq. 11;
  - the **dashed box** Eq. 14–17 is a side branch that only feeds 6A;
  - the **dashed bypass** in Part D skips ZNE (the deployed path);
  - the **long arrow up the right side** goes from RE-CALIBRATE back to 6B — the only backward arrow.

### 1.2 Code files and the blocks they implement

| File | What it contains | Diagram blocks |
|---|---|---|
| `src/gci_model.py` | Vasicek PD(z), z-grid, target Gaussian, classical VaR | Eq. 1, Eq. 10, classical reference in Part E |
| `src/quantum_encoding.py` | fit of PD(z) ≈ sin²(αz+β); α̃, β̃ | Eq. 2, 3, 4 |
| `src/vqc_circuit.py` | loader ansatz and full GCI circuit (Stage 3) | Eq. 4, 5, 12–13, full circuit |
| `src/training.py` | circuit probabilities, training loop | Eq. 8–9, training |
| `src/parameter_shift.py` | exact gradients, MSE loss | Eq. 11, parameter shift |
| `src/adam.py` | Adam optimiser | Adam |
| `src/transpilation.py` | parameterised circuits, SABRE | full circuit, SABRE |
| `src/noise_model.py` | depolarizing, readout, drift | Addition 1 |
| `src/device.py` | `NoisyDevice` — "the chip" | Addition 1, used by Parts C–F |
| `src/metrics.py` | Hellinger distance and fidelity | Addition 2, Part E |
| `src/calibration.py` | grid sweep, SPSA, Bayesian optimisation, 6B | 6A, Addition 3 |
| `src/mitigation.py` | readout mitigation, ZNE, mitigation-aware wrapper | Additions 2, 5, 6 |
| `src/postprocessing.py` | bitstrings → loss PDF/CDF, VaR | post-processing, Addition 7 |
| `src/stages.py` | runs Stages 6–9, fidelity table, closed loop | Parts C–F, Addition 8 |
| `src/report.py` | writes `results/FINAL_REPORT.md` | output |
| `src/config.py` | every setting in one place | all |
| `src/pipeline_io.py` | finds and saves each stage's output | all |
| `run_pipeline.py`, `main.ipynb` | run every stage in order | all |
| `scripts/run_stageXX_*.py` | headless runner per stage | all |
| `00_…09_*.ipynb` | narrated notebook per stage | all |
| `images/build_quantum_diagram.py` | draws the architecture diagram | documentation |

---

## §2 Part A — Replication: Finance branch

> **The job of this column:** build the **default coin** — the asset qubit whose chance of reading "1" equals the borrower's default probability in each economy.
> **Flow:** Eq. 1 → Eq. 2 → Eq. 3 → Eq. 4 → FULL GCI CIRCUIT.

### A1 · Eq. 1 — Vasicek PD(z) `BASE PAPER`

**In simple words.** A formula that tells you how likely the borrower is to default for any state of the economy z. z = −3 is a deep recession, 0 is normal, +3 is a boom.

**Why it is here.** It is the financial ground truth. Everything quantum in the project exists to reproduce this curve, and at the end the quantum result is checked against it.

**Equation (paper Eq. 1)**

$$
\mathrm{PD}(z) = \Phi\!\left(\frac{\Phi^{-1}(p_0) - \sqrt{\rho}\,z}{\sqrt{1-\rho}}\right)
$$

- p₀ = 0.25 — the average default probability
- ρ = 0.027 — how strongly the borrower depends on the economy
- Φ — the standard normal CDF (turns a number into a probability); Φ⁻¹ — its inverse

**Needs.** p₀ and ρ (from `src/config.py`) and a value of z.

**Passes on.** The PD(z) curve → Eq. 2 (arrow label: *passes: PD(z) curve*).

**Code** — `src/gci_model.py → pd_given_z`
```python
def pd_given_z(z, p0, rho):
    numerator = norm.ppf(p0) - np.sqrt(rho) * z      # Φ⁻¹(p0) − √ρ·z
    denominator = np.sqrt(1 - rho)                    # √(1−ρ)
    return norm.cdf(numerator / denominator)          # Φ( … )
```
The same file also builds the classical answers used at the end: `discrete_grid_var` (the loss distribution on the same grid the circuit uses) and `monte_carlo_var` (2 million random draws).

**Why this, not something else.** The Vasicek / GCI model is the basis of the Basel capital formula and is the paper's model. Richer models (several risk factors, fat-tailed copulas) need more qubits; one factor keeps the circuit at 3–4 qubits, small enough to study with realistic noise on a laptop.

**Result.** PD(−3) ≈ 0.427, PD(0) ≈ 0.247, PD(+3) ≈ 0.118. Classical baseline: P(loss = 0) = 0.750, expected loss ≈ $250, VaR₉₅ = $1000.

---

### A2 · Eq. 2 — Linearise onto the Born rule `BASE PAPER`

**In simple words.** Rewrites the default curve in a form a qubit can produce. A qubit rotated by 2φ gives "1" with probability exactly sin²φ. If φ is a straight line in z, φ = αz + β, then one rotation gives the right default probability for every z.

**Why it is here.** A quantum circuit cannot evaluate Φ directly. The sin² form is exactly what a single rotation gate produces, so it turns a finance formula into something a gate can do.

**Equation (paper Eq. 2)**

$$
\mathrm{PD}(z) \equiv P_1 = \sin^2(\alpha z + \beta)
$$

"P₁" means "the probability of measuring 1 on the asset qubit". α (slope) and β (offset) are found by fitting a straight line to arcsin(√PD(z)).

**Needs.** The PD(z) curve from Eq. 1.

**Passes on.** α, β → Eq. 3.

**Code** — `src/quantum_encoding.py → fit_linear_angle`
```python
z_fit = np.linspace(-z_max, z_max, n_fit_points)
theta_targets = np.arcsin(np.sqrt(pd_given_z(z_fit, p0, rho)))   # exact angle for each z
alpha, beta = np.polyfit(z_fit, theta_targets, 1)                 # best straight line
pd_approx = np.sin(alpha * z_fit + beta) ** 2                     # check the fit
```

**Why this, not something else.**
- An exact angle for every bin would need an expensive multi-controlled gate per bin (2ⁿ of them). The straight-line form needs only n + 1 simple gates (see Eq. 4).
- A curved (quadratic) fit would need extra two-qubit gates — more noise. The straight line is already accurate to < 0.007, far below the chip's noise.
- The paper computes α, β with an analytic formula (Supplementary Eqs. 5–6); this project uses a least-squares fit. Same encoding, simpler to reproduce — listed as a modification in the equation audit.

**Result.** α = −3.47°, β = 30.03°. Maximum error vs Vasicek: 0.0065; mean error: 0.0025.

---

### A3 · Eq. 3 — Rotation angle `BASE PAPER`

**In simple words.** The actual gate on the default coin. Rotating the asset qubit by 2(αz + β) makes "1" (default) appear with probability PD(z).

**Why it is here.** It turns the fitted line into a physical operation.

**Equation (paper Eq. 3)**

$$
R_y\big(2(\alpha z + \beta)\big), \qquad P(|1\rangle) = \text{default probability}
$$

Ry(θ) turns |0⟩ into cos(θ/2)|0⟩ + sin(θ/2)|1⟩, so P(1) = sin²(θ/2). With θ = 2(αz + β), P(1) = sin²(αz + β) = PD(z).

**Needs.** α, β.

**Passes on.** The rotation angle 2(αz + β) → Eq. 4.

**Code.** Used inside the asset gates of Eq. 4 (below).

**Why this, not something else.** Ry keeps amplitudes real and directly sets P(1) = sin². Rx or Rz rotations would add complex phases that do nothing for a probability.

---

### A4 · Eq. 4 — Register-indexed asset gates `BASE PAPER`

**In simple words.** The circuit doesn't store z itself — it stores a **bin number** b (0, 1, 2, 3 for 2 qubits). This block rewrites the angle in terms of b. Because b is written in binary (b = q₀ + 2·q₁ + 4·q₂ …), the gate splits into:
- one plain rotation **Ry(2β̃)** — the baseline default chance, and
- one **controlled rotation per economy qubit** — it only adds its piece when that economy bit is 1.

So "worse economy bin" automatically means "more likely to default".

**Why it is here.** This is what links the coin to the dice: the asset qubit's rotation depends on the economy qubits' values.

**Equation (paper Eq. 4)**

$$
R_y\big(2(\tilde\alpha\,b + \tilde\beta)\big), \qquad \tilde\alpha = \alpha\cdot\frac{2z_{\max}}{2^n-1}, \qquad \tilde\beta = \beta - \alpha z_{\max}
$$

**Needs.** α, β and the grid spacing (6 / (2ⁿ − 1)).

**Passes on.** The asset-qubit gates (α̃, β̃) → **FULL GCI CIRCUIT**.

**Code** — `src/quantum_encoding.py → register_adapted_params`
```python
slope = (2 * z_max) / (2 ** n_qubits - 1)
alpha_tilde = alpha * slope
beta_tilde = beta - alpha * z_max
```
and the gates — `src/vqc_circuit.py → build_gci_circuit`
```python
qc.ry(2 * beta_tilde, asset_qubit)                       # baseline rotation
for k in range(n_z_qubits):
    qc.cry(2 * alpha_tilde * (2 ** k), k, asset_qubit)   # one controlled-Ry per economy bit
```

**Why this, not something else.** The binary split needs n + 1 gates; a lookup table (one gate per bin) needs 2ⁿ expensive gates. Because the controls are the economy bits themselves, the coin cannot disturb the dice: P(default, bin b) = P(bin b) × PD(bin b) exactly.

**Result.** β̃ = 40.42°; α̃ = −6.93° (2-qubit register), −2.97° (3-qubit register). For the 2-qubit register the gates are Ry(80.8°), CRy(−13.9°), CRy(−27.7°).

---

## §3 Part A — Replication: Loader branch

> **The job of this column:** build and train the **economy dice** — a register whose measurements follow a bell curve.
> **Flow:** Eq. 10 → Eq. 5 → Eq. 6 → Eq. 12–13 → Eq. 8–9 → Eq. 11 → parameter shift → Adam → FULL GCI CIRCUIT.

### A5 · Eq. 10 — Target Gaussian p*_b `BASE PAPER`

**In simple words.** Turns the smooth bell curve of the economy into a few bins — one bin per possible register outcome. 2 qubits → 4 bins; 3 qubits → 8 bins. This is the shape the dice must reproduce.

**Why it is here.** A quantum register only has a fixed number of outcomes, so the continuous bell curve must become a histogram first.

**Equation (paper Eq. 10)**

$$
z(b) = -z_{\max} + \frac{2 z_{\max}}{2^n - 1}\, b, \qquad p^\star_b \propto \exp\!\left(-\frac{z(b)^2}{2}\right), \qquad z_{\max} = 3
$$

**Needs.** The number of economy qubits n and the range [−3, 3].

**Passes on.** The target histogram p*. It is **held** along the dashed line on the right until Eq. 11, where it is compared with the circuit's output.

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

**Why this, not something else.** ±3 covers 99.7 % of a normal distribution; wider wastes bins on almost-zero probabilities, narrower cuts off the recessions that drive credit losses. Even spacing makes z(b) a straight line in b — which is exactly what makes Eq. 4 work.

**Result.** 2-qubit grid z = −3, −1, +1, +3 → target ≈ [0.009, 0.491, 0.491, 0.009].

---

### A6 · Eq. 5 — Register size `BASE PAPER`

**In simple words.** Counts the qubits: one per asset plus n per risk factor. Here: 1 asset + 2 or 3 economy qubits = **3 or 4 qubits**.

**Why it is here.** It fixes the size of the circuit and shows how the model would grow (2 assets and 2 risk factors would need at least 6 qubits).

**Equation (paper Eq. 5)**

$$
N_{\text{qubits}} = N_{\text{assets}} + \sum_{k} n_k
$$

**Needs.** The model size (1 asset, 1 risk factor) and n.

**Passes on.** The register size (n + 1 qubits) → Eq. 6.

**Code** — `src/vqc_circuit.py → build_gci_circuit`
```python
n_total = n_z_qubits + 1        # Eq. 5 with one asset
asset_qubit = n_z_qubits        # the asset is the highest-numbered qubit
```
Register sizes are set in `src/config.py → REGISTER_SIZES = (2, 3)`.

**Why 2 and 3 qubits.** 2 is the paper's hardware case; 3 tests whether the methods scale, still small enough for a laptop.

---

### A7 · Eq. 6 — Goal state `BASE PAPER`

**In simple words.** Defines what the economy register must become. When measured, a qubit state gives each outcome with probability equal to its amplitude **squared** — so the amplitudes must be the **square roots** of the bin probabilities.

**Why it is here.** It states the goal precisely before choosing the gates that reach it.

**Equation (paper Eq. 6)**

$$
|\psi(\theta)\rangle = \sum_{b} \sqrt{p_b(\theta)}\;|b\rangle
$$

**Needs.** The register size.

**Passes on.** The goal state → Eq. 12–13 (the gates that build it).

**Code.** A goal, not a function: it is realised by the ansatz (A8) and checked by `training.probabilities_from_theta` (A9).

---

### A8 · Eq. 12, 13 — Ry matrix + CNOT `BASE PAPER`

**In simple words.** The economy dice themselves, called the **ansatz**: one Ry(θᵢ) knob on each economy qubit, followed by CNOT gates from qubit 0 to every other qubit (a "star"). The rotations spread probability over the outcomes; the CNOT **swaps two amplitudes**, and that swap is what creates the bell shape (small at the edges, large in the middle).

**Why it is here.** It is the paper's hardware-efficient design — a shallow circuit with few two-qubit gates, so it survives noise.

**Equations (paper Eq. 12, 13)**

$$
R_Y(\theta) = \begin{bmatrix}\cos\frac{\theta}{2} & -\sin\frac{\theta}{2}\\ \sin\frac{\theta}{2} & \cos\frac{\theta}{2}\end{bmatrix}
$$

After Ry(θ₀) and Ry(θ₁) on |00⟩ the amplitudes are [c₀c₁, c₀s₁, s₀c₁, s₀s₁] (c = cos(θ/2), s = sin(θ/2)). The CNOT swaps the last two (Eq. 13): [c₀c₁, c₀s₁, s₀s₁, s₀c₁]. With θ₀ = 90° and the right θ₁ this is a bell shape.

**Needs.** The knob angles θ.

**Passes on.** The amplitudes as formulas of θ → Eq. 8–9. (They also feed the side branch Eq. 14–17.)

**Code** — `src/vqc_circuit.py → build_ansatz`
```python
thetas = [Parameter(f"theta_{i}") for i in range(n_z_qubits)]
for i in range(n_z_qubits):
    qc.ry(thetas[i], i)                  # Eq. 12: one knob per qubit
if entangler == "star":
    for i in range(1, n_z_qubits):
        qc.cx(0, i)                      # Eq. 13: CNOT from qubit 0 to each other qubit
```

**Why this, not something else.**
- Ry only — real amplitudes are enough for a probability distribution.
- Star entangler — the paper's design, kept for a faithful replication. Stage 4 also tried a **chain** (0→1, 1→2): for 3 qubits it trains much better (loss 0.0018 vs 0.049). The star caps the 3-qubit match at about 0.78 against the ideal bell curve. This is reported openly as a limitation.
- One layer — every extra layer adds CNOTs, the noisiest gates on real chips.

---

### A9 · Eq. 8, 9 — Circuit histogram `BASE PAPER`

**In simple words.** For the current knob settings, what probabilities does the circuit actually produce?

**Why it is here.** Training needs to compare what the dice do with what they should do.

**Equations (paper Eq. 8 for 2 qubits, Eq. 9 for 3 qubits)**

$$
p_b(\theta) = \big|\langle b \mid \psi(\theta)\rangle\big|^2
$$

**Needs.** The amplitudes from Eq. 12–13.

**Passes on.** The circuit histogram p(θ) → Eq. 11.

**Code** — `src/training.py → probabilities_from_theta`
```python
qc, thetas = build_ansatz(n_z_qubits, entangler=entangler)
bound = qc.assign_parameters(dict(zip(thetas, theta_values)))   # put numbers into the knobs
return Statevector.from_instruction(bound).probabilities()      # |⟨b|ψ⟩|² for every b
```

**Why exact (statevector), not shots.** Training happens on a perfect simulator, as in the paper. Exact probabilities remove shot noise so the optimiser sees the true loss. Noise comes later, in Part B.

---

### A10 · Eq. 11 — MSE loss `BASE PAPER`

**In simple words.** One number saying how far the dice are from the target bell curve: add up the squared differences bin by bin. Training makes it as small as possible.

**Why it is here.** An optimiser needs one number to minimise. This is the block where the loader branch's two inputs **meet**: p(θ) from Eq. 8–9 and p* from Eq. 10 (the dashed line).

**Equation (paper Eq. 11)**

$$
\mathcal{L}(\theta) = \sum_{b} \big(p_b(\theta) - p^\star_b\big)^2
$$

**Needs.** p(θ) and p*.

**Passes on.** The loss → parameter-shift gradient.

**Code** — `src/parameter_shift.py → mse_loss`
```python
def mse_loss(p, target):
    return float(np.sum((p - target) ** 2))
```

**Why MSE, not KL divergence or Hellinger.** It is the paper's choice; it is smooth and never infinite (KL blows up when a bin is zero). Hellinger is used later to *judge* results, because the paper reports it.

---

### A11 · Parameter-shift gradient `BASE PAPER (unnumbered)`

**In simple words.** Tells you which way to turn each knob to make the loss smaller. It runs the circuit with one knob nudged +90° and −90°, and the difference gives the **exact** slope.

**Why it is here.** You cannot "backpropagate" through a quantum circuit like a neural network — you only see measurement results. This rule gets exact derivatives from the circuit itself.

**Equations**

$$
\frac{\partial p_b}{\partial \theta_i} = \frac{p_b(\theta_i + \tfrac{\pi}{2}) - p_b(\theta_i - \tfrac{\pi}{2})}{2},
\qquad
\frac{\partial \mathcal{L}}{\partial \theta_i} = \sum_b 2\,(p_b - p^\star_b)\,\frac{\partial p_b}{\partial \theta_i}
$$

(The second line is the chain rule applied to Eq. 11.)

**Needs.** The loss and the circuit.

**Passes on.** The gradients ∂L/∂θ → Adam.

**Code** — `src/parameter_shift.py → gradient`
```python
for i in range(n_params):
    shifted_plus  = theta.copy(); shifted_plus[i]  += np.pi / 2
    shifted_minus = theta.copy(); shifted_minus[i] -= np.pi / 2
    dp_dtheta_i = (prob_fn(shifted_plus) - prob_fn(shifted_minus)) / 2   # shift rule
    grad[i] = np.sum(2 * (p_current - target) * dp_dtheta_i)            # chain rule on Eq. 11
```

**Why this, not something else.** Finite differences (a tiny nudge) are only approximate and very sensitive to noise; the shift rule uses a big π/2 nudge and is exact for rotation gates.

**Result.** Matches finite differences to 3.7 × 10⁻¹¹ (checked in `00_overview.ipynb`).

---

### A12 · Adam update `BASE PAPER (unnumbered)`

**In simple words.** The thing that actually turns the knobs. It remembers the recent direction (momentum) and adapts the step size for each knob, so training is fast and smooth. Repeated 150 times.

**Why it is here.** Plain gradient descent needs a hand-tuned step size and oscillates; the paper chose Adam for stable convergence.

**Equation**

$$
m \leftarrow \beta_1 m + (1-\beta_1) g, \quad v \leftarrow \beta_2 v + (1-\beta_2) g^2, \quad
\theta \leftarrow \theta - \eta\,\frac{\hat m}{\sqrt{\hat v} + \epsilon}
$$

g = gradient; m = running average of g; v = running average of g²; the hats correct for starting at zero; η = 0.15.

**Needs.** The gradients.

**Passes on.** The trained angles θ* → **FULL GCI CIRCUIT**.

**Code** — `src/adam.py → AdamOptimizer.step`, used by the training loop `src/training.py → train_gaussian_loader`
```python
# Adam step
self.m = self.beta1 * self.m + (1 - self.beta1) * grad
self.v = self.beta2 * self.v + (1 - self.beta2) * grad ** 2
m_hat = self.m / (1 - self.beta1 ** self.t)
v_hat = self.v / (1 - self.beta2 ** self.t)
return theta - self.lr * m_hat / (np.sqrt(v_hat) + self.eps)

# training loop (A9 → A10 → A11 → A12, repeated)
for _ in range(n_iterations):
    grad, p_current = gradient(prob_fn, theta, target)
    loss_history.append(mse_loss(p_current, target))
    theta = optimizer.step(theta, grad)
```

**Result (Stage 4)**

| Register | Trained angles θ* | Final loss | Note |
|---|---|---|---|
| 2-qubit | 90.0°, 195.4° | 2 × 10⁻⁸ | reproduces the 4-bin bell curve essentially exactly |
| 3-qubit (star) | 90.0°, 55.0°, 131.0° | 0.049 | limit of the star design (≈ 0.78 fidelity vs ideal) |
| 3-qubit (chain, comparison) | 90.0°, 70.1°, 208.7° | 0.0018 | better, but not the paper's design |

---

## §4 Part A — Full GCI circuit and SABRE transpilation

### A13 · FULL GCI CIRCUIT — where the two columns meet

**In simple words.** Joins the trained economy dice (θ*) and the default coin (Eq. 4) into **one circuit** on n + 1 qubits. Every run gives one scenario for the bank: the **left bit** says whether the borrower defaulted, the **right bits** say which economy bin happened.

**Why it is here.** This single circuit *is* the credit-risk "uncertainty model" — the thing a quantum risk algorithm would use.

**Equation.** No new equation — it combines Eq. 6/12/13 (dice) and Eq. 4 (coin). Because the coin is controlled by the dice bits:

$$
P(\text{default}, \text{bin } b) = P(\text{bin } b)\times \mathrm{PD}(\text{bin } b)
$$

**Needs.** θ* from the loader branch and α̃, β̃ from the finance branch.

**Passes on.** The logical circuit → SABRE.

**Code.** Two versions with the same structure:
- `src/vqc_circuit.py → build_gci_circuit` (Stage 3): coin angles are fixed numbers.
- `src/transpilation.py → build_param_circuit` (Stage 6 onwards): **coin angles are knobs too**, because calibration has to tune them.
```python
for i in range(n):
    qc.ry(params[i], i)                           # dice knobs θ_i
for i in range(1, n):
    qc.cx(0, i)                                   # star CNOTs
qc.ry(2 * beta_t, asset)                          # coin baseline (Eq. 4)
for k in range(n):
    qc.cry(2 * alpha_t * (2 ** k), k, asset)      # coin depends on dice bits (Eq. 4)
```
From Stage 6 on, all knobs together are called the **commanded angles** x = [θ₀ … θₙ₋₁, β̃, α̃]. Their trained values come from `src/pipeline_io.py → nominal_parameters`.

**Why rebuild it in `transpilation.py`.** Calibration must change the coin angles, so they need to be symbolic. It also lets the circuit be translated for the chip **once**, then only the numbers change — exactly how an experimentalist works.

---

### A14 · SABRE transpilation `BASE PAPER (unnumbered)`

**In simple words.** Translates the circuit into the chip's language. A real chip only knows four basic operations (`rz`, `sx`, `x`, `cz`) and only lets **neighbouring** qubits interact. SABRE rewrites every gate into those four and adds swap operations where non-neighbours must interact, keeping the circuit as short as possible.

**Why it is here.** Without it the circuit cannot run on hardware. It also shows the hidden cost of limited connectivity.

**Equation.** None — it is a search algorithm (paper ref. 38).

**Needs.** The logical circuit and the chip's connection map (a line of qubits).

**Passes on.** The hardware circuit → Part B.

**Code** — `src/transpilation.py → transpile_for_device`
```python
return transpile(qc, coupling_map=coupling_map(n), basis_gates=NATIVE_GATES,
                 initial_layout=initial_layout,
                 layout_method=None if initial_layout else "sabre", routing_method="sabre",
                 optimization_level=OPTIMIZATION_LEVEL, seed_transpiler=SEED_TRANSPILER)
```
`logical_to_physical` records which real qubit each circuit qubit landed on — needed because the drift (Part B) is different on every real qubit. Narrated in `05_transpilation.ipynb`.

**Why this, not something else.** CZ is the paper chip's two-qubit gate; a straight line of qubits is the most restrictive common layout, so connectivity costs are visible; SABRE is the paper's choice. The paper also hand-replaced part of the transpiled circuit; this project does not need to, because calibration absorbs those effects — listed as a modification.

**Result.**

| Register | Depth | Two-qubit CZ gates |
|---|---|---|
| 2-qubit | 6 → 33 | 5 → 8 |
| 3-qubit | 8 → 56 | 8 → 14 |

**Key point.** Transpilation fixes the circuit's *shape* but knows nothing about how faulty each gate is. That is why Parts B and C exist.

---

## §5 Part B — Noisy device

### B1 · Addition 1 — Noise-emulated device `OUR ADDITION`

**In simple words.** A **faulty chip** that runs on your laptop. You send it knob settings; it applies them slightly wrong, adds randomness, and sometimes misreads the result — just like real hardware.

**Why it is here.** The paper needed a real chip. This block reproduces that experiment on a laptop, with the same three error sources the paper names (Sec. V), so the problem — and the fix — can be studied, repeated and stress-tested.

**Equations (this project)**

$$
\text{gate noise: } \rho \to (1-p)\,\rho + p\,\frac{I}{d}, \qquad
\text{readout: } \begin{bmatrix}1-p_{01} & p_{01}\\ p_{10} & 1-p_{10}\end{bmatrix}, \qquad
\text{drift: } \theta_{\text{real}} = (1+\varepsilon_q)\,\theta + \delta_q
$$

| Error | What it means | Value |
|---|---|---|
| Gate noise (depolarizing) | each operation slightly randomises the state | 0.2 % per single-qubit gate, 1.5 % per two-qubit gate |
| Readout error | 0 read as 1, or 1 read as 0 | 2–7 % per qubit (≈ 5 % average) |
| Drift | knobs over- or under-turn | up to ±14 % and ±15°, different on every qubit |

The drift values are **hidden** — no calibration method ever reads them. Methods only see measured results, like an experimentalist in front of a real chip.

**Needs.** The hardware circuit (from SABRE) and the angles you send.

**Passes on.** The measured distribution p_dev(x) → Addition 2.

**Code**
`src/noise_model.py → build_noise_model` (gate noise and readout):
```python
nm.add_all_qubit_quantum_error(depolarizing_error(depol_1q, 1), ["sx", "x"])
nm.add_all_qubit_quantum_error(depolarizing_error(depol_2q, 2), ["cz"])
for q in range(n_physical):
    p01, p10 = readout_errors[q]
    nm.add_readout_error(ReadoutError([[1 - p01, p01], [p10, 1 - p10]]), [q])
```
`src/noise_model.py → ControlDrift.realise` (the faulty knobs):
```python
x[i] = (1 + self.eps[q]) * x[i] + self.delta[q]          # dice knob on real qubit q
x[n] = (1 + self.eps[qa]) * x[n] + self.delta[qa] / 2    # coin baseline
x[n + 1] = (1 + self.eps[qa]) * x[n + 1]                 # coin slope
```
`src/device.py → NoisyDevice` — "the chip":
```python
def bound_circuit(self, x):
    realised = self.drift.realise(x, self.n, self.kind, self.phys)   # the chip distorts the knobs
    return self.tqc.assign_parameters(dict(zip(self.params, realised)))

def run(self, x, shots, seed=None):          # knobs in → measured histogram out
    return self.run_circuit(self.bound_circuit(x), shots, seed)
```
It also counts circuit runs and shots, so the cost of every calibration method can be compared.

**Why this, not something else.** A real IBM chip has queues and changing noise, so results can't be repeated exactly; Qiskit's built-in fake devices have gate and readout noise but no drift, so there would be little to calibrate. Drift is modelled as wrong knob angles because the paper's chip sets angles by pulse strength — a strength error *is* a scale error on the angle.

**Result.** The perfectly trained angles drop from fidelity **1.00** to **0.88** (2-qubit) and **0.92** (3-qubit). This is the problem the rest of the project solves.

---

### B2 · Addition 2 — Calibration objective `OUR ADDITION`

**In simple words.** A single "how wrong is it?" score: the **Hellinger distance** between what the faulty chip produces and what a perfect chip would produce. 0 = identical. It is measured on readout-corrected results.

**Why it is here.** To let an algorithm fix the knobs, "does it look right?" must become a number it can minimise. Measuring after readout correction means the knobs don't try to absorb readout errors — otherwise readout mitigation later would correct the same error twice.

**Equations (this project)**

$$
J(x) = H\big(p_{\text{dev}}(x),\ p_{\text{ref}}\big), \qquad H(p,q) = \sqrt{1 - \sum_i \sqrt{p_i\,q_i}}, \qquad F_H = (1-H^2)^2
$$

- p_dev(x): the chip's output at knob settings x (4 000 shots)
- p_ref: the perfect chip's output with the trained knobs
- F_H: Hellinger **fidelity** (1 = identical) — the paper's own metric

**Needs.** The measured distribution.

**Passes on.** The number to minimise → **both** 6A and 6B ("J(x) feeds BOTH methods").

**Code** — `src/metrics.py`, `src/calibration.py → objective`, `src/mitigation.py → ReadoutMitigatedDevice`
```python
def hellinger_distance(p, q):  return float(np.sqrt(max(0.0, 1.0 - bhattacharyya(p, q))))
def hellinger_fidelity(p, q):  return float(bhattacharyya(p, q) ** 2)

def objective(device, reference, x, shots):
    return hellinger_distance(device.run(x, shots), reference)

# mitigation-aware: every histogram the optimiser sees is readout-corrected first
def run(self, x, shots, seed=None):
    return apply_readout_mitigation(self.device.run(x, shots, seed), self.A)
```

**Why this, not something else.** KL divergence becomes infinite when a bin is empty (common with shots); Hellinger is always finite and symmetric. It is also the paper's reporting metric, so results are directly comparable.

---

## §6 Part C — Calibration

> **The job of this part:** find knob settings that make the faulty chip produce the right distribution. Two methods are run side by side on the same objective: **6A** (the paper's, as the baseline) and **6B** (this project's).

### C1 · Eq. 14–17 — Symmetry conditions `BASE PAPER` (side branch)

**In simple words.** Rules from the paper saying which knob ranges give a bell shape rather than a flat or upside-down one. For example: θ₀ = 90° gives symmetry; θ₁ between 90° and 270° gives a bell. This is why the paper fixes θ₀ = 90° and sweeps θ₁ from 90° to 450°.

**Why it is here.** The paper's hand-tuning needs to know where to search. Only 6A uses this; 6B does not.

**Equations (paper Eq. 14–17)**

$$
\theta_0 = \pm\frac{(2n_0+1)\pi}{2}, \qquad \frac{\pi}{2} < \theta_1 < \frac{3\pi}{2}, \qquad \theta_2 = 2\pi n_2 \pm \theta_1, \qquad \frac{\pi}{2} < \theta_2 < \frac{5\pi}{2}
$$

**Needs.** The amplitude formulas from Eq. 12–13.

**Passes on.** Search ranges → **6A only**.

**Code** — the ranges become the sweep settings in `src/stages.py → paper_grid_loader`
```python
if n == 2:   # θ1 from 90° to 450° in 21° steps, then 1° steps
    return grid_sweep(dev, ref, x_nom, [1], [D(np.arange(90, 451, 21))], [D(21)], [D(1)], ...)
# 3 qubits: θ1 and θ2 from 90° to 450° in 36° steps, then 7.5° / 14.5° steps
return grid_sweep(dev, ref, x_nom, [1, 2],
                  [D(np.arange(90, 451, 36)), D(np.arange(90, 451, 36))], ...)
```
Figure `stage06_theta1_sweep_2q.png` reproduces the paper's Fig. 5.

---

### C2 · 6A — Grid sweep `BASE PAPER` (baseline)

**In simple words.** The paper's hand-tuning, automated only so it can be measured: try knob values on a fixed grid, keep the best, then try a finer grid around it. One or two knobs at a time; the rest stay fixed; θ₀ is never tuned.

| Circuit | Knobs swept | Coarse grid | Fine grid |
|---|---|---|---|
| 2-qubit loader | θ₁ | 90°–450°, 21° steps | ±21°, 1° steps |
| 3-qubit loader | θ₁, θ₂ | 90°–450°, 36° steps each | 7.5° (θ₁) / 14.5° (θ₂) steps |
| full circuit | coin angles 2β̃, 2α̃ | ±60° × ±15°, 10° × 3° | 2° × 0.5° |

**Why it is here.** It is the paper's method, reproduced with its exact ranges and steps, so 6B can be compared against it fairly.

**Equation.** No formula — "evaluate J at every grid point, keep the smallest".

**Needs.** J(x) and the Eq. 14–17 ranges.

**Passes on.** Calibrated angles (6A version) → CALIBRATED ANGLES x*.

**Code** — `src/calibration.py → grid_sweep`
```python
xs_c, d_c, pts_c = evaluate(coarse_axes)                     # coarse grid
best_c = xs_c[int(np.argmin(d_c))]
fine_axes = [np.arange(best_c[i] - hw, best_c[i] + hw + 1e-9, st)
             for i, hw, st in zip(indices, fine_half_widths, fine_steps)]
xs_f, d_f, pts_f = evaluate(fine_axes)                       # fine grid around the best
x_best = xs_f[int(np.argmin(d_f))]
```

**Why it falls short.** θ₀ is never tuned, so its drift can't be fixed however fine the grid is; and the number of grid points grows exponentially with the number of knobs.

**Result.** F_H = **0.939 / 0.957** using **347 / 477** circuit runs. Cross-check: the sweep moves the 2-qubit θ₁ from 195° to ≈ 234° — the paper measured 237° and 224° on its real chip.

---

### C3 · 6B — Addition 3: automated calibration `OUR ADDITION` (core novelty)

**In simple words.** An algorithm tunes **all** the knobs automatically, using only the chip's outputs. It works in four steps:
1. **Smart-guess the dice knobs** (Bayesian optimisation, 40 runs).
2. **Smart-guess the coin knobs**, dice knobs frozen (Bayesian optimisation, 30 runs).
3. **Fine-tune all knobs together** (SPSA, 60 steps × 2 runs).
4. **Verify**: re-measure both candidates with more shots, keep the better one.

**Why it is here.** It replaces the paper's manual brute force with an optimiser that is more accurate, cheaper, and needs no person — the core contribution of the project.

**Equations (this project)**

*Bayesian optimisation (BO)* — builds a smooth "map" of J from every point measured so far: a prediction μ and an uncertainty σ everywhere. It measures next where improvement is most likely — either where J is predicted low (exploit) or where the map is unsure (explore):

$$
\mathrm{EI}(x) = (J^* - \mu)\,\Phi(z) + \sigma\,\varphi(z), \qquad z = \frac{J^* - \mu}{\sigma}
$$

*SPSA* — estimates the slope of J in **all** directions from just **two** measurements, by nudging every knob at once in a random ± direction:

$$
\hat g = \frac{J(x + c\Delta) - J(x - c\Delta)}{2c}\,\Delta, \quad \Delta_i \in \{-1,+1\}, \qquad x \leftarrow x - a\,\hat g
$$

**Needs.** J(x). When called from the closed loop, also the current knob settings as a starting point (the arrow coming back from RE-CALIBRATE).

**Passes on.** Calibrated angles (6B version) → CALIBRATED ANGLES x*.

**Code** — `src/calibration.py`
```python
# BO: model the objective, pick the most promising next point
gp.fit(U, y)
m, s = gp.predict(cand)                                   # prediction μ and uncertainty σ
imp = y.min() - m - xi * gp.sd
ei = imp * _norm.cdf(imp / s) + s * _norm.pdf(imp / s)   # Expected Improvement
u_next = cand[int(np.argmax(ei))]

# SPSA: two runs give the whole slope
delta = rng.choice([-1.0, 1.0], size=d)
jp = objective(device, reference, x + ck * delta, shots)
jm = objective(device, reference, x - ck * delta, shots)
x = x - ak * (jp - jm) / (2 * ck) * delta

# the 6B procedure: hierarchical_calibration
loader_result = bayesian_opt(loader_dev, loader_ref, x_start[:n], shots, budget=40, ...)   # step 1
r2 = bayesian_opt(SubspaceDevice(gci_dev, x1, [n, n + 1]), gci_ref, ..., budget=30)       # step 2
r3 = spsa(gci_dev, gci_ref, x2, shots, n_iter=60, c=0.06, target_first_step=0.05)         # step 3
x_best = r3.x_best if f3 >= f2 else x2                                                     # step 4
```
Run per register by `src/stages.py → stage06_loader` and `stage06_gci`, which also run two **ablations** (one SPSA, or one BO, on all knobs at once). Narrated in `06_hardware_retuning.ipynb`; output `results/stage06_retuning.json`.

**Why this, not something else.**
- Grid search (6A): cost explodes with the number of knobs.
- Parameter shift on the chip: 2 runs **per knob** per step, and noisy; SPSA needs 2 runs per step **in total**.
- BO alone stalls in five dimensions (0.964 for 3 qubits); SPSA alone converges slowly from a poor start (0.947). **BO places the knobs globally, SPSA refines them locally** — together 0.994.
- Dice first, then coin — mirrors the paper's own order, and splits one hard 5-knob problem into an easy 3-knob and an easy 2-knob one.

**Result (full GCI circuit)**

| Register | Method | Circuit runs | F_H |
|---|---|---|---|
| 2-qubit | uncalibrated | 0 | 0.923 |
| 2-qubit | 6A grid sweep | 347 | 0.939 |
| 2-qubit | **6B automated** | **204** | **0.982** |
| 2-qubit | ablation: SPSA only / BO only | 308 / 70 | 0.982 / 0.973 |
| 3-qubit | uncalibrated | 0 | 0.910 |
| 3-qubit | 6A grid sweep | 477 | 0.957 |
| 3-qubit | **6B automated** | **204** | **0.994** |
| 3-qubit | ablation: SPSA only / BO only | 308 / 70 | 0.947 / 0.964 |

---

### C4 · CALIBRATED ANGLES x*

**In simple words.** The corrected knob settings that will be sent to the chip from now on. Three sets are kept for comparison: **uncalibrated** (trained, as is), **6A** and **6B**.

**Why it is here.** Execution needs fixed knob settings; keeping all three makes the comparison in Part D fair.

**Needs.** The output of 6A and 6B.

**Passes on.** → Addition 4 (execution).

**Code** — `src/stages.py → stage06_gci`, saved by `save_stage06` to `results/stage06_retuning.json`
```python
params = {"uncalibrated": x0.tolist(), "grid_6A": np.asarray(g.x_best).tolist(),
          "auto_6B": np.asarray(h.x_best).tolist()}
```

---

## §7 Part D — Execution and mitigation

### D1 · Addition 4 — Repeated execution `OUR ADDITION`

**In simple words.** Runs each version of the circuit **20 separate times × 20 000 shots** and reports the average and the spread. A probability near 0.25 measured with 20 000 shots is accurate to about ±0.3 %.

**Why it is here.** One run could be lucky. Repetition gives error bars, so "6B is better than 6A" is proven, not assumed.

**Equation.** Statistical error of a measured probability: √(p(1 − p)/N).

**Needs.** The calibrated angles.

**Passes on.** Raw measured histograms → Addition 5.

**Code** — `src/stages.py → execute_variants` (settings `N_REPEATS = 20`, `SHOTS_EXECUTION = 20000` in `src/config.py`)
```python
for r in range(n_repeats):
    s = seed0 + 1000 * r                                   # new random seed each repetition
    p_unc = dev.run(x_unc, shots, seed=s)
    runs["noisy_uncalibrated"].append(p_unc)
    runs["uncalibrated_REM"].append(apply_readout_mitigation(p_unc, A))
    runs["6A_grid_REM"].append(apply_readout_mitigation(dev.run(x_6a, shots, seed=s + 1), A))
    runs["6B_auto_REM"].append(apply_readout_mitigation(dev.run(x_6b, shots, seed=s + 2), A))
    runs["6B_auto_REM_ZNE"].append(run_zne(dev, x_6b, shots, ..., readout_A=A)[0])
```
Narrated in `07_run_on_backend.ipynb`; output `results/stage07_execution.json`.

---

### D2 · Addition 5 — Readout mitigation `OUR ADDITION`

**In simple words.** First, measure **how** the chip misreads: prepare every possible outcome, measure it, and record what comes out — this table is the matrix A. Then "undo" A on every real measurement to recover what the chip actually produced.

**Why it is here.** Readout error is one of the paper's three named error sources, and the paper applied no correction (it lists this as future work).

**Equation (this project)**

$$
A_{is} = P(\text{read } i \mid \text{prepared } s), \qquad m = A\,p, \qquad \hat p = \arg\min_{p \ge 0}\ \lVert A p - m\rVert
$$

m = measured distribution; p = true distribution. Solving with "p ≥ 0" (NNLS) keeps the answer a valid probability distribution.

**Needs.** Raw histograms and the matrix A.

**Passes on.** The readout-corrected distribution → either straight to the corrected distribution (the **deployed path**, the dashed bypass in the diagram) or through ZNE.

**Code** — `src/mitigation.py`
```python
def assignment_matrix(device, shots=20000, seed=77):
    for s in range(2 ** n_bits):                     # prepare every outcome |s⟩
        for q_phys, c in meas:
            if (s >> c) & 1:
                qc.x(q_phys)                          # on the same real qubits the circuit uses
    ...

def apply_readout_mitigation(p_measured, A):
    p, _ = nnls(A, np.asarray(p_measured, dtype=float))   # undo the misreads
    return p / p.sum()
```

**Why this, not something else.** Simply inverting A can give negative "probabilities"; NNLS cannot. With 3–4 measured bits the full table is small (16 × 16) and also captures errors that affect several qubits at once.

**Result.** On its own it **cannot** fix drift (uncalibrated + correction: 0.92 / 0.91). After 6B retuning it gives the deployed result: **0.982 / 0.995**.

---

### D3 · Addition 6 — Zero-noise extrapolation `OPTIONAL`

**In simple words.** Deliberately make the noise worse — 3× and 5× — by running the circuit forwards, backwards and forwards again (which logically does nothing but triples the operations). Watch how each result changes as the noise grows, and extend that trend back to **zero noise**.

**Why it is here.** It targets the gate noise left over after retuning and readout correction. The paper only discussed it.

**Equation (this project)**

$$
U \to U\,(U^\dagger U)^k, \quad \lambda = 2k+1 \in \{1, 3, 5\}, \qquad p(\lambda) \approx a + b\,\lambda \;\Rightarrow\; p(0) \approx a
$$

**Needs.** Runs at the three noise levels, each readout-corrected.

**Passes on.** The extrapolated distribution → the corrected distribution.

**Code** — `src/mitigation.py`
```python
def fold_circuit(bound_tqc, scale):
    for _ in range((scale - 1) // 2):
        folded.compose(inv, inplace=True)        # U†
        folded.compose(body_nb, inplace=True)    # U
    return transpile(folded, basis_gates=NATIVE_GATES, optimization_level=0)   # don't simplify U†U away

def zne_extrapolate(scales, prob_list, order=1):
    coeffs = np.polyfit(scales, P, order)        # straight-line fit per outcome
    p0 = np.clip(coeffs[-1], 0, None)            # value at zero noise
    return p0 / p0.sum()
```

**Why optional.** The gain is real but small after retuning, it costs up to 1 + 3 + 5 = **9×** the gate time, and it does not reliably improve the risk numbers (it brings expected loss closer for the 2-qubit register but overshoots for the 3-qubit one). A straight-line fit is used because a curved fit through three noisy points exaggerates noise.

**Result.** 0.982 → **0.998** (2-qubit), 0.995 → **0.996** (3-qubit).

---

### D4 · CORRECTED DISTRIBUTION p(default, z)

**In simple words.** The final, cleaned probability of every (default yes/no, economy bin) outcome.

**Why it is here.** Every financial number in Part E is computed from this one distribution.

**Needs.** Readout correction (plus ZNE in the optional variant).

**Passes on.** → post-processing.

**Code.** The `mean_probs` of each variant in `results/stage07_execution.json`.

---

## §8 Part E — Risk numbers

### E1 · Post-processing `BASE PAPER (Sec. IV-C)`

**In simple words.** Turns bitstrings into money, exactly as the paper does. For every outcome:
- the **right bits** give the economy bin;
- the **left bit** says default (1) or not (0); a default costs $1000.

Add up the probabilities of equal losses → a loss distribution (PDF) → its running total (CDF) → expected loss.

**Why it is here.** A bank needs a loss distribution, not a list of bitstrings.

**Equations**

$$
b = i \bmod 2^n, \quad d = \lfloor i / 2^n \rfloor, \qquad \text{loss} = d \times \mathrm{LGD}, \qquad
F(L) = \sum_{L' \le L} P(L'), \qquad \mathbb{E}[L] = \sum_L L\,P(L)
$$

**Needs.** The corrected distribution.

**Passes on.** The loss CDF and the joint distribution p(default, z) → Addition 7.

**Code** — `src/postprocessing.py`
```python
def decompose(probs, n, n_assets=1):
    for idx, p in enumerate(probs):
        b = idx & (n_z - 1)          # rightmost n bits → economy bin
        d = idx >> n                 # leftmost bit(s)  → default
        joint[d, b] += p

def credit_statistics(probs, n, lgd=LGD, ...):
    p_z = joint.sum(axis=0)                                   # P(economy bin)
    pdf = [scenario_prob[scenario_loss == L].sum() for L in unique_losses]
    cdf = np.cumsum(pdf)
    expected_loss = np.sum(unique_losses * pdf)
```
Narrated in `08_classical_postprocessing.ipynb`; output `results/stage08_postprocessing.json`.

**Result.** Noiseless: P(loss = 0) = 0.748 / 0.746 and P(loss ≤ $1000) = 1 — the paper's Fig. 10.

---

### E2 · Addition 7 — Conditional-default check `OUR ADDITION`

**In simple words.** From the measured results, work out "how often did the borrower default **in each economy bin**?" and compare that with the Vasicek formula (Eq. 1). Also compute four fidelity scores that separate different kinds of error.

**Why it is here.** A histogram can look fine while the finance inside it is wrong. This checks that the **financial model itself** survived the noise. It also uses Eq. 1 a second time — the finance model both starts and closes the chain.

**Equation (this project)**

$$
P(\text{default} \mid z_b) = \frac{p(1, b)}{P(Z = z_b)}
$$

| Fidelity | Compares | A low value means |
|---|---|---|
| vs perfect circuit | chip output vs noiseless circuit | chip error is left (**used for ACCEPT**) |
| vs classical model | chip output vs Eq. 1 + Eq. 10 | chip error + modelling error |
| loss distribution | P(loss = 0), P(loss = $1000) vs classical | default probability is off |
| economy bins | economy part vs target bell curve | the dice are off |

**Needs.** The joint distribution and Eq. 1.

**Passes on.** The loss CDF and the distributions → VaR & Hellinger.

**Code** — `src/postprocessing.py` and `src/stages.py → fidelity_table`
```python
cond_pd = joint[1:].sum(axis=0) / p_z            # P(default | economy bin)

# classical reference built from Eq. 1 + Eq. 10
out[: 2 ** n] = p_z * (1 - pd)                    # no default
out[2 ** n:] = p_z * pd                           # default
```

**Result.** After calibration the recovered default curve follows the Vasicek curve again (`stage08_conditional_pd.png`).

---

### E3 · VaR & Hellinger fidelity `BASE PAPER`

**In simple words.**
- **VaR₉₅**: the smallest loss L such that the bank is at least 95 % sure the loss won't exceed it.
- **Hellinger fidelity**: one score from 0 to 1 for how closely two distributions match.

**Why it is here.** These are the two numbers the paper reports.

**Equations**

$$
\mathrm{VaR}_{0.95} = \min\{L : F(L) \ge 0.95\}, \qquad F_H = \Big(\sum_i \sqrt{p_i\,q_i}\Big)^2
$$

**Needs.** The loss CDF and the distributions.

**Passes on.** F_H → Part F.

**Code** — `src/postprocessing.py → value_at_risk`, `src/metrics.py → hellinger_fidelity`
```python
def value_at_risk(unique_losses, cdf, confidence=CONFIDENCE):
    idx = int(np.searchsorted(np.asarray(cdf) - 1e-12, confidence))
    return float(unique_losses[min(idx, len(unique_losses) - 1)])
```

**Result.** VaR₉₅ = **$1000** for every version — the paper's value.

**Important point.** With one borrower the loss is either $0 or $1000, and P(loss = 0) ≈ 0.75 < 0.95, so **any** reasonable distribution gives VaR = $1000 — even the uncalibrated one. That is why the fidelity, not the VaR, is the real test. The paper says the same.

---

## §9 Part F — Closed loop

### F1 · Addition 8 — Fidelity gate: F_H ≥ 0.97 ? `OUR ADDITION`

**In simple words.** An automatic "is it still good?" check on the deployed pipeline (6B knobs + readout correction):
- **YES → ACCEPT** — the distribution is validated and the VaR is reported.
- **NO → RE-CALIBRATE** — go back to 6B, starting from the current knobs, and check again. This is the long arrow up the right side of the diagram.

**Why it is here.** Real chips drift — their calibration changes from day to day. The paper calibrates once, by hand. This system notices when it has gone wrong and repairs itself.

**Equation (this project)**

$$
F_H(\text{6B + readout correction}) \ge 0.97 \;\Rightarrow\; \text{ACCEPT}; \quad \text{otherwise} \;\Rightarrow\; \text{RE-CALIBRATE}
$$

**Needs.** The fidelity F_H.

**Passes on.** Either done (ACCEPT), or the current knobs back to 6B (RE-CALIBRATE).

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
The "chip changed overnight" test uses completely new drift values (`DRIFT_EPS_DAY2`, `DRIFT_DELTA_DEG_DAY2` in `src/config.py`). Narrated in `09_var_fidelity_check.ipynb`; outputs `results/stage09_final_report.json` and `results/FINAL_REPORT.md`.

**Why 0.97.** Close to the paper's 98.9 % hardware result while leaving room for shot noise; it can be changed in `src/config.py`. The deployed pipeline is 6B + readout correction (not + ZNE) because it needs only one circuit per estimate.

**Result.**
- Today's chip: 0.982 / 0.995 → **ACCEPT**.
- After the drift event: yesterday's knobs give **0.53 / 0.68** → RE-CALIBRATE → 6B re-runs itself (204 runs) → **0.97 / 0.99** → ACCEPT. A manual re-sweep would cost 347 / 477 runs and a person.

### F2 · Execution environment

**In simple words.** Everything above runs on a laptop with Qiskit's simulator — no real quantum chip is needed. The noise model carries the three error sources the paper names (gate noise, readout errors, drift), and the drift is hidden from every calibration method. The whole pipeline runs in about 75 seconds.

---

## §10 Supporting files, one run end to end, and checklist

### 10.1 Supporting files (the glue)

| File | What it does | Why it exists |
|---|---|---|
| `src/config.py` | every setting: p₀, ρ, LGD, gate set, chip layout, noise and drift values, shots, budgets, threshold | change one number in one place |
| `src/pipeline_io.py` | each stage finds the previous stage's saved output; falls back to recomputing | stages can run alone or together |
| `src/stages.py` | the core of Stages 6–9 | notebooks and scripts run the **same** code, so results are identical |
| `src/report.py` | writes `results/FINAL_REPORT.md` | one-page summary |
| `run_pipeline.py` | runs notebooks 00 → 09 in order (`--from`, `--to`, `--mode scripts`) | one command reproduces everything |
| `main.ipynb` | runs the whole pipeline and shows the headline results | the demo |
| `scripts/run_stage0X_*.py` | headless runner per stage | fast runs without notebook output |
| `00_overview.ipynb` | the problem, the gaps, parameter-shift check, Adam demo | the "why" before the "how" |
| `01…09_*.ipynb` | narrated version of each stage, with plots | learning and presenting |
| `images/build_quantum_diagram.py` | draws `images/quantum_architecture.png` | keeps the diagram in sync |
| `requirements.txt` | qiskit, qiskit-aer, numpy, scipy, matplotlib, pylatexenc, jupyter, ipykernel, nbclient, nbformat | reproducible setup |

### 10.2 One run, end to end, following the numbers

1. **Eq. 1:** p₀ = 0.25, ρ = 0.027 → PD(recession) = 0.43, PD(boom) = 0.12.
2. **Eq. 10:** 2-qubit bins at z = −3, −1, +1, +3 → target ≈ [0.009, 0.491, 0.491, 0.009].
3. **Eq. 2–3:** α = −3.47°, β = 30.03°, error < 0.007.
4. **Eq. 4:** β̃ = 40.42°, α̃ = −6.93° → Ry(80.8°) + CRy(−13.9°) + CRy(−27.7°).
5. **Eq. 5–13 + training:** θ* = [90°, 195.4°], loss 2 × 10⁻⁸.
6. **Full circuit + SABRE:** 3 qubits → depth 33, 8 CZ gates on a line of 4 qubits.
7. **Addition 1:** on the faulty chip the trained knobs give F_H = 0.88.
8. **6A:** grid sweep → 0.939 in 347 runs (θ₁ → ≈ 234°, as in the paper).
9. **6B:** BO → BO → SPSA → 0.982 in 204 runs.
10. **Additions 4–5:** 20 × 20 000 shots + readout correction → 0.982 ± 0.002.
11. **Addition 6 (optional):** ZNE → 0.998.
12. **Post-processing:** P(loss = 0) ≈ 0.73–0.75, expected loss ≈ $245–273 (classical $250), VaR = $1000.
13. **Addition 7:** the recovered default curve follows Vasicek again.
14. **Addition 8:** 0.982 ≥ 0.97 → ACCEPT. After drift: 0.53 → recalibrate → 0.97 → ACCEPT.

### 10.3 "Nothing left out" checklist

**Every block of the diagram**

| Block | Section |
|---|---|
| Eq. 1 Vasicek PD(z) | A1 |
| Eq. 2 Linearise onto the Born rule | A2 |
| Eq. 3 Rotation angle | A3 |
| Eq. 4 Register-indexed asset gates | A4 |
| Eq. 10 Target Gaussian | A5 |
| Eq. 5 Register size | A6 |
| Eq. 6 Goal state | A7 |
| Eq. 12, 13 Ry matrix + CNOT | A8 |
| Eq. 8, 9 Circuit histogram | A9 |
| Eq. 11 MSE loss | A10 |
| Parameter-shift gradient | A11 |
| Adam update | A12 |
| FULL GCI CIRCUIT | A13 |
| SABRE transpilation | A14 |
| Addition 1 Noise-emulated device | B1 |
| Addition 2 Calibration objective | B2 |
| Eq. 14–17 Symmetry conditions | C1 |
| 6A Grid sweep | C2 |
| 6B Addition 3 Automated calibration | C3 |
| CALIBRATED ANGLES x* | C4 |
| Addition 4 Repeated execution | D1 |
| Addition 5 Readout mitigation | D2 |
| Addition 6 Zero-noise extrapolation | D3 |
| CORRECTED DISTRIBUTION | D4 |
| Sec. IV-C Post-processing | E1 |
| Addition 7 Conditional-default check | E2 |
| VaR & Hellinger fidelity | E3 |
| F_H ≥ 0.97 gate, ACCEPT, RE-CALIBRATE | F1 |
| Execution environment | F2 |

**Every code file**

| File | Sections |
|---|---|
| `gci_model.py` | A1, A5 |
| `quantum_encoding.py` | A2, A4 |
| `vqc_circuit.py` | A4, A6, A8, A13 |
| `training.py` | A9, A12 |
| `parameter_shift.py` | A10, A11 |
| `adam.py` | A12 |
| `transpilation.py` | A13, A14 |
| `noise_model.py`, `device.py` | B1 |
| `metrics.py` | B2, E3 |
| `calibration.py` | B2, C2, C3 |
| `mitigation.py` | B2, D2, D3 |
| `postprocessing.py` | E1, E2, E3 |
| `stages.py` | C1, C3, C4, D1, E2, F1, §10.1 |
| `config.py`, `pipeline_io.py`, `report.py`, runners, notebooks, diagram script | §10.1 |

**The three kinds of equation**

| Kind | Count | Where |
|---|---|---|
| Implemented exactly as the paper prints them | 16 (Eq. 1–6, 8–17, parameter shift, Adam, post-processing, VaR) | Part A, C1, E1, E3 |
| Modified with a reason | 4 (α/β fitting, transpilation, retuning procedure, Hellinger as objective) | A2, A14, C3, B2 |
| Added by this project | 6 groups (device model, BO/SPSA, readout mitigation, ZNE, conditional default, acceptance gate) | B1, C3, D2, D3, E2, F1 |

---

## §11 Glossary and likely questions

### 11.1 Glossary

| Term | Plain meaning |
|---|---|
| Ansatz | the fixed layout of a trainable circuit (where the knobs and CNOTs go) |
| Amplitude | the number attached to each outcome of a qubit state; its square is the probability |
| Assignment matrix | table of how the chip misreads each outcome |
| Bayesian optimisation | smart guessing: builds a map of the score and tries the most promising point next |
| CDF | running total of probabilities: P(loss ≤ L) |
| CNOT | two-qubit gate that flips one qubit when the other is 1; creates correlations |
| Coupling map | which real qubits can talk to each other directly |
| Depolarizing noise | each operation slightly randomises the state |
| Drift | the chip's knobs over- or under-turn by a fixed, unknown amount |
| Fidelity (Hellinger) | how alike two distributions are, from 0 to 1 |
| GCI / Vasicek model | the bank's model: defaults are independent once the economy is known |
| LGD | loss given default — here $1000 |
| NISQ | today's noisy, small quantum chips |
| Parameter shift | exact way to get a circuit's slope from two runs |
| PD | probability of default |
| QAE | Quantum Amplitude Estimation — the quadratically faster replacement for Monte Carlo |
| Readout mitigation | undoing measurement misreads |
| Ry | rotation gate; sets the probability of reading 1 |
| SABRE | algorithm that fits a circuit onto a chip's layout |
| Shot | one run and measurement of the circuit |
| SPSA | gets the slope in all directions from two runs |
| Transpilation | rewriting a circuit for a specific chip |
| VaR | Value at Risk: the loss you're 95 % sure not to exceed |
| ZNE | zero-noise extrapolation: increase the noise on purpose, then extend the trend back to zero |

### 11.2 Questions a professor is likely to ask

**Why use a quantum computer for credit risk at all?** Monte Carlo error shrinks as 1/√N; Quantum Amplitude Estimation shrinks as 1/N — a quadratic speed-up. Loading the model correctly, which this project does, is its first building block.

**Why is default written as sin²(αz + β)?** A rotation Ry(2φ) gives P(1) = sin²φ exactly. Making φ a straight line in z means a few simple gates encode the whole default curve.

**Why do trained angles fail on hardware?** Real chips over- and under-rotate (drift), misread results and add gate noise; the perfect simulator used for training has none of these.

**What exactly is your contribution?** Replacing the paper's manual angle sweep with automated, noise-aware calibration (BO → BO → SPSA); adding readout mitigation and ZNE; and closing the loop so drift is detected and repaired automatically.

**How do you know the calibration isn't cheating?** The drift values are never given to any method; the optimisers only see measured results.

**Why not just SPSA or just BO?** The ablations: SPSA alone 0.947, BO alone 0.964 on the 3-qubit register; together 0.994.

**Why is VaR $1000 for every version?** With one borrower the loss is $0 or $1000 and P(loss = 0) ≈ 0.75 < 0.95, so the 95 % point is always $1000. That is why the full distribution is judged with fidelity.

**Why is the 3-qubit match with the ideal bell curve only about 0.78?** The paper's star design has too few knobs to draw an 8-bin bell curve exactly; a chain layout does better. It is reported as a limitation.

**Does this run on a real quantum computer?** No — on a simulator with an emulated noise model. The calibration loop only needs measured counts, so it could run unchanged on real IBM hardware; that is the first item of future work.

**How does it compare with the paper's 98.9 %?** 98.2 % (2-qubit register) and 99.5 % (3-qubit register) after automated calibration and readout correction — similar in size, but on an emulated device rather than real hardware.

---

*All results in this guide come from the project's own pipeline run on a simulator with an emulated noise model, not from a physical quantum processor.*
