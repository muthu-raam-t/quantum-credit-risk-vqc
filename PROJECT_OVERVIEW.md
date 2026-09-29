# Project Overview — Variational Quantum Modeling for Portfolio Credit Risk

**An Adaptive Quantum Circuit Framework for the GCI Uncertainty Model**

Team 16 · Quantum Computing & Algorithms (23AID302) · School of Artificial Intelligence, Amrita Vishwa Vidyapeetham, Coimbatore · Academic Year 2026–27
Faculty in charge: Snigdhatanu Acharya
Team: Lalith Sagar (CB.AI.U4AID24009) · Ruthwik (CB.AI.U4AID24023) · Muthu Raam (CB.AI.U4AID24058) · Prapul Chandra (CB.AI.U4AID24063)

Base paper: H. G. Ahmad et al., *"Quantum Circuit-Based Adaptation for Credit Risk Analysis,"* IEEE Transactions on Quantum Engineering, vol. 7, 3103316, 2026. DOI: 10.1109/TQE.2026.3691176

---

## Contents

1. [The project in one page](#1-the-project-in-one-page)
2. [The finance problem: credit risk](#2-the-finance-problem-credit-risk)
3. [The quantum computing background](#3-the-quantum-computing-background)
4. [The base paper](#4-the-base-paper)
5. [Our objectives and novelty](#5-our-objectives-and-novelty)
6. [System architecture](#6-system-architecture)
7. [Stage-by-stage walkthrough](#7-stage-by-stage-walkthrough)
8. [Results](#8-results)
9. [Discussion — what the results mean](#9-discussion--what-the-results-mean)
10. [Limitations](#10-limitations)
11. [Future work](#11-future-work)
12. [Glossary](#12-glossary)
13. [Likely review questions — with answers](#13-likely-review-questions--with-answers)
14. [Suggested presentation structure](#14-suggested-presentation-structure)

---

## 1. The project in one page

**The question.** How much could a bank lose if its borrowers default? Regulators require banks to answer this with a number called **Value at Risk (VaR)**. The standard model behind it — the **Gaussian Conditional-Independence (GCI)** model, also known as the one-factor **Vasicek** model — is normally evaluated with millions of Monte Carlo simulations.

**Why quantum.** A quantum algorithm called **Quantum Amplitude Estimation (QAE)** can estimate the same risk numbers with quadratically fewer samples (error ∝ 1/N instead of 1/√N). Before QAE can run, the credit model itself must be *loaded* into a quantum circuit: the circuit must produce the correct joint distribution of "state of the economy" and "borrower defaults". This loading circuit is the subject of the base paper and of this project.

**The obstacle.** Today's quantum computers are **NISQ** devices (Noisy Intermediate-Scale Quantum). Their rotation pulses are miscalibrated, their readout flips bits, their gates add noise, and their qubits are only connected to neighbours. A circuit trained on a perfect simulator gives the *wrong* distribution on a real chip.

**What the base paper did.** It built the loading circuit, trained it on a simulator, adapted it to its chip's connectivity (transpilation), and then fixed the angles **by hand**: sweeping one or two rotation angles on a grid, degree by degree, directly on the hardware, until the output looked right. It reached a Hellinger fidelity of 98.9 % against the simulated distribution.

**What we did.**
1. **Replicated** the entire pipeline from scratch in Qiskit — 9 stages, from the classical model to the final VaR.
2. **Built a realistic noisy device** in simulation, with the three error sources the paper identifies: gate (depolarizing) noise, readout errors, and coherent control drift.
3. **Replaced the manual grid sweep with an automated calibration loop** (Bayesian optimisation + SPSA) that reaches higher accuracy with fewer circuit runs.
4. **Benchmarked error mitigation** (readout mitigation, zero-noise extrapolation) — which the paper does not apply.
5. **Closed the loop:** when the device drifts and the accuracy check fails, the calibration re-runs itself automatically.

**Headline result.** Automated calibration: fidelity **0.982 / 0.994** (2-qubit / 3-qubit register) with **204** circuit runs, versus **0.939 / 0.957** with **347 / 477** runs for the paper-style grid sweep. The replicated risk figures match the paper: P(L ≤ 0) ≈ 0.75, P(L ≤ 1000) = 1, 95 % VaR = $1000.

---

## 2. The finance problem: credit risk

### 2.1 Basic terms

| Term | Meaning | Value in this project |
|---|---|---|
| **Default** | A borrower fails to repay | — |
| **PD** — probability of default | Chance that the borrower defaults within the horizon | baseline p₀ = 0.25 |
| **LGD** — loss given default | Money lost if the borrower defaults | $1000 |
| **Expected loss (EL)** | Average loss = PD × LGD for one borrower | ≈ $250 |
| **VaR at 95 %** | The loss that is *not exceeded* with 95 % probability | $1000 |
| **CDF of losses** | P(Loss ≤ L) for every loss level L | read VaR from it |

**Value at Risk, formally:** VaR₀.₉₅ = the smallest loss L such that P(Loss ≤ L) ≥ 0.95.

### 2.2 Why defaults are correlated — the latent factor

Borrowers do not default independently: in a recession *many* default together. The GCI model captures this with one shared, hidden (**latent**) variable z — think of it as "the state of the economy" — distributed as a standard normal, z ~ N(0, 1). Negative z is a bad economy, positive z a good one.

Given z, each borrower defaults independently (hence "conditional independence") with probability

$$
\mathrm{PD}(z) = \Phi\!\left(\frac{\Phi^{-1}(p_0) - \sqrt{\rho}\,z}{\sqrt{1-\rho}}\right)
$$

- Φ is the standard normal CDF, Φ⁻¹ its inverse.
- p₀ is the baseline default probability (0.25 here).
- ρ is the **asset correlation** — how strongly the borrower depends on the economy (0.027 here, the paper's value).

With these values, PD(z) falls from ≈ 0.43 in a bad economy (z = −3) to ≈ 0.12 in a good one (z = +3), and averages back to 0.25.

### 2.3 The classical way to compute VaR

Monte Carlo: draw z, draw a default with probability PD(z), record the loss; repeat millions of times; read the 95 % point from the histogram of losses. Accuracy improves only as 1/√N — halving the error needs four times as many samples. For large portfolios with many correlated risk factors this becomes the computational bottleneck of bank capital calculations.

### 2.4 Where the quantum speed-up comes from

Quantum Amplitude Estimation estimates a probability with error ∝ 1/N instead of 1/√N — a **quadratic speed-up** over Monte Carlo (Montanaro, 2015; Egger et al., 2021). QAE needs, as its first ingredient, a circuit that *prepares the uncertainty model* — a quantum state whose measurement outcomes follow the GCI distribution. This project is about building that ingredient so that it works on noisy hardware.

---

## 3. The quantum computing background

### 3.1 Qubits, rotations, entanglement, measurement

- A **qubit** is in a superposition α|0⟩ + β|1⟩; measuring it gives 0 with probability |α|² and 1 with probability |β|².
- The **R<sub>y</sub>(θ)** rotation turns |0⟩ into cos(θ/2)|0⟩ + sin(θ/2)|1⟩, so **P(1) = sin²(θ/2)**. A single angle therefore sets a probability.
- **CNOT** flips a target qubit when the control is 1. It creates **entanglement** — correlations between qubits — and is what lets a few qubits represent a shaped distribution.
- A **controlled-R<sub>y</sub>** rotates a target only when the control qubit is 1 — this is how the default qubit is made to depend on z.
- **Measurement** returns one bitstring per run ("shot"). A distribution is only visible as the histogram of many shots.

### 3.2 Amplitude encoding of a distribution

With n qubits there are 2ⁿ basis states |b⟩. A state Σ_b √p_b |b⟩ produces bitstring b with probability p_b. Assign each b a grid value z_b between −3 and +3, and the register becomes a **discretised probability distribution** over z. Two qubits give 4 bins, three qubits give 8.

### 3.3 Variational Quantum Circuits (VQC)

A VQC is a fixed circuit structure (**ansatz**) with tunable angles θ. A classical optimiser adjusts θ to minimise a loss computed from the circuit's output. It is the quantum analogue of training a neural network, and it suits NISQ devices because the circuits are shallow.

### 3.4 The parameter-shift rule

For rotation gates, the exact gradient of a circuit's output can be computed from two extra circuit runs:

$$
\frac{\partial f}{\partial \theta_i} = \frac{f(\theta_i + \pi/2) - f(\theta_i - \pi/2)}{2}
$$

No backpropagation through the quantum device is needed — this is what allows gradient-based training (with Adam) of a quantum circuit.

### 3.5 NISQ noise — the three error sources

| Error | Physical cause | Effect | What fixes it |
|---|---|---|---|
| **Coherent control drift** | microwave pulse amplitude/phase slightly wrong | every rotation is systematically over- or under-rotated | re-tuning the angles (Stage 6) |
| **Readout error** | qubit decays or is misread during measurement | 0 read as 1 or 1 read as 0 | readout-error mitigation (Stage 7) |
| **Depolarizing gate noise** | decoherence during gates, especially two-qubit gates | output drifts toward uniform randomness | zero-noise extrapolation (Stage 7), shorter circuits |

### 3.6 Transpilation

Real chips support only a few **native gates** (here `rz`, `sx`, `x`, `cz`) and only let **neighbouring** qubits interact. **Transpilation** rewrites a circuit into native gates and inserts SWAP operations where two non-neighbouring qubits must interact. **SABRE** (SWAP-based bidirectional heuristic search) chooses the qubit placement and the SWAPs that keep the circuit as short as possible.

---

## 4. The base paper

**Ahmad et al., IEEE Transactions on Quantum Engineering, 2026** — a collaboration of the University of Naples Federico II, G2Q Computing and the bank Intesa Sanpaolo.

### 4.1 What the paper did

1. Mapped the one-asset / one-risk-factor GCI model to a **3-qubit circuit**: 2 qubits load a Gaussian over z, 1 qubit encodes default.
2. Wrote PD(z) as **sin²(αz + β)** so default becomes a single rotation whose angle depends linearly on z.
3. Trained the Gaussian loader with **parameter-shift gradients and Adam** on a noiseless simulator.
4. **Transpiled** the circuit with Qiskit's preset pass manager and SABRE for their chip.
5. Ran it on a real superconducting processor — **Contralto-D** (QuantWare, 17 transmon qubits) at the Partenope quantum computing centre, Naples.
6. Found the trained angles did not work on hardware and **re-tuned them by hand**: θ₁ swept from 90° to 450° in 21° steps, then 1° steps; three-qubit angles in 36° steps then 7.5° / 14.5°; the full circuit's asset angles on a 2-D grid (their Table 3).
7. Post-processed the bitstrings into a loss CDF and compared with the simulation.

### 4.2 What the paper found

- Optimal angles on hardware differ from the simulator's (θ₁: trained 111° → hardware 237° on qubits D3–C4, 224° on D3–A6) and **differ between qubit pairs** — offline, hardware-agnostic optimisation is not enough.
- The final hardware distribution matched the simulated one with **Hellinger fidelity 98.9 ± 0.3 %**; CDF: P(L ≤ 0) ≈ 0.75, P(L ≤ 1000) = 1, VaR = $1000.
- Three noise sources should be modelled: **readout noise, phase errors, depolarizing errors**.

### 4.3 The gaps we address

| Gap in the paper | Our response |
|---|---|
| Angle tuning is manual and brute-force; cost grows exponentially with the number of angles | Automated closed-loop calibration (Bayesian optimisation + SPSA) |
| No error mitigation applied (stated as future work) | Readout mitigation and zero-noise extrapolation, benchmarked |
| Calibration is a one-off; the chip drifts | Stage 9 acceptance check that triggers re-calibration automatically |
| Requires a physical chip | Fully reproducible on a laptop with an emulated noisy device |

---

## 5. Our objectives and novelty

**Objectives**

1. **Variational Gaussian loading** — 2-qubit and 3-qubit R<sub>y</sub> + CNOT circuits that reproduce a discrete standard normal distribution.
2. **Hybrid quantum optimisation** — train the angles with an Adam loop driven by exact parameter-shift gradients.
3. **Noise-resilient risk analysis** — emulate NISQ noise in Qiskit Aer and recover the correct loss CDF and VaR.

**Novelty contributions**

1. **Automated in-situ calibration (Stage 6B)** — a hierarchical optimiser that replaces the manual grid sweep: fewer circuit runs, higher accuracy, no human in the loop.
2. **Mitigation-aware calibration** — angles are tuned on readout-corrected data, so retuning and readout mitigation do not both correct the same error twice.
3. **Error-mitigation benchmark (Stage 7)** — quantifies what readout mitigation and zero-noise extrapolation add on top of retuning.
4. **Closed-loop acceptance (Stage 9)** — an ACCEPT / RE-CALIBRATE decision that detects device drift and repairs it automatically.

---

## 6. System architecture

```
 1. Classical GCI model (Vasicek PD(z))
             │
 2. Quantum encoding  PD(z) ≈ sin²(αz + β)  →  Ry(2(αz + β))
             │
 3. Circuit design   z-register (Ry + CNOT)  +  asset qubit (controlled-Ry)
             │
 4. Classical training   parameter-shift gradients + Adam
             │
 5. Transpilation   SABRE layout/routing → native rz, sx, x, cz
             │
     ┌───────┴────────┐
 6A. Baseline       6B. Automated
     grid sweep         BO → BO → SPSA
     (base paper)       (this project)
     └───────┬────────┘
 7. Execution on the noise-emulated backend  (+ readout mitigation, ZNE)
             │
 8. Classical post-processing   bitstrings → loss PDF → CDF
             │
 9. VaR & fidelity check ── fidelity ≥ threshold ──► ACCEPT
             │
             └── fidelity < threshold ──► RE-CALIBRATE (re-run 6B)
```

**"As in the base paper" vs "as implemented here":** the paper executes on a real superconducting chip and retunes by hand; we execute on Qiskit's AerSimulator with an emulated noise model and retune automatically. Every other stage follows the paper.

---

## 7. Stage-by-stage walkthrough

Each stage is a notebook (`0X_*.ipynb`) that explains *what*, *why*, *where it fits*, the maths, and the implementation, and saves its outputs to `results/` for the next stage.

### Stage 0 — Overview (`00_overview.ipynb`)

Sets up the problem, the base paper's gaps, and the three algorithms everything relies on: the VQC, the parameter-shift rule (verified numerically against finite differences), and the Adam optimiser (demonstrated on a toy problem).

### Stage 1 — Classical GCI model (`01_classical_gci_model.ipynb`)

**Goal:** the classical ground truth every quantum result is compared with.

**What happens:**
- Implements PD(z) (the Vasicek formula) for p₀ = 0.25, ρ = 0.027.
- Discretises z ∈ [−3, 3] into 4 bins (2 qubits) and 8 bins (3 qubits) and computes the **target Gaussian histogram** each register must reproduce: p*_b ∝ exp(−z_b²/2).
- Computes the classical loss distribution two ways: on the discrete grid ("Method A") and with 2 million continuous Monte Carlo draws ("Method B").

**Result:** P(L ≤ 0) ≈ 0.75, expected loss ≈ $250, 95 % VaR = $1000.

### Stage 2 — Quantum encoding (`02_quantum_encoding.ipynb`)

**Goal:** turn PD(z) into something a single qubit rotation can express.

**Idea:** a rotation R<sub>y</sub>(2φ) gives P(1) = sin²(φ). If φ depends *linearly* on z, one rotation angle per bin is enough:

$$
\mathrm{PD}(z) \approx \sin^2(\alpha z + \beta)
$$

α and β are found by fitting arcsin(√PD(z)) with a straight line. Because the register stores the integer index b rather than z, the parameters are rewritten per register size as α̃ (per index step) and β̃ (offset), so that the asset rotation is R<sub>y</sub>(2(α̃ b + β̃)).

**Result:** the sin² curve matches the Vasicek curve closely over the whole z range (validation plot `stage02_quantum_encoding_fit_validation.png`).

### Stage 3 — Circuit design (`03_circuit_design.ipynb`)

**Goal:** the full GCI circuit.

- **z-register** (n = 2 or 3 qubits): an R<sub>y</sub>(θᵢ) on each qubit, then CNOTs from qubit 0 to every other qubit (star entangler, as in the paper's Figs. 1–3). This shapes a bell curve over the 2ⁿ states.
- **Asset qubit:** R<sub>y</sub>(2β̃) sets the baseline, then one controlled-R<sub>y</sub>(2α̃·2ᵏ) per z-qubit k adds the z-dependent part. Because the controls are the binary digits of b, the total angle is exactly 2(α̃ b + β̃).
- Total qubits: n + 1 (3 or 4).

Measuring gives a bitstring whose **left bit is the default indicator** and whose **right n bits are the z index** — exactly the layout the paper describes.

### Stage 4 — Classical training (`04_classical_training.ipynb`)

**Goal:** find loader angles θ that reproduce the target Gaussian.

- Loss: L(θ) = Σ_b (p_b(θ) − p*_b)² (mean squared error between the circuit's histogram and the target).
- Gradients: parameter-shift rule, exact.
- Optimiser: Adam, 150 iterations.
- Compares the star entangler with other topologies.

**Result:** the 2-qubit loader reproduces the 4-bin Gaussian essentially exactly (trained angles ≈ 90° and 195°). The 3-qubit loader reaches the best its 3-parameter star ansatz allows — Hellinger fidelity ≈ 0.78 against the ideal 8-bin Gaussian. This is an **expressivity limit of the circuit design**, confirmed by an exhaustive grid search, not a training failure.

### Stage 5 — Transpilation (`05_transpilation.ipynb`)

**Goal:** make the circuit runnable on a realistic chip.

- Native gate set: `rz`, `sx`, `x`, `cz` (the paper's device uses CZ as its two-qubit gate).
- Mock linear coupling maps (each qubit connected only to its neighbours), one qubit larger than the circuit needs.
- SABRE layout and routing, optimisation level 1, fixed seed.

**Result:**

| Register | Depth before → after | CZ gates (decomposition only → with routing) |
|---|---|---|
| 2-qubit | 6 → 33 | 5 → 8 |
| 3-qubit | 8 → 56 | 8 → 14 |

The extra CZ gates are the price of limited connectivity. Transpilation optimises *structure* only — it knows nothing about how noisy each gate is, which is exactly why Stage 6 is needed.

### Stage 6 — Hardware retuning (`06_hardware_retuning.ipynb`) — **core novelty**

**Goal:** make the circuit produce the correct distribution on a noisy device.

**6.1 The noise-emulated device.** Qiskit AerSimulator plus:

| Error | Setting |
|---|---|
| Depolarizing gate noise | 0.2 % on `sx`, `x`; 1.5 % on `cz`; `rz` is virtual and error-free |
| Readout errors | per physical qubit, 2–7 % (≈ 5 % average; 1→0 larger than 0→1) |
| Coherent control drift | per physical qubit: θ_real = (1 + ε)θ + δ, ε up to ±14 %, δ up to ±15° |

The drift values are hidden: no calibration method reads them. Methods only see measured histograms — like an experimentalist in front of a real chip.

**6.2 The objective.** Every method minimises the **Hellinger distance** between the device's measured distribution (4 000 shots) and the noiseless reference distribution of the trained circuit:

$$
H(p, q) = \sqrt{1 - \sum_i \sqrt{p_i\,q_i}}, \qquad F_H = (1 - H^2)^2
$$

F_H (Hellinger fidelity) is the paper's own metric: 1 means identical distributions.

**6.3 Mitigation-aware calibration.** All methods tune against **readout-corrected** histograms. Otherwise the angles would partly absorb the readout error, and readout mitigation later would correct it a second time.

**6.4 Method 6A — the base paper's grid sweep.** Same ranges and steps as the paper:
- 2-qubit loader: θ₀ fixed, θ₁ swept 90°–450° in 21° steps, then 1° steps around the best.
- 3-qubit loader: θ₁ and θ₂ swept in 36° steps, then 7.5° / 14.5° steps.
- Full circuit: loader angles from the loader sweep, then a 2-D grid over the two asset angles (coarse 10° × 3°, fine 2° × 0.5°).

**6.5 Method 6B — automated calibration.**

- **Bayesian optimisation (BO).** Fits a Gaussian-process model to every (angles → distance) pair measured so far. The model predicts a mean and an uncertainty everywhere; the next point measured maximises the **Expected Improvement**, balancing "go where the model predicts low error" against "go where the model is unsure". Very sample-efficient in low dimensions.
- **SPSA** (Simultaneous Perturbation Stochastic Approximation). Estimates the full gradient from just **two** measurements per step, whatever the number of angles, by perturbing all angles at once in random ± directions. Robust to shot noise.

The 6B procedure is an automated version of the paper's own workflow:
1. BO on the loader angles, on the stand-alone loader circuit, on the same physical qubits (40 runs).
2. BO on the two asset angles, full circuit, loader angles frozen (30 runs).
3. SPSA refinement of all angles jointly (60 iterations) — captures interactions a block-wise search misses.
4. Verification: both candidates re-measured with more shots; the better one is kept.

**Ablations:** a single SPSA and a single BO on all angles at once, to show why the hierarchical design matters.

**Result (full GCI circuit):**

| Register | Method | Circuit runs | F_H |
|---|---|---|---|
| 2-qubit | uncalibrated | 0 | 0.923 |
| 2-qubit | 6A grid sweep | 347 | 0.939 |
| 2-qubit | **6B automated** | **204** | **0.982** |
| 2-qubit | ablation: joint SPSA | 308 | 0.982 |
| 2-qubit | ablation: joint BO | 70 | 0.973 |
| 3-qubit | uncalibrated | 0 | 0.910 |
| 3-qubit | 6A grid sweep | 477 | 0.957 |
| 3-qubit | **6B automated** | **204** | **0.994** |
| 3-qubit | ablation: joint SPSA | 308 | 0.947 |
| 3-qubit | ablation: joint BO | 70 | 0.964 |

**Paper cross-check:** the paper-style sweep moves the 2-qubit θ₁ from 195° to ≈ 234°; the paper measured 237° and 224° on its real qubit pairs.

**Why 6A falls short:** with θ₀ frozen, the drift on the first qubit can never be corrected, and grid resolution grows exponentially with the number of angles.

### Stage 7 — Execution on the noisy backend (`07_run_on_backend.ipynb`)

**Goal:** the actual experiment, with statistics.

- Each variant runs **20 independent times × 20 000 shots** → mean and standard deviation.
- **Readout-error mitigation (REM):** prepare every basis state, measure, build the assignment matrix A (A_is = P(read i | prepared s)); recover the true distribution from the measured one with non-negative least squares.
- **Zero-noise extrapolation (ZNE):** fold the circuit (U → U U† U …) to multiply the gate noise by λ = 1, 3, 5; fit each probability linearly in λ and extrapolate to λ = 0.

**Result (Hellinger fidelity vs noiseless reference, mean ± std):**

| Variant | 2-qubit | 3-qubit |
|---|---|---|
| uncalibrated, raw | 0.879 ± 0.003 | 0.919 ± 0.002 |
| uncalibrated + REM | 0.922 ± 0.003 | 0.909 ± 0.003 |
| 6A + REM | 0.939 ± 0.002 | 0.956 ± 0.002 |
| **6B + REM (deployed)** | **0.982 ± 0.002** | **0.995 ± 0.001** |
| 6B + REM + ZNE | 0.998 ± 0.001 | 0.996 ± 0.001 |

**Readings:** readout mitigation alone cannot fix drift (it even lowers the 3-qubit fidelity, because drift and readout bias happened to partly cancel). Retuning is what moves the needle; ZNE adds a little more fidelity but costs up to 9× the gate-time.

### Stage 8 — Classical post-processing (`08_classical_postprocessing.ipynb`)

**Goal:** turn bitstrings into money, exactly as in the paper.

For every outcome with probability p:
- right n bits → z index b → P(Z = z_b) accumulates;
- left bit = 1 → default → loss = LGD = $1000;
- equal losses merged into a PDF, cumulated into a CDF;
- expected loss = Σ loss × probability; VaR read from the CDF.

It also recovers **P(default | z)** for every economy bin directly from the counts and compares it with the Vasicek curve — a check that the *financial model*, not just a histogram, survives the hardware.

**Result:**

| Variant | P(L ≤ 0) 2q / 3q | Expected loss 2q / 3q | VaR |
|---|---|---|---|
| noiseless | 0.748 / 0.746 | $252.5 / $254.4 | $1000 |
| uncalibrated | 0.826 / 0.809 | $174.1 / $190.7 | $1000 |
| 6A + REM | 0.755 / 0.738 | $244.7 / $262.5 | $1000 |
| 6B + REM | 0.727 / 0.739 | $272.9 / $261.3 | $1000 |
| classical grid | 0.750 / 0.750 | $250.4 / $250.0 | $1000 |

The uncalibrated circuit underestimates the default probability by roughly a quarter to a third (the drift under-rotates the asset qubit). After calibration, expected loss returns to within roughly ±10 % of the reference.

### Stage 9 — VaR & fidelity check (`09_var_fidelity_check.ipynb`)

**Goal:** the acceptance decision of the architecture diagram.

Four fidelities per variant:
1. vs the noiseless circuit — hardware error only (**used for ACCEPT**);
2. vs the classical GCI joint distribution — hardware + modelling error;
3. of the loss distribution vs classical;
4. of the z-marginal vs the target Gaussian.

**Decision:** the deployed pipeline (6B + REM) is accepted if F_H ≥ 0.97 → **ACCEPT** for both registers (0.982, 0.995).

**Drift event.** The chip is given a completely new miscalibration ("the next day"). Yesterday's angles now give F_H = **0.528** (2-qubit) and **0.676** (3-qubit) → **RE-CALIBRATE** → 6B re-runs automatically (204 circuit runs) → **0.972** and **0.992** → **ACCEPT**. A manual 6A re-sweep would cost 347 / 477 runs.

**Why VaR alone is a weak test:** with one asset the loss is $0 or $1000 and P(L = 0) ≈ 0.75 < 0.95, so *any* distribution with a default probability above 5 % gives VaR = $1000 — even the uncalibrated circuit. The paper makes the same point: the real result is reproducing the *distribution* the VaR is computed from.

---

## 8. Results

### 8.1 Summary

| Claim | Evidence |
|---|---|
| Replication is faithful | P(L ≤ 0) ≈ 0.75, P(L ≤ 1000) = 1, VaR = $1000; 6A sweep reproduces the paper's angle shift (195° → 234°; paper 224°–237°) |
| Automated calibration beats manual grid | F_H 0.982 / 0.994 vs 0.939 / 0.957, with 204 vs 347 / 477 circuit runs |
| Hierarchical design matters | joint SPSA fails for 5 angles (0.947); joint BO plateaus (0.964); 6B reaches 0.994 |
| Each correction fixes a different error | REM alone < retuning; retuning + REM ≈ 0.98–0.995; ZNE adds up to +0.016 |
| The loop self-heals | drift event 0.53 → 0.97 and 0.68 → 0.99 without human input |
| Runs on a laptop | full pipeline ≈ 1–2 minutes on a CPU |

### 8.2 Comparison with the base paper

| | Base paper | This project |
|---|---|---|
| Platform | Real Contralto-D superconducting chip | Qiskit AerSimulator + emulated noise |
| Circuit | 1 asset, 1 risk factor, 2-qubit z-register | same, plus a 3-qubit z-register |
| Angle tuning | Manual grid sweep | Automated BO + SPSA (grid sweep also reproduced) |
| Error mitigation | none | readout mitigation, ZNE |
| Final fidelity | 98.9 ± 0.3 % | 98.2 % (2-qubit), 99.5 % (3-qubit) |
| CDF / VaR | P(L ≤ 0) ≈ 0.75, VaR $1000 | P(L ≤ 0) ≈ 0.73–0.74, VaR $1000 |

### 8.3 Figures to use

All in `results/figures/`:

| Figure | Shows |
|---|---|
| `stage01_gci_pd_curve.png` | the Vasicek default curve |
| `stage02_quantum_encoding_fit_validation.png` | sin² encoding vs Vasicek |
| `stage03_circuit_2q_register.png` | the full circuit |
| `stage04_training_convergence.png` | Adam training loss |
| `stage05_transpilation_cost_breakdown.png` | cost of limited connectivity |
| `stage06_problem_uncalibrated.png` | noise breaks the trained circuit |
| `stage06_theta1_sweep_2q.png` | paper-style angle sweep (paper Fig. 5) |
| `stage06_convergence_gci.png` | **6A vs 6B: cost vs quality — the key novelty figure** |
| `stage06_cost_vs_quality.png` | all methods in one scatter |
| `stage07_fidelity_by_variant.png` | what each correction contributes |
| `stage07_zne_extrapolation.png` | how ZNE works |
| `stage08_conditional_pd.png` | P(default | z) recovered from counts vs Vasicek |
| `stage08_loss_cdf.png` | loss CDF (paper Fig. 10) |
| `stage09_recalibration_loop.png` | ACCEPT / RE-CALIBRATE after a drift event |

---

## 9. Discussion — what the results mean

1. **Offline training is not enough on NISQ hardware.** The same trained angles lose 8–12 fidelity points on the noisy device. This reproduces the paper's central finding.
2. **Calibration is an optimisation problem, and it should be treated as one.** A grid sweep spends most of its runs in useless regions and cannot tune many angles at once. BO learns where to look; SPSA refines cheaply. Together they beat the grid on both axes: fewer runs *and* higher fidelity.
3. **Different errors need different tools.** Coherent drift is fixed in the angles; readout bias in post-processing; depolarizing noise partly by ZNE. Applying one tool to the wrong error does not help — readout mitigation on an uncalibrated circuit barely improves it.
4. **The metric matters.** Hellinger fidelity over the whole distribution is what the paper and we optimise. A single number such as expected loss can move differently: for the 2-qubit register, 6A lands slightly closer on expected loss than 6B despite a much lower fidelity. For a bank, a calibration objective that also weights the loss distribution would be the natural next step.
5. **Automation makes calibration repeatable.** Real chips drift daily. A loop that detects the drift and fixes itself in ~200 runs turns a lab procedure into a pipeline.

---

## 10. Limitations

- **Simulator, not hardware.** Crosstalk, leakage, non-Markovian and time-varying noise are not modelled.
- **Drift is emulated on the commanded angles**, using the initial qubit layout; rotations after routing SWAPs are approximated.
- **Toy portfolio.** One asset and one risk factor; VaR is trivially $1000. The fidelity carries the real information.
- **3-qubit loader expressivity.** The 3-angle star ansatz cannot represent the 8-bin Gaussian exactly (F_H ≈ 0.78 even without noise). This caps fidelity against the classical model and is inherited from Stage 4.
- **The calibration objective is distribution-level.** It does not directly weight expected loss.

---

## 11. Future work

1. **Real IBM Quantum hardware** — the calibration loop only needs counts, so it can run unchanged against a real backend.
2. **Scaling to 2 assets / 2 risk factors (6 qubits)** — the case the paper only projects.
3. **Task-aware calibration objective** — add the loss-distribution distance so expected loss is matched as well as the full distribution.
4. **Richer loader ansatz** — a second rotation layer to lift the 3-qubit expressivity ceiling.
5. **Full Quantum Amplitude Estimation** on top of the calibrated loader, to estimate VaR with the quadratic speed-up rather than direct sampling.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **Ansatz** | The fixed structure of a variational circuit whose angles are trained |
| **Assignment matrix** | Matrix of readout probabilities P(read i \| prepared s) used for readout mitigation |
| **Bayesian optimisation** | Optimiser that models the objective with a Gaussian process and chooses the most informative next point |
| **CDF** | Cumulative distribution function, P(X ≤ x) |
| **Coupling map** | Which physical qubits can interact directly |
| **Depolarizing noise** | Noise that pushes a quantum state toward a random one |
| **Drift / control error** | Systematic over- or under-rotation of gates due to pulse miscalibration |
| **Expected Improvement** | BO acquisition function balancing exploitation and exploration |
| **GCI model** | Gaussian Conditional-Independence model: defaults independent given a normal latent factor |
| **Hellinger fidelity** | Similarity of two distributions, 1 = identical |
| **LGD** | Loss given default |
| **NISQ** | Noisy Intermediate-Scale Quantum — today's hardware generation |
| **Parameter-shift rule** | Exact gradient of a quantum circuit from two shifted evaluations |
| **PD** | Probability of default |
| **QAE** | Quantum Amplitude Estimation — quadratic speed-up over Monte Carlo |
| **Readout error mitigation** | Correcting measured distributions for misread bits |
| **SABRE** | SWAP-based heuristic for qubit placement and routing |
| **Shot** | One execution and measurement of a circuit |
| **SPSA** | Gradient-free optimiser using two evaluations per step |
| **Transpilation** | Rewriting a circuit for a specific device's gates and connectivity |
| **VaR** | Value at Risk: loss not exceeded at a given confidence |
| **Vasicek model** | One-factor credit model giving PD(z) |
| **ZNE** | Zero-noise extrapolation: amplify noise, extrapolate back to zero |

---

## 13. Likely review questions — with answers

**Q1. Why use a quantum computer at all for credit risk?**
Monte Carlo error falls as 1/√N; Quantum Amplitude Estimation falls as 1/N — a quadratic speed-up. Loading the uncertainty model, which this project does, is the first building block of that algorithm.

**Q2. Why is the default probability encoded as sin²(αz + β)?**
A rotation R<sub>y</sub>(2φ) gives P(1) = sin²φ. Making φ linear in z means the asset angle is a sum of fixed pieces controlled by the bits of z — implementable with one R<sub>y</sub> and one controlled-R<sub>y</sub> per z-qubit.

**Q3. Why the parameter-shift rule instead of backpropagation?**
A quantum device cannot be differentiated like a neural network. The shift rule gives the *exact* gradient from two extra circuit runs per angle.

**Q4. Why do the trained angles fail on hardware?**
Pulses are miscalibrated (coherent drift), readout misreads bits, and gates add noise. The simulator used for training has none of these.

**Q5. What exactly is your novelty?**
Replacing the paper's manual grid sweep with automated, mitigation-aware calibration (BO → BO → SPSA), benchmarking readout mitigation and ZNE, and closing the loop so drift is detected and repaired automatically.

**Q6. Why not just use SPSA or BO alone?**
The ablations show it: joint SPSA on five angles from a poor start converges poorly (0.947 for the 3-qubit register); joint BO plateaus (0.964). BO first places the angles globally, SPSA then refines them locally — 0.994.

**Q7. How do you know the calibration isn't cheating by seeing the noise model?**
The drift values are never passed to any method. The optimisers only receive measured histograms, exactly as on a real chip.

**Q8. Why is VaR $1000 for every variant — even the bad one?**
With one asset the loss is $0 or $1000 and P(L = 0) ≈ 0.75 < 0.95, so the 95 % point is always $1000. That is why the paper and we judge the full distribution with Hellinger fidelity.

**Q9. Why 20 000 shots and 20 repetitions?**
Shot noise on a probability near 0.25 is about ±0.3 % at 20 000 shots — small enough to resolve the ZNE gains (≈ 0.001–0.016). Twenty repetitions give error bars. The calibration loops use 4 000 shots per run because they need many runs rather than high precision.

**Q10. Why is the 3-qubit fidelity against the classical model only ≈ 0.8?**
The 3-parameter star ansatz cannot represent an 8-bin Gaussian exactly — even noiselessly it reaches ≈ 0.78. That is a circuit-design limit, not noise; a richer ansatz is listed as future work.

**Q11. Does this run on real hardware?**
No — on a simulator with an emulated noise model. The calibration loop only needs counts, so it could run unchanged on IBM Quantum hardware; that is the first future-work item.

**Q12. How does this compare with the paper's 98.9 %?**
We reach 98.2 % (2-qubit) and 99.5 % (3-qubit) after automated calibration and readout mitigation, on an emulated device. The numbers are comparable in size, but one is hardware and the other simulation.

---

## 14. Suggested presentation structure

| Slide | Content | Source in this document |
|---|---|---|
| 1 | Title, team, course | header |
| 2 | Motivation: credit risk, VaR, Monte Carlo cost, quantum speed-up, NISQ reality | §1, §2 |
| 3 | Base paper: what it did, what it found | §4.1–4.2 |
| 4 | Gaps and our novelty | §4.3, §5 |
| 5 | Literature survey | Review-1 slides |
| 6 | Architecture diagram | §6, `images/architecture_flowchart.png` |
| 7 | Stages 1–3: model → encoding → circuit | §7 stages 1–3, figures stage01–03 |
| 8 | Stage 4: training | §7 stage 4, `stage04_training_convergence.png` |
| 9 | Stage 5: transpilation | §7 stage 5 table |
| 10 | Stage 6: the noise problem | `stage06_problem_uncalibrated.png` |
| 11 | Stage 6: 6A vs 6B | §7 stage 6 table, `stage06_convergence_gci.png` |
| 12 | Stage 7: mitigation benchmark | `stage07_fidelity_by_variant.png` |
| 13 | Stage 8: loss CDF and P(default \| z) | `stage08_loss_cdf.png`, `stage08_conditional_pd.png` |
| 14 | Stage 9: acceptance and drift recovery | `stage09_recalibration_loop.png` |
| 15 | Results vs base paper | §8.2 |
| 16 | Limitations and future work | §10, §11 |
| 17 | Thank you / questions | — |
