# Project Study Guide — From Zero

**Quantum Circuit-Based Adaptation for Credit Risk Analysis**
Base paper: Ahmad et al., *IEEE Transactions on Quantum Engineering*, vol. 7, 3103316, 2026

This guide assumes you know nothing about credit risk or quantum computing. It explains:

- **every word** the project uses (bin, register, amplitude, shot, transpile, …) the first time it appears;
- **every equation** in the same five steps: *why it exists → what each symbol means → a worked example with the project's real numbers → what we do with its output next → where it is in the code*;
- **every design choice** (why 2 or 3 qubits, why ±3, why 4 000 shots, why 0.97, …) with the reason behind it.

Read Parts 1–3 in order once. Part 4 answers "why did you choose X?" questions. Part 5 is a quick lookup table of terms.

---

## Contents

- [Part 1 — The background you need](#part-1--the-background-you-need)
  - [1.1 The bank's problem](#11-the-banks-problem)
  - [1.2 Probability words](#12-probability-words)
  - [1.3 The normal distribution and why everything uses it](#13-the-normal-distribution)
  - [1.4 Quantum computing words](#14-quantum-computing-words)
  - [1.5 Training words](#15-training-words)
  - [1.6 Why real quantum chips go wrong](#16-why-real-quantum-chips-go-wrong)
- [Part 2 — The big picture in one page](#part-2--the-big-picture-in-one-page)
- [Part 3 — Every equation, step by step](#part-3--every-equation-step-by-step)
- [Part 4 — Why we chose what we chose](#part-4--why-we-chose-what-we-chose)
- [Part 5 — Word list](#part-5--word-list)

---

## Part 1 — The background you need

### 1.1 The bank's problem

**Loan.** A bank lends money to a **borrower** (a person or a company), here **$1000**.

**Default.** The borrower fails to pay the loan back. Then the bank loses money.

**Loss given default (LGD).** How much the bank loses *if* the borrower defaults. Here **$1000** — the whole loan. (Real banks often recover part of it; the paper keeps it simple.)

**Probability of default (PD).** The chance the borrower defaults within a year. Our borrower: **25 %**.

**Expected loss.** The *average* loss: PD × LGD = 0.25 × $1000 = **$250**. If the bank made this same loan to thousands of similar borrowers, it would lose about $250 per loan on average.

**The catch: defaults happen together.** In a recession, many borrowers default at the same time. So a bank cannot just look at averages; it must know how bad things can get in a bad year. That is why the default probability must depend on **the state of the economy**.

**Value at Risk (VaR).** The number regulators require. "95 % VaR = $X" means: *in 95 % of possible years, the bank loses at most $X*. It is a worst-case-but-not-the-very-worst number.

**Why this is hard to compute.** Normally a bank uses **Monte Carlo simulation**: it invents millions of random possible years on a computer, checks the loss in each, and sorts them. That works, but it is slow: to make the answer twice as accurate you need **four times** as many simulated years. (Error shrinks like 1/√N, where N is the number of simulated years.)

**Why quantum computing.** A quantum algorithm called **Quantum Amplitude Estimation (QAE)** can reach the same accuracy with far fewer steps: twice as accurate needs only twice as many steps (error shrinks like 1/N). This is called a **quadratic speed-up**. But QAE first needs a quantum circuit that *contains* the credit-risk model. Building that circuit — and making it work on noisy hardware — is what the base paper and this project do. (This project does not run QAE itself; it builds and fixes the part QAE needs first.)

### 1.2 Probability words

**Probability.** A number from 0 (never) to 1 (always). 0.25 = 25 %.

**Distribution.** A list of all possible outcomes and how likely each is. Example: the loss is $0 with probability 0.75 and $1000 with probability 0.25. The probabilities always add up to 1.

**Histogram.** A distribution drawn as bars — one bar per outcome, bar height = probability.

**Bin.** One bar of a histogram — a "bucket" that collects everything in a range. If you sort the economy into 4 buckets — "very bad", "bad", "good", "very good" — each bucket is a bin. The project uses bins because a quantum circuit can only produce a fixed, small number of outcomes (see 1.4), so a smooth curve must be chopped into a few buckets.

**PDF (probability distribution / density).** The list of outcome → probability. Here: loss $0 → 0.75, loss $1000 → 0.25.

**CDF (cumulative distribution function).** The *running total* of the PDF: "what is the chance the loss is **at most** L?"
- P(loss ≤ $0) = 0.75
- P(loss ≤ $1000) = 0.75 + 0.25 = 1.00

VaR is read from the CDF: it is the first loss where the running total reaches 95 %.

**Conditional probability, P(A | B).** "The chance of A, *given that* B happened." P(default | recession) = the chance of default if we already know there is a recession. The bar "|" is read "given".

### 1.3 The normal distribution

**What it is.** The famous bell curve. Most values are near the middle, fewer and fewer further out. Heights of people, measurement errors and — in finance models — "how good or bad the economy is" are all modelled this way.

**Mean and standard deviation.** The **mean** is the centre (here 0). The **standard deviation (σ)** measures how spread out it is (here 1). A **standard normal** distribution has mean 0 and σ = 1, written **N(0, 1)**.

**What "z" means.** z is a value from N(0, 1) and it measures **how many standard deviations from average** something is. In this project z is **the state of the economy**:

| z | Meaning | How often |
|---|---|---|
| −3 | deep recession | very rare |
| −1 | mild downturn | common |
| 0 | average economy | most common |
| +1 | mild boom | common |
| +3 | strong boom | very rare |

How much of the bell curve lies within a range:

| Range | Share of all outcomes |
|---|---|
| −1 to +1 | 68.3 % |
| −2 to +2 | 95.4 % |
| −3 to +3 | **99.7 %** |

That last row is why the project's economy axis runs from −3 to +3: it covers almost every possible economy (see Part 4, Q1).

**Φ (capital phi) — the standard normal CDF.** Φ(x) = the chance a standard normal value is **below** x. It turns a "number of standard deviations" into a probability.
- Φ(0) = 0.5 (half the bell curve is below the middle)
- Φ(−0.674) ≈ 0.25
- Φ(−1.645) ≈ 0.05

**Φ⁻¹ — the inverse.** Goes the other way: probability → number of standard deviations. Φ⁻¹(0.25) = −0.674 means "the bottom 25 % of the bell curve is everything below −0.674".

### 1.4 Quantum computing words

**Bit.** An ordinary computer bit is 0 or 1.

**Qubit.** A quantum bit. Before you look at it, it can be in a **superposition** — partly 0 and partly 1 at the same time, with a certain "weight" on each.

**Measurement.** Looking at a qubit. It always gives a plain 0 or 1 — never something in between. Which one you get is random, and the weights decide the odds.

**Amplitude.** The weight on each outcome. The rule (called the **Born rule**) is:

> probability of an outcome = (its amplitude)²

Example: a qubit with amplitude 0.6 on |0⟩ and 0.8 on |1⟩ gives 0 with probability 0.36 and 1 with probability 0.64.

**|0⟩ and |1⟩.** Just the notation physicists use for "the outcome 0" and "the outcome 1". The brackets are called "kets"; read |1⟩ as "state one".

**Shot.** One run of the circuit followed by a measurement. Because each measurement gives a single random outcome, you run the circuit many times (thousands of shots) and **count** how often each outcome appears. Those counts give the probabilities. More shots → more accurate counts.

**Register.** A group of qubits used together to store one number. 2 qubits can show 4 outcomes (00, 01, 10, 11), so a 2-qubit register can store a number from 0 to 3. A 3-qubit register: 8 outcomes, numbers 0 to 7. In general **n qubits → 2ⁿ outcomes**.

**Bitstring.** The row of 0s and 1s you read when you measure several qubits, e.g. `101`.

**Basis state.** One specific outcome of a register, like |01⟩. Each basis state ↔ one bin.

**Gate.** An operation on qubits — the quantum version of a logic gate. A circuit is a sequence of gates.

**Ry(θ) — rotation gate.** Turns a qubit by an angle θ. Starting from |0⟩:

> after Ry(θ): P(measure 1) = sin²(θ/2)

So **the angle sets the probability**. Ry(0°) → never 1. Ry(90°) → 1 half the time. Ry(180°) → always 1. This is the key trick of the whole project: *to make something happen with probability p, rotate a qubit by the right angle.*

**CNOT (controlled-NOT).** A two-qubit gate: "if qubit A is 1, flip qubit B". It makes the qubits' results **depend on each other** (this is called **entanglement**). Without it, each qubit would behave independently and you could not make a bell-shaped curve over the register.

**Controlled rotation, CRy(θ).** "If the control qubit is 1, rotate the target qubit by θ". It lets one qubit's outcome change another qubit's probability — exactly what we need to make "default" depend on "economy".

**Circuit.** The whole recipe: which gates, on which qubits, in which order.

**Depth.** How many layers of gates the circuit has. Deeper = more time on the chip = more noise.

**Simulator.** Ordinary software that computes what a quantum circuit would do. **Statevector simulation** computes the exact amplitudes (perfect, no noise). **Shot-based simulation** imitates measuring, with randomness, and can add noise. This project uses Qiskit's simulator (Qiskit Aer) — no real quantum chip.

**Qiskit.** IBM's free Python library for building and simulating quantum circuits. Everything in this project is written with it.

### 1.5 Training words

**Parameter / angle / knob.** A number you can change in the circuit — here, rotation angles θ. I call them "knobs".

**Loss function.** One number that says how wrong the current output is. Training = making it small. (Careful: "loss" here means *error*, not money. The bank's money loss is a different thing.)

**Gradient.** For each knob, which direction to turn it — and how strongly — to make the loss smaller. It is the "slope" of the loss.

**Optimiser.** The procedure that repeatedly turns the knobs using the gradient (or other information) until the loss is small.

**Iteration.** One round of "measure → compute direction → turn knobs".

### 1.6 Why real quantum chips go wrong

Today's quantum chips are called **NISQ** — *Noisy Intermediate-Scale Quantum*: they have tens to hundreds of qubits, but every operation is imperfect. Three error types matter here (the base paper names all three in Section V):

1. **Gate noise (depolarizing noise).** Every gate slightly scrambles the state, pushing it towards pure randomness. Two-qubit gates (like CNOT) are much worse than one-qubit gates.
2. **Readout error.** When you measure, the chip sometimes reports the wrong value — a 1 read as 0, or a 0 read as 1.
3. **Control drift / miscalibration.** A rotation is made by a microwave pulse. If the pulse is slightly too strong or too weak, the qubit is turned by the wrong angle — you ask for 90° and get 101°. Every qubit is off by a different amount, and it changes over time (the chip "drifts").

**Why it matters.** A circuit whose angles were trained on a perfect simulator gives the **wrong distribution** on a real chip, because of these errors. Fixing that is this project's main contribution.

**Physical vs logical qubit.** A **logical** qubit is a qubit in your circuit design ("qubit 0"). A **physical** qubit is an actual piece of hardware on the chip ("Q2"). The software decides which physical qubit plays which logical role.

**Coupling map / connectivity.** Which physical qubits are wired to each other. On real chips, a two-qubit gate only works between **neighbours**.

**Native gates.** The few operations a chip can do directly. Everything else must be rebuilt from them. Our emulated chip (like the paper's) uses `rz`, `sx`, `x` and `cz`.

**Transpilation.** Rewriting a circuit so a specific chip can run it: only native gates, only neighbour-to-neighbour two-qubit gates. Like translating a sentence into a language with a smaller vocabulary.

---

## Part 2 — The big picture in one page

### The idea

Build a small quantum circuit that behaves like **loaded dice**:

- **Economy dice — the z-register (2 or 3 qubits).** Measuring them gives an **economy bin**: very bad … very good, with the middle bins most likely (a bell curve).
- **Default coin — the asset qubit (1 qubit).** Its chance of showing "1" (default) depends on which economy bin came up: worse economy → more likely to default.

Each **shot** = one possible year for the bank. 20 000 shots = 20 000 simulated years, from which we read the loss distribution and VaR — just like Monte Carlo, but produced by a quantum circuit.

### The steps, and which equation does what

| Step | What happens | Equations |
|---|---|---|
| 1 | Write down how default depends on the economy | Eq. 1 |
| 2 | Chop the economy's bell curve into bins | Eq. 10 |
| 3 | Turn the default formula into rotation angles for the coin | Eq. 2, 3, 4 |
| 4 | Decide the number of qubits and what the dice must produce | Eq. 5, 6 |
| 5 | Build the dice circuit and train its knobs | Eq. 12, 13, 8, 9, 11, parameter shift, Adam |
| 6 | Join dice + coin; rewrite for the chip | full circuit, SABRE |
| 7 | Run on a noisy chip — it goes wrong | noise model |
| 8 | Measure how wrong; fix the knobs automatically | Hellinger, 6A vs 6B (BO, SPSA) |
| 9 | Run many times; clean up measurement errors | readout mitigation, ZNE |
| 10 | Turn bitstrings into money; compute VaR | post-processing, VaR |
| 11 | Check it is trustworthy; recalibrate if not | fidelity gate |

### The worked example used everywhere

The base paper's borrower (Section IV-C): **p₀ = 0.25, ρ = 0.027, LGD = $1000**, with a **2-qubit** economy register (4 bins). All numbers below are what the project's code actually computes.

---

## Part 3 — Every equation, step by step

Each equation follows the same five headings:
**Why it exists · The equation and its symbols · Worked example · What we do with the output · Code**

---

### Step 1 — Eq. 1: how default depends on the economy (the Vasicek / GCI model)

**Why it exists.** We need a rule that says *how likely the borrower is to default in each state of the economy*. Without it, there is nothing for the quantum circuit to reproduce.

The idea behind it (the **Vasicek model**, the basis of the Basel banking rules):
- The borrower's financial health is affected by two things: the **economy** (shared by everyone) and **its own luck** (unique to it).
- The borrower defaults if its health falls below a **threshold**.
- Given the economy, borrowers default independently of each other — hence the name **Gaussian Conditional Independence (GCI)**: "Gaussian" because everything is normally distributed, "conditional independence" because borrowers are independent *once you know the economy*.

**The equation (paper Eq. 1)**

$$
\mathrm{PD}(z) = \Phi\!\left(\frac{\Phi^{-1}(p_0) - \sqrt{\rho}\,z}{\sqrt{1-\rho}}\right)
$$

| Symbol | Meaning | Value |
|---|---|---|
| PD(z) | chance of default **given** the economy is at z — a conditional probability, P(default \| z) | output |
| z | state of the economy, in standard deviations from average | any number; we use −3 … +3 |
| p₀ | the borrower's **average** default probability | 0.25 (from the paper) |
| ρ (rho) | **correlation**: how strongly the borrower depends on the economy. 0 = not at all; 1 = completely | 0.027 (from the paper) |
| Φ⁻¹(p₀) | the default **threshold**, in standard deviations | Φ⁻¹(0.25) = −0.674 |
| √ρ · z | how much the economy pushes the borrower's health up or down | |
| √(1−ρ) | rescales by the borrower's own-luck part | √0.973 = 0.986 |
| Φ( … ) | turns the result back into a probability | |

Reading it in words: *"start from the borrower's normal default threshold; a bad economy (negative z) moves it closer to default; convert that to a probability."*

**Worked example**
- Average economy, z = 0: PD = Φ(−0.674 / 0.986) = Φ(−0.684) = **0.247** — close to the average 0.25, as it should be.
- Deep recession, z = −3: PD = **0.427** (43 %).
- Strong boom, z = +3: PD = **0.118** (12 %).

So the same borrower is almost four times as likely to default in a deep recession as in a strong boom.

**Where p₀ and ρ come from.** Both are taken directly from the base paper (Section IV-C). They are demonstration values, not a real customer's data. In a real bank, p₀ comes from the borrower's credit rating and ρ from the Basel formula — both originally estimated from historical default records. That is why the project needs **no dataset**: the data work is already summarised in these two numbers.

**What we do with the output next.**
1. Step 3 (Eq. 2) turns this curve into rotation angles for the default coin.
2. Step 10 uses it again as the **classical correct answer** that the quantum result is compared against.

**Code.** `src/gci_model.py → pd_given_z(z, p0, rho)`

---

### Step 2 — Eq. 10: chop the economy into bins

**Why it exists.** The economy z is a smooth bell curve with infinitely many possible values. A quantum register has only a few outcomes (2 qubits → 4). So we must chop the curve into a few **bins** and give each bin a probability. This list of probabilities is the **target** — what the economy dice must produce.

**The equation (paper Eq. 10)**

$$
z(b) = -z_{\max} + \frac{2 z_{\max}}{2^n - 1}\, b, \qquad
p^\star_b \propto \exp\!\left(-\frac{z(b)^2}{2}\right)
$$

| Symbol | Meaning | Value |
|---|---|---|
| n | number of qubits in the economy register | 2 (or 3) |
| 2ⁿ | number of bins | 4 (or 8) |
| b | bin number — the number stored in the register | 0, 1, 2, 3 |
| z_max | edge of the economy axis | 3 (**this project's choice** — the paper leaves it as a parameter; see Part 4, Q1) |
| z(b) | the economy value that bin b stands for | −3, −1, +1, +3 |
| exp(−z²/2) | the shape of the bell curve at z | |
| ∝ | "proportional to" — compute the heights, then divide by their total so they add up to 1 | |
| p\*_b | target probability of bin b | output |

The first formula spaces the bins **evenly** from −3 to +3. The second gives each bin the height of the bell curve at that point.

**Worked example (2 qubits)**

| Bin b | Bits | z(b) | Target p\*_b | Meaning |
|---|---|---|---|---|
| 0 | 00 | −3 | 0.009 | deep recession — rare |
| 1 | 01 | −1 | 0.491 | mild downturn — common |
| 2 | 10 | +1 | 0.491 | mild boom — common |
| 3 | 11 | +3 | 0.009 | strong boom — rare |

With 3 qubits there are 8 bins at z = −3, −2.14, −1.29, −0.43, +0.43, +1.29, +2.14, +3 with targets 0.004, 0.034, 0.150, 0.312, 0.312, 0.150, 0.034, 0.004 — a smoother bell curve.

**What we do with the output next.** The target p\* is held until Step 5 (Eq. 11), where the circuit is trained to reproduce it. It is also used in Step 10 as part of the classical answer.

**Code.** `src/gci_model.py → discretize_z`, `target_gaussian_histogram`

---

### Step 3a — Eq. 2: rewrite the default curve in a form a qubit can produce

**Why it exists.** A quantum gate cannot compute Φ. But a rotation gate naturally produces probabilities of the form **sin²** (see 1.4: Ry(θ) gives P(1) = sin²(θ/2)). So if we can write the default curve as a sin², one rotation can produce it.

**The equation (paper Eq. 2)**

$$
\mathrm{PD}(z) \equiv P_1 = \sin^2(\alpha z + \beta)
$$

| Symbol | Meaning | Value |
|---|---|---|
| P₁ | probability of measuring 1 on the default qubit — "1" means "defaulted" | |
| ≡ | "we define these to be the same thing" | |
| α (alpha) | slope — how fast the angle changes with the economy | −3.47° |
| β (beta) | offset — the angle at z = 0 | 30.03° |

**How α and β are found.** Undo the sin²: the exact angle that would give PD(z) is arcsin(√PD(z)). Compute that for 400 values of z between −3 and +3, then draw the **best straight line** through them (a least-squares fit). Slope = α, intercept = β.

Why a straight line: in Step 3c a straight line in z lets the whole curve be built from very few simple gates.

**Worked example.** α = −3.47°, β = 30.03°. The largest error of sin²(αz + β) against the true PD(z) anywhere on [−3, 3] is **0.0065** (0.65 percentage points); the average error is 0.0025. Much smaller than the chip's noise, so the straight line is good enough.

The negative slope makes sense: as the economy improves (z up), the angle goes down, so the default probability goes down.

**Note.** The paper computes α and β with a formula in its Supplementary Material (Eqs. 5–6). This project uses the least-squares fit — the same idea, simpler to reproduce. It is listed as a modification in the slides.

**What we do with the output next.** α and β go into Eq. 3.

**Code.** `src/quantum_encoding.py → fit_linear_angle`

---

### Step 3b — Eq. 3: the rotation that encodes default

**Why it exists.** It turns Eq. 2 into an actual gate.

**The equation (paper Eq. 3)**

$$
R_y\big(2(\alpha z + \beta)\big)
$$

**Why the "2".** Ry(θ) gives P(1) = sin²(θ/2) — the gate halves its angle. To get sin²(αz + β) we must feed it **twice** that angle: θ = 2(αz + β), so θ/2 = αz + β.

**Worked example.** At z = −3: angle = 2 × (−3.47° × −3 + 30.03°) = 2 × 40.4° = 80.8°. P(1) = sin²(40.4°) = **0.420** — close to the true 0.427.

**What we do with the output next.** The circuit doesn't store z directly — it stores the bin number b. So Eq. 4 rewrites this angle in terms of b.

**Code.** used inside Eq. 4's gates.

---

### Step 3c — Eq. 4: build the coin's gates from the bin number

**Why it exists.** The economy register stores the **bin number b** (0, 1, 2, 3), written in binary across its qubits. We need the coin's rotation angle to depend on b, built from gates that read the register's qubits one by one.

**The equation (paper Eq. 4)**

$$
R_y\big(2(\tilde\alpha\, b + \tilde\beta)\big), \qquad \tilde\alpha = \alpha\cdot\Delta z, \qquad \tilde\beta = \beta - \alpha\, z_{\max}
$$

| Symbol | Meaning | Value (2 qubits) |
|---|---|---|
| b | bin number stored in the register | 0–3 |
| Δz | spacing between bins = 2 z_max / (2ⁿ − 1) | 6/3 = 2 |
| α̃ ("alpha tilde") | slope per bin instead of per unit of z | −6.93° |
| β̃ ("beta tilde") | angle for bin 0 instead of for z = 0 | 40.42° |

This is just Eq. 3 with z replaced by z(b) from Eq. 10, then tidied up: αz(b) + β = α̃b + β̃.

**The binary trick — why only a few gates are needed.** The register stores b in binary: b = q₀ + 2·q₁ (+ 4·q₂ for 3 qubits), where each qᵢ is 0 or 1. So

> α̃·b + β̃ = β̃ + α̃·q₀ + 2α̃·q₁

and the rotation splits into simple pieces:
- one plain rotation **Ry(2β̃)** — always applied;
- one **controlled rotation CRy(2α̃·2ᵏ)** for each economy qubit k — applied only if that qubit is 1.

So the coin needs just **n + 1 gates**, however many bins there are.

**Worked example (2 qubits).** The gates are Ry(80.8°), CRy(−13.9°) controlled by qubit 0, CRy(−27.7°) controlled by qubit 1. Resulting default probability per bin:

| Bin b | Angle α̃b + β̃ | P(default) from the coin | True PD from Eq. 1 |
|---|---|---|---|
| 0 (z = −3) | 40.42° | 0.420 | 0.427 |
| 1 (z = −1) | 33.49° | 0.305 | 0.303 |
| 2 (z = +1) | 26.56° | 0.200 | 0.198 |
| 3 (z = +3) | 19.63° | 0.113 | 0.118 |

**What we do with the output next.** These gates are the "coin" half of the full circuit (Step 6).

**Code.** `src/quantum_encoding.py → register_adapted_params`; the gates in `src/vqc_circuit.py → build_gci_circuit` and `src/transpilation.py → build_param_circuit`.

---

### Step 4a — Eq. 5: how many qubits

**Why it exists.** To know how big the circuit is.

**The equation (paper Eq. 5)**

$$
N_{\text{qubits}} = N_{\text{assets}} + \sum_k n_k
$$

| Symbol | Meaning | Value |
|---|---|---|
| N_assets | number of borrowers — one coin qubit each | 1 |
| n_k | qubits for risk factor k (the economy) | 2 or 3 |
| Σ | add up over all risk factors | one risk factor here |

**Worked example.** 1 + 2 = **3 qubits** (or 1 + 3 = 4). Scaling up: 2 borrowers and 2 risk factors with 2 qubits each → 2 + 2 + 2 = 6 qubits. A real bank portfolio of 1000 borrowers would need over 1000 qubits — which is why this is still a research demonstration.

**What we do with the output next.** Fixes the circuit layout: qubits 0…n−1 are the economy register, qubit n is the coin.

**Code.** `n_total = n_z_qubits + 1` in `src/vqc_circuit.py`.

---

### Step 4b — Eq. 6: what the economy register must become

**Why it exists.** It states precisely the goal of the economy dice before we design them.

**The equation (paper Eq. 6)**

$$
|\psi(\theta)\rangle = \sum_{b} \sqrt{p_b(\theta)}\;|b\rangle
$$

| Symbol | Meaning |
|---|---|
| \|ψ(θ)⟩ | the state of the register — the whole collection of amplitudes ("psi") |
| θ | the knob angles |
| \|b⟩ | basis state = bin b |
| √p_b | the amplitude on bin b |
| Σ | the state is a mix of all bins |

**Why square roots.** Probability = amplitude² (Born rule, 1.4). So to get probability p_b, the amplitude must be √p_b.

**Worked example.** Target [0.009, 0.491, 0.491, 0.009] needs amplitudes [0.095, 0.701, 0.701, 0.095].

**What we do with the output next.** Step 5 designs gates that produce this state.

---

### Step 5a — Eq. 12, 13: the economy dice (the "ansatz")

**Ansatz** (German for "approach") = the fixed layout of a trainable circuit: which gates go where. Only the angles are trained; the layout stays fixed.

**Why it exists.** We need actual gates whose output, for the right angles, is the bell curve.

**The design (paper Figs. 1–3)**
- one **Ry(θᵢ)** on each economy qubit — the knobs;
- then **CNOT** gates from qubit 0 to every other qubit — a "star" pattern.

**Eq. 12 — the rotation as a matrix**

$$
R_Y(\theta) = \begin{bmatrix}\cos\frac{\theta}{2} & -\sin\frac{\theta}{2}\\ \sin\frac{\theta}{2} & \cos\frac{\theta}{2}\end{bmatrix}
$$

This is just Ry written so it can be multiplied out. Starting from |0⟩ it gives amplitude cos(θ/2) on 0 and sin(θ/2) on 1.

**Eq. 13 — what the CNOT does.** After the two rotations, the four amplitudes are products like cos(θ₀/2)·cos(θ₁/2). The CNOT **swaps two of the four amplitudes**. That swap is what lets the register put most probability in the **middle** two bins and little at the **edges** — a bell shape. Without it, the two qubits act independently and you can only get flat or lopsided shapes.

**Worked example (2 qubits)**
- θ₀ = 90°, θ₁ = 90° → [0.25, 0.25, 0.25, 0.25] — flat, every bin equal.
- θ₀ = 90°, θ₁ = 195.4° (the trained value) → [0.009, 0.491, 0.491, 0.009] — exactly the target bell curve.

**What we do with the output next.** Eq. 8–9 compute the probabilities this design gives for any knob setting, so the knobs can be trained.

**Code.** `src/vqc_circuit.py → build_ansatz`

---

### Step 5b — Eq. 8, 9: the probabilities the dice actually produce

**Why it exists.** To train the knobs we must compare what the dice produce with the target.

**The equation (paper Eq. 8 for 2 qubits, Eq. 9 for 3)**

$$
p_b(\theta) = \big|\langle b \mid \psi(\theta)\rangle\big|^2
$$

| Symbol | Meaning |
|---|---|
| ⟨b \| ψ(θ)⟩ | the amplitude of bin b in the state (read "the overlap of b with psi") |
| \| … \|² | squared — Born rule: amplitude² = probability |

**How we compute it.** During training we use an **exact statevector simulation** — perfect, no noise, no shots. This matches the paper, which also trained on a perfect simulator.

**What we do with the output next.** The probabilities p(θ) go into the loss (Eq. 11).

**Code.** `src/training.py → probabilities_from_theta`

---

### Step 5c — Eq. 11: how wrong are the dice? (training loss)

**Why it exists.** Training needs **one number** that says how far the dice are from the target.

**The equation (paper Eq. 11)**

$$
\mathcal{L}(\theta) = \sum_b \big(p_b(\theta) - p^\star_b\big)^2
$$

For each bin: take the difference between "what the dice produce" and "what they should produce", square it (so negative and positive errors both count, and big errors count more), and add up over all bins. This is called **mean squared error (MSE)**.

**Worked example.** With the flat start [0.25 × 4] against the target [0.009, 0.491, 0.491, 0.009]: each bin is off by 0.241, so L = 4 × 0.241² = **0.233**. After training: L = **0.00000002** (2 × 10⁻⁸).

**What we do with the output next.** Step 5d asks: which way should each knob turn to make L smaller?

**Code.** `src/parameter_shift.py → mse_loss`

---

### Step 5d — Parameter-shift rule: which way to turn each knob

**Why it exists.** To lower the loss, we need the **gradient** — for each knob, the slope of the loss. In ordinary machine learning that is done by **backpropagation**, which needs to see every internal value of the model. A quantum circuit doesn't allow that — you can only see measurement results. The **parameter-shift rule** gets the exact slope by running the circuit at two shifted settings.

**The equation (paper, unnumbered)**

$$
\frac{\partial p_b}{\partial \theta_i} = \frac{p_b(\theta_i + 90^\circ) - p_b(\theta_i - 90^\circ)}{2}
$$

$$
\frac{\partial \mathcal{L}}{\partial \theta_i} = \sum_b 2\,(p_b - p^\star_b)\,\frac{\partial p_b}{\partial \theta_i}
$$

| Symbol | Meaning |
|---|---|
| ∂/∂θᵢ | "how much does this change when knob i is nudged" — the slope |
| θᵢ ± 90° | run the circuit with knob i turned 90° up, then 90° down (π/2 radians) |

**Why it is exact.** For rotation gates the probability follows a sine wave in the angle, and for a sine wave, the difference between points 90° either side gives the exact slope. Ordinary "nudge by a tiny amount" methods are only approximate and very sensitive to noise. The project checks this: the shift-rule slope matches a careful numerical slope to **0.00000000004**.

The second line is the **chain rule**: it converts "how each probability changes" into "how the loss changes".

**Cost.** 2 extra circuit runs per knob per step.

**What we do with the output next.** The gradient goes to Adam.

**Code.** `src/parameter_shift.py → gradient`

---

### Step 5e — Adam: actually turning the knobs

**Why it exists.** Knowing the slope isn't enough — you need a rule for **how far** to turn each knob each step. Too far and you overshoot; too little and training is slow.

**The equation (paper, unnumbered; Kingma & Ba)**

$$
m \leftarrow 0.9\,m + 0.1\,g, \qquad v \leftarrow 0.999\,v + 0.001\,g^2, \qquad
\theta \leftarrow \theta - \eta\,\frac{\hat m}{\sqrt{\hat v} + \epsilon}
$$

| Symbol | Meaning | Value |
|---|---|---|
| g | the gradient from Step 5d | |
| m | running average of recent gradients — **momentum**: keeps moving in a consistent direction, ignores jitter | |
| v | running average of squared gradients — measures how big the slopes usually are, so each knob gets its **own step size** | |
| m̂, v̂ | m and v corrected for starting at zero | |
| η (eta) | **learning rate** — overall step size | 0.15 |
| ε | tiny number so we never divide by zero | 10⁻⁸ |

**Why Adam.** It is the paper's choice. Plain gradient descent needs a hand-tuned step size and tends to zigzag; Adam adapts automatically.

**Worked example.** Start from random angles; after **150 iterations** the 2-qubit knobs settle at **θ₀ = 90.0°, θ₁ = 195.4°**, loss 2 × 10⁻⁸. For 3 qubits: 90.0°, 55.0°, 131.0°, loss 0.049 (the star layout cannot reach the 8-bin bell curve exactly — see Part 4, Q6).

**What we do with the output next.** The trained angles θ\* are the dice half of the full circuit (Step 6). They are saved in `results/trained_parameters.json`. **They never change for a different borrower** — the economy is always N(0, 1) — which is why the app doesn't need to retrain.

**Code.** `src/adam.py → AdamOptimizer.step`; the loop in `src/training.py → train_gaussian_loader`

---

### Step 5f — Eq. 14–17: which angles give a bell shape (used only by 6A)

**Why it exists.** The paper worked out, from the formulas in Eq. 12–13, which angle ranges give a symmetric bell (not flat, not upside-down). On real hardware the authors used these rules to know **where to search** when they adjusted angles by hand.

**The equations (paper Eq. 14–17)**

$$
\theta_0 = 90^\circ,\ 270^\circ, \ldots \qquad 90^\circ < \theta_1 < 270^\circ \qquad \theta_2 = \theta_1 \pm 360^\circ n \qquad 90^\circ < \theta_2 < 450^\circ
$$

In words:
- θ₀ = 90° makes the curve symmetric (left half mirrors right half);
- θ₁ between 90° and 270° puts more probability in the middle than at the edges (a bell);
- θ₁ = 90° or 270° makes it flat; outside that range it is upside-down.

**What we do with the output next.** These become the **search ranges for 6A**, the paper's hand-tuning (Step 8). The project's automated method 6B doesn't need them.

**Code.** the ranges in `src/stages.py → paper_grid_loader`

---

### Step 6a — The full circuit

**Why it exists.** It joins the dice and the coin into one circuit — the credit-risk "uncertainty model".

**What it is.** n economy qubits with the trained Ry knobs and CNOTs, then the coin qubit with Ry(2β̃) and one CRy per economy qubit. Every qubit is measured at the end.

**What one shot looks like.** A bitstring of n + 1 bits, e.g. **`101`** (2-qubit register):
- **left bit** = coin: 1 → defaulted (the bank loses $1000);
- **right two bits** = economy bin: `01` → bin 1 → z = −1 (mild downturn).

So `101` reads: "mild downturn, and the borrower defaulted".

**Why the coin can't disturb the dice.** The coin is only ever a *target* of gates — nothing flows back into the economy qubits. So the economy distribution stays exactly as trained, and

> P(default and bin b) = P(bin b) × PD(bin b)

**Worked example.** The full circuit, on a perfect simulator, gives these probabilities:

| Bin | z | P(no default, bin) | P(default, bin) |
|---|---|---|---|
| 0 | −3 | 0.0052 | 0.0038 |
| 1 | −1 | 0.3425 | 0.1485 |
| 2 | +1 | 0.3940 | 0.0970 |
| 3 | +3 | 0.0079 | 0.0011 |
| **Total** | | **0.750** | **0.250** |

Total default probability ≈ **0.25** — exactly the borrower's average, as it should be.

**The commanded angles x.** From now on all the knobs together — dice angles plus coin angles — are written as one list:

> x = [θ₀, …, θₙ₋₁, β̃, α̃]

"Commanded" because these are the angles **we ask for**; Step 7 shows the chip doesn't apply exactly these.

**What we do with the output next.** Transpile it for the chip.

**Code.** `src/vqc_circuit.py → build_gci_circuit`; `src/transpilation.py → build_param_circuit` (the version where every angle can be tuned)

---

### Step 6b — SABRE transpilation: rewrite for the chip

**Why it exists.** The chip can only do 4 native operations (`rz`, `sx`, `x`, `cz`) and only between neighbouring qubits. Our circuit uses Ry, CNOT and CRy, and CRy needs qubits that are not neighbours. So it must be rewritten.

**What SABRE does.** SABRE (SWAP-based BidiREctional heuristic search) does two jobs:
1. **Layout:** decides which physical qubit plays each logical role.
2. **Routing:** where two non-neighbouring qubits must interact, it inserts **SWAP** operations that move the information next to each other.

It searches for the arrangement that keeps the circuit shortest. Every gate is also rewritten into the 4 native operations.

**No equation** — it is a search algorithm (paper reference 38).

**Worked example.**

| | Before | After |
|---|---|---|
| 2-qubit-register circuit, depth | 6 | 33 |
| 2-qubit-register circuit, two-qubit gates | 5 (if all qubits were connected) | 8 |
| 3-qubit-register circuit, depth | 8 | 56 |
| 3-qubit-register circuit, two-qubit gates | 8 | 14 |

The extra two-qubit gates are the price of limited connectivity — and two-qubit gates are the noisiest operations on the chip.

**Key point.** SABRE makes the circuit **fit** the chip, but it knows nothing about how **noisy** each gate is. A well-transpiled circuit can still give the wrong answer. That is the gap the rest of the project addresses.

**What we do with the output next.** The transpiled circuit runs on the noisy chip.

**Code.** `src/transpilation.py → transpile_for_device`

---

### Step 7 — The noisy chip (this project's addition)

**Why it exists.** The paper ran on a real superconducting chip. We don't have one, so we **emulate** one: a simulator with the same three error types the paper names. This also lets the experiment be repeated exactly and stress-tested.

**The three error models**

**(a) Gate noise — depolarizing**

$$
\rho \to (1-p)\,\rho + p\,\frac{I}{d}
$$

With probability p, a gate replaces the qubits' state with complete randomness (I/d means "all outcomes equally likely"). Here ρ is the qubits' state (a different ρ from the correlation in Eq. 1 — physicists reuse letters). p = **0.2 %** for one-qubit gates, **1.5 %** for two-qubit gates. These are realistic figures for today's superconducting chips.

**(b) Readout error.** For each physical qubit, a small table: chance of reading 1 when the truth is 0, and 0 when the truth is 1 — between **2 % and 7 %** per qubit, about 5 % on average (the paper reports "about 5 %"). Reading 1 as 0 is more common, because a qubit in state 1 can decay to 0 during the measurement.

**(c) Drift (control miscalibration)**

$$
\theta_{\text{real}} = (1+\varepsilon)\,\theta + \delta
$$

| Symbol | Meaning | Value |
|---|---|---|
| θ | the angle we command | |
| ε (epsilon) | pulse-strength error: +0.12 means 12 % too strong | up to ±14 % |
| δ (delta) | constant offset | up to ±15° |
| θ_real | the angle the chip actually applies | |

Each physical qubit has its own ε and δ. **They are hidden** — no fixing method is ever shown them. The methods only see measurement counts, like an experimenter in front of a real chip.

**Worked example.** Commanded 90° on a qubit with ε = +0.12, δ = +10° → real angle = 1.12 × 90° + 10° = **110.8°**.

**Result.** Running the perfectly trained angles on this chip, the output matches a perfect chip with fidelity only **0.88** (2-qubit register) and **0.92** (3-qubit). (Fidelity is explained in Step 8a; 1.00 would be perfect.)

**What we do with the output next.** Measure how wrong the output is (Step 8a) and fix the angles (Step 8b).

**Code.** `src/noise_model.py → build_noise_model`, `ControlDrift`; `src/device.py → NoisyDevice`

---

### Step 8a — Hellinger distance and fidelity: measuring how wrong (this project's addition as the objective)

**Why it exists.** To fix the angles automatically, "does the output look right?" must become **one number** an algorithm can push down. The paper uses Hellinger fidelity to *report* its result; this project also uses it as the thing to *minimise*.

**The equations**

$$
\text{BC}(p, q) = \sum_i \sqrt{p_i\, q_i}, \qquad H(p,q) = \sqrt{1 - \text{BC}}, \qquad F_H = \text{BC}^2
$$

| Symbol | Meaning |
|---|---|
| p | the distribution the noisy chip produced (from shots) |
| q | the distribution a perfect chip would produce (the **reference**) |
| BC | "Bhattacharyya coefficient" — how much the two distributions overlap; 1 = identical |
| H | **Hellinger distance** — 0 = identical, 1 = completely different. **This is what calibration minimises.** |
| F_H | **Hellinger fidelity** — 1 = identical. This is what we report. |

**The calibration objective (our addition)**

$$
J(x) = H\big(p_{\text{chip}}(x),\ p_{\text{reference}}\big)
$$

Send commanded angles x to the chip, run 4 000 shots, compute the distance to the perfect-chip output. Small J = good angles.

**Measured after readout correction.** The histogram is cleaned of readout errors (Step 9b) *before* computing J. Otherwise the angles would be bent to compensate for readout errors, and the later readout correction would fix the same error a second time.

**Worked example.** Perfect chip [0.25, 0.25, 0.25, 0.25] vs chip [0.20, 0.30, 0.30, 0.20]: BC = 2√(0.25×0.20) + 2√(0.25×0.30) = 0.447 + 0.548 = 0.995 → F_H = **0.990**, H = **0.071**.

**Why Hellinger** (not something else): see Part 4, Q15.

**What we do with the output next.** J feeds both fixing methods, 6A and 6B.

**Code.** `src/metrics.py`; `src/calibration.py → objective`; `src/mitigation.py → ReadoutMitigatedDevice`

---

### Step 8b — 6A: the paper's way of fixing the angles (grid sweep)

**Why it exists.** It is the base paper's own procedure, reproduced so our method can be compared against it fairly.

**What it does.** A **grid sweep**: try angles on a fixed grid of values, keep the best, then try a finer grid around it. One or two knobs at a time; the rest stay fixed; θ₀ is never adjusted.
- 2-qubit register: θ₁ from 90° to 450° in 21° steps, then 1° steps around the best.
- 3-qubit register: θ₁ and θ₂ from 90° to 450° in 36° steps, then 7.5° (θ₁) and 14.5° (θ₂) steps.
- Full circuit: the two coin angles on a 2-D grid (10° × 3°, then 2° × 0.5°).

These ranges and steps are the paper's own (Sections IV-A to IV-C, Table 3).

**No formula** — "measure J at every grid point, keep the lowest".

**Result.** Fidelity **0.939** (2-qubit) and **0.957** (3-qubit), using **347** and **477** circuit runs. Cross-check with the paper: our sweep moves θ₁ from 195° to about **234°**; the paper found **237°** and **224°** on two qubit pairs of its real chip.

**Why it falls short.** θ₀ is never adjusted, so drift on the first qubit can never be corrected. And the number of grid points multiplies with every extra knob, so it becomes hopeless for bigger circuits.

**Code.** `src/calibration.py → grid_sweep`; ranges in `src/stages.py`

---

### Step 8c — 6B: this project's automatic fixing (the main contribution)

**Why it exists.** To replace the paper's manual grid search with an algorithm that tunes **all** knobs at once, needs fewer circuit runs, and needs no person.

It combines two optimisers.

**Bayesian optimisation (BO) — smart guessing.** BO keeps a **map** of J built from every point measured so far. The map is a **Gaussian process**: a statistical model that predicts J everywhere (μ, the prediction) and also says how sure it is (σ, the uncertainty). Points near measured ones are predicted confidently; far away, less so.

Each step, BO measures the point with the highest **Expected Improvement**:

$$
\mathrm{EI}(x) = (J^\ast - \mu)\,\Phi(z) + \sigma\,\varphi(z), \qquad z = \frac{J^\ast - \mu}{\sigma}
$$

| Symbol | Meaning |
|---|---|
| J\* | the best (lowest) J found so far |
| μ, σ | the map's prediction and uncertainty at x |
| Φ, φ | the normal CDF and the bell curve's height |

In words: a point is attractive if the map predicts it is **better than the best so far** (exploit), *or* if the map is **very unsure** there and it might be better (explore). BO finds good regions with very few measurements — ideal when each measurement costs a circuit run.

**SPSA — fine-tuning.** SPSA (Simultaneous Perturbation Stochastic Approximation) estimates the slope in **all** directions from just **two** measurements:

$$
\hat g = \frac{J(x + c\Delta) - J(x - c\Delta)}{2c}\,\Delta, \qquad x \leftarrow x - a\,\hat g
$$

| Symbol | Meaning |
|---|---|
| Δ | a random list of +1 and −1, one per knob — every knob is nudged at once, in a random direction |
| c | how far to nudge (shrinks over time) |
| a | step size (shrinks over time) |
| ĝ | estimated slope |

It works even though the measurements are noisy, because the random errors average out over many steps.

**The 6B procedure (4 steps)**
1. **BO on the dice knobs**, on the stand-alone economy circuit, same physical qubits — 40 runs.
2. **BO on the two coin knobs**, full circuit, dice knobs frozen — 30 runs.
3. **SPSA on all knobs together** — 60 steps × 2 runs. Catches interactions the block-by-block search misses.
4. **Verify** — re-measure both candidates (after step 2 and step 3) with more shots; keep the better one.

**Result.** Fidelity **0.982** (2-qubit) and **0.994** (3-qubit), using **204** circuit runs — better than 6A with fewer runs.

**Why both optimisers**: see Part 4, Q13.

**What we do with the output next.** The calibrated angles x\* are sent to the chip for the real runs.

**Code.** `src/calibration.py → bayesian_opt`, `spsa`, `hierarchical_calibration`

---

### Step 9a — Repeated execution (this project's addition)

**Why it exists.** Results from shots are random. One run might be lucky. Repeating gives **error bars** — a measure of how much the result wobbles.

**The idea.** A probability p measured with N shots has a typical error of

$$
\sqrt{\frac{p(1-p)}{N}}
$$

For p = 0.25: N = 4 000 → ±0.7 %; N = 20 000 → ±0.3 %.

**What we do.** Run each version **20 times × 20 000 shots** and report the average and the spread. The spreads come out at ±0.001–0.003 in fidelity — small enough that every difference between methods is real, not luck.

**Code.** `src/stages.py → execute_variants`

---

### Step 9b — Readout error mitigation (this project's addition)

**Why it exists.** Readout errors (1.6) distort every measurement. The paper applied no correction; it listed this as future work.

**The idea.** First, measure **how** the chip misreads: prepare every possible outcome on purpose (e.g. set the qubits to `101`), measure many times, and record what comes out. This gives a table A — the **assignment matrix**:

$$
A_{is} = P(\text{read } i \mid \text{prepared } s)
$$

A measured distribution m is the true distribution p scrambled by A:

$$
m = A\,p
$$

So to recover p, "undo" A: find the p that best explains m, with all probabilities ≥ 0 — a method called **non-negative least squares (NNLS)**.

**Worked example.** If a qubit reads a true 1 as 0 6 % of the time, a true default rate of 0.250 shows up as about 0.235 before correction; mitigation brings it back to about 0.250.

**Result.** On its own it **cannot** fix drift (uncalibrated + mitigation: 0.92 / 0.91). After 6B retuning it gives **0.982 / 0.995**.

**Code.** `src/mitigation.py → assignment_matrix`, `apply_readout_mitigation`

---

### Step 9c — Zero-noise extrapolation (ZNE) (this project's addition, optional)

**Why it exists.** Some gate noise remains after retuning. ZNE estimates what a noise-free chip would give. The paper only mentioned it.

**The idea.** Make the noise **worse on purpose**, watch how the result changes, and extend the trend back to zero noise.

How to make it worse without changing the answer: run the circuit forwards, then backwards, then forwards again. Backwards undoes forwards, so the logical result is the same, but the chip performs three times as many noisy gates:

$$
U \to U\,(U^\dagger U)^k, \qquad \lambda = 2k + 1 = 1, 3, 5
$$

U is the circuit, U† is its reverse, λ (lambda) is the noise multiplier. Then fit each probability as a straight line in λ and read off the value at λ = 0:

$$
p(\lambda) \approx a + b\,\lambda \;\Rightarrow\; p(0) \approx a
$$

**Result.** 0.982 → **0.998** (2-qubit), 0.995 → **0.996** (3-qubit). But it costs up to 1 + 3 + 5 = **9×** the chip time, so it is offered as an option, not the default.

**Code.** `src/mitigation.py → fold_circuit`, `zne_extrapolate`, `run_zne`

---

### Step 10a — Post-processing: from bitstrings to money (paper Section IV-C)

**Why it exists.** A bank wants losses, not bitstrings.

**What we do.** For every measured bitstring:
- right n bits → economy bin b;
- left bit → defaulted (d = 1) or not (d = 0);
- loss of that outcome = d × LGD.

Then add up probabilities with equal losses (→ PDF), take the running total (→ CDF), and compute the expected loss.

$$
F(L) = \sum_{L' \le L} P(L'), \qquad \mathbb{E}[L] = \sum_L L\,P(L)
$$

| Symbol | Meaning |
|---|---|
| F(L) | the CDF — chance the loss is at most L |
| 𝔼[L] | expected (average) loss |

**Worked example.** Add up all the "default" rows of the table in Step 6a: P(loss = $1000) = 0.250, P(loss = $0) = 0.750.
- CDF: F($0) = 0.75, F($1000) = 1.00 — the same as the paper's Fig. 10.
- Expected loss = 0 × 0.75 + 1000 × 0.25 = **$250**.

**The conditional-default check (our addition).** From the same counts we can recover the default rate inside each economy bin:

$$
P(\text{default} \mid z_b) = \frac{P(\text{default and bin } b)}{P(\text{bin } b)}
$$

and compare it with Eq. 1. This checks that the **finance model itself** survived the noise, not just the histogram. Example: bin 1: 0.1485 / 0.4910 = **0.302** vs Eq. 1's 0.303.

**What we do with the output next.** Read off VaR; compute fidelity.

**Code.** `src/postprocessing.py → decompose`, `credit_statistics`

---

### Step 10b — Value at Risk

**Why it exists.** It is the number regulators ask for.

**The equation**

$$
\mathrm{VaR}_{95\%} = \text{the smallest } L \text{ with } F(L) \ge 0.95
$$

In words: walk up the CDF and stop at the first loss where the running total reaches 95 %.

**Worked example.** F($0) = 0.75 — not yet 95 %. F($1000) = 1.00 — reached. So **VaR = $1000**, matching the paper.

**Why VaR is the same for every version.** With one borrower the loss can only be $0 or $1000. Since P(loss = $0) ≈ 0.75 is below 0.95, the 95 % point is always at $1000 — for the good circuit *and* the bad one. So VaR alone cannot tell them apart; **fidelity** does. The paper makes the same point. (For a borrower with a default probability below 5 %, VaR becomes $0 — the app lets you try that.)

**Code.** `src/postprocessing.py → value_at_risk`

---

### Step 11 — The fidelity gate: accept or recalibrate (this project's addition)

**Why it exists.** Real chips drift over time, so a calibration that worked yesterday may fail today. The paper calibrated once, by hand. This project checks automatically and repairs itself.

**The rule**

$$
F_H \ge 0.97 \;\Rightarrow\; \text{ACCEPT}; \qquad \text{otherwise} \;\Rightarrow\; \text{RE-CALIBRATE (re-run 6B, check again)}
$$

**Worked example.** Calibrated chip: 0.982 → ACCEPT. Then the chip "drifts overnight" (new hidden ε and δ). Yesterday's angles give **0.53** → RE-CALIBRATE → 6B runs again (204 runs) → **0.97** → ACCEPT. A manual re-sweep would cost 347 runs and a person.

**Code.** `src/stages.py → acceptance_check`, `recalibration_loop`

---

## Part 4 — Why we chose what we chose

**Q1. Why does the economy axis run from −3 to +3? Is 3 a limit?**
Not a hard limit — z can be any number. But z is a standard normal, and **99.7 %** of all possible economies lie between −3 and +3. A register has only 4 or 8 bins, so we must decide which stretch of the bell curve they cover. Wider (say ±4) wastes bins on nearly impossible economies; narrower (say ±2) cuts off severe recessions, which matter most to a bank. The paper writes the range as [−z_max, z_max] but does not give a number; **z_max = 3 is this project's choice** (the usual "three standard deviations"). It is one setting, `Z_MAX` in `src/config.py`.

**Q2. What is a "bin", and why do we need bins at all?**
A bin is one bucket of a histogram. A quantum register can only show a fixed number of outcomes (2ⁿ), so the smooth economy curve must be cut into that many buckets, each standing for one economy value. More qubits → more bins → a smoother curve.

**Q3. Why 2 or 3 qubits for the economy? Why not a fixed number, or more?**
- **2 qubits (4 bins)** is exactly the paper's hardware experiment, so it is needed for a fair replication.
- **3 qubits (8 bins)** tests whether the methods still work when the problem grows. The paper only built the 3-qubit economy register on its own; it never ran the full 4-qubit credit circuit. This project does.
- Running **both** answers "does it scale?" — the automatic method's advantage over the grid sweep **grows** with size (204 vs 477 runs at 3 qubits).
- **Not more**, because every extra qubit adds two-qubit gates (more noise), deepens the transpiled circuit (more noise), and makes the paper's simple dice layout even less able to draw a smooth bell curve (see Q6). Each run uses one size; "2 or 3" means the project studies both.

**Q4. Why is "default" written as sin²?**
Because a rotation gate produces exactly sin²-shaped probabilities. Writing the default curve as sin²(αz + β) lets one rotation produce it.

**Q5. Why a straight line αz + β inside the sin²?**
Because a straight line in z becomes a straight line in the bin number b, and that splits into one plain rotation plus one controlled rotation per qubit — only n + 1 gates. A curved fit would need extra two-qubit gates (more noise), and the straight line is already accurate to 0.0065.

**Q6. Why the "star" CNOT layout? Is it the best?**
It is the paper's design, kept so the replication is faithful. For 2 qubits it is perfect. For 3 qubits it has only 3 knobs and cannot draw the 8-bin bell curve exactly (best match ≈ 0.78 fidelity to the ideal curve). A "chain" layout (CNOT 0→1, 1→2) does better — loss 0.0018 against 0.049 — and is reported as a finding and future work.

**Q7. Why Ry rotations and not Rx or Rz?**
Ry keeps every amplitude a plain real number and directly sets P(1) = sin². Other rotations add "phases" that don't change probabilities and would only waste gates.

**Q8. Why mean squared error for training?**
The paper's choice. It is smooth (easy to optimise) and never infinite. Other measures like KL divergence become infinite when a bin is empty.

**Q9. Why 150 Adam iterations and a learning rate of 0.15?**
The paper reports convergence in about 150 iterations. The learning rate 0.15 gives smooth, fast convergence for these few knobs; the 2-qubit loss reaches 2 × 10⁻⁸, so more iterations would not help.

**Q10. Why train on a perfect simulator first, if the chip is noisy?**
That is the paper's two-phase approach: design and train in the ideal world, then adapt to the hardware. It also gives us the **reference** (what a perfect chip would output) that calibration aims for.

**Q11. Why emulate the chip instead of using a real one?**
No hardware access was available. An emulated chip is free, unlimited, and exactly repeatable, and it carries the same three error types the paper names. The calibration only needs measurement counts, so it could run unchanged on a real IBM chip (future work).

**Q12. Why is the drift hidden from the calibration?**
On a real chip nobody knows the exact errors — you only see results. Hiding ε and δ makes the test honest: if the methods could read them, they could simply undo them.

**Q13. Why BO first and then SPSA? Why not just one?**
Tested directly (called **ablations**). On the 3-qubit register: SPSA alone 0.947; BO alone 0.964; BO then SPSA **0.994**. BO quickly finds the right region with few runs but gets stuck refining many knobs at once; SPSA refines efficiently but wanders from a poor start. Together: BO places, SPSA polishes.

**Q14. Why 40, 30 and 60 for the step budgets, and ±45° for BO?**
Chosen so the whole 6B procedure costs about 200 runs — clearly less than 6A — while leaving enough measurements for each stage. ±45° is wide enough to cover the drift (up to ~±40° of effective error) without searching useless angles.

**Q15. Why Hellinger fidelity and not some other comparison?**
It is the paper's own reporting metric (98.9 %), so results are directly comparable. It is always between 0 and 1, symmetric, and never infinite even when a bin is empty.

**Q16. Why 4 000 shots during calibration but 20 000 for the final runs?**
Calibration needs **many** measurements (hundreds), each only roughly accurate (±0.7 %); 4 000 keeps it fast. The final numbers need **few** measurements, each very accurate (±0.3 %), to see small differences such as ZNE's effect.

**Q17. Why 20 repetitions?**
Enough for reliable error bars (the paper used 100 hardware repetitions; on a simulator 20 already give stable spreads), while keeping the run under a minute.

**Q18. Why ZNE with λ = 1, 3, 5 and a straight-line fit?**
Global folding can only multiply the circuit by odd numbers (1, 3, 5, …). Three points are enough for a straight line; a curved fit through three noisy points would exaggerate the noise.

**Q19. Why is the acceptance threshold 0.97?**
Close to the paper's real-hardware result (98.9 %), but with room for shot noise so a good calibration isn't rejected by bad luck. It is a setting in `src/config.py`.

**Q20. Why is VaR always $1000?**
With one borrower the loss is either $0 or $1000, and P(loss = $0) ≈ 0.75 is below 0.95, so the 95 % point is always $1000. That is why the project judges results by fidelity, not VaR. The paper says the same.

**Q21. Is there a dataset?**
No, and that is correct for this project. The input is a **model** of a borrower — p₀, ρ, LGD — and the assumption that the economy is N(0, 1). In a bank those numbers come from credit ratings and the Basel formula, which were estimated from historical data. Everything else is computed from them.

**Q22. Where do p₀ = 0.25, ρ = 0.027 and LGD = $1000 come from?**
Directly from the base paper (Section IV-C and Fig. 10). They are demonstration values: a 25 % default rate shows up clearly on a noisy chip; a real borrower's 1 % would drown in noise. Using the paper's values lets our results be compared with theirs.

**Q23. Why does the quantum result struggle for low default probabilities?**
The calibration minimises the difference over the **whole** distribution. When default is rare (say 4 %), the default outcomes are a tiny part of that distribution, so small errors there barely change the score — but they can flip VaR. A calibration objective that also weights the loss directly is listed as future work.

**Q24. What would make this useful for a real bank?**
Running Quantum Amplitude Estimation on top of the calibrated circuit (the speed-up), many borrowers and risk factors (many more qubits), and a real quantum chip. This project solves the step those need first: getting the model to load correctly on noisy hardware.

---

## Part 5 — Word list

| Word | Plain meaning |
|---|---|
| Ablation | Removing or replacing one part of a method to see how much it contributed |
| Adam | An optimiser that adjusts each knob's step size automatically |
| Amplitude | The weight on an outcome; probability = amplitude² |
| Ansatz | The fixed layout of a trainable circuit |
| Assignment matrix (A) | Table of how often the chip misreads each outcome |
| Basis state | One specific outcome of a register, e.g. \|01⟩ |
| Bayesian optimisation (BO) | Smart guessing using a map of the score built from past measurements |
| Bin | One bucket of a histogram |
| Bitstring | The row of 0s and 1s read from a measurement, e.g. `101` |
| Born rule | Probability = amplitude² |
| CDF | Running total of probabilities: P(loss ≤ L) |
| CNOT | Two-qubit gate: flip B if A is 1 |
| Commanded angles (x) | The angles we ask the chip to apply |
| Conditional probability | Chance of A given B, written P(A \| B) |
| Coupling map | Which physical qubits can interact directly |
| CRy | Controlled rotation: rotate B if A is 1 |
| Depolarizing noise | Each gate slightly randomises the state |
| Depth | Number of gate layers in a circuit |
| Drift | The chip's rotations being off by a fixed, unknown amount |
| Entanglement | Qubits whose results depend on each other |
| Expected loss | Average loss = PD × LGD |
| Expected Improvement (EI) | BO's rule for choosing the next point to measure |
| Fidelity (Hellinger) | How alike two distributions are; 1 = identical |
| Gaussian process | A model that predicts a value and its uncertainty everywhere |
| GCI model | Vasicek credit model: borrowers independent once the economy is known |
| Gradient | The slope of the loss for each knob |
| Grid sweep | Trying every value on a fixed grid |
| Hellinger distance (H) | How different two distributions are; 0 = identical |
| Iteration | One round of measure → compute → adjust |
| Learning rate | Overall step size of an optimiser |
| LGD | Loss given default — money lost if the borrower defaults |
| Logical / physical qubit | Qubit in the design / actual qubit on the chip |
| Loss function | One number saying how wrong the output is |
| Monte Carlo | Estimating by simulating many random cases |
| MSE | Mean squared error — sum of squared differences |
| Native gates | Operations the chip can do directly |
| NISQ | Today's small, noisy quantum chips |
| NNLS | Non-negative least squares — solving m = A·p with p ≥ 0 |
| Normal distribution N(0, 1) | Bell curve with mean 0 and standard deviation 1 |
| Parameter shift | Exact slope from two runs at ±90° |
| PD | Probability of default |
| PDF | List of outcome → probability |
| Φ, Φ⁻¹ | Normal CDF (number → probability) and its inverse |
| QAE | Quantum Amplitude Estimation — the quadratically faster replacement for Monte Carlo |
| Qubit | Quantum bit; can be partly 0 and partly 1 until measured |
| Readout error | Measurement reporting the wrong bit |
| Readout mitigation | Undoing readout errors using the assignment matrix |
| Register | Group of qubits storing one number; n qubits → 2ⁿ outcomes |
| Ry(θ) | Rotation gate; P(1) = sin²(θ/2) |
| SABRE | Algorithm that fits a circuit onto a chip's layout |
| Shot | One run and measurement of the circuit |
| Simulator | Software that computes what a quantum circuit would do |
| SPSA | Optimiser that gets the slope in all directions from two runs |
| Standard deviation (σ) | How spread out a distribution is |
| Statevector | The exact list of amplitudes, computed without noise |
| SWAP | Operation that exchanges two qubits' information |
| Transpilation | Rewriting a circuit for a specific chip |
| VaR | Value at Risk — the loss not exceeded in 95 % of years |
| z | State of the economy, in standard deviations from average |
| ZNE | Zero-noise extrapolation — add noise on purpose, extend back to zero |

---

*All results in this guide come from the project's own pipeline on a simulator with an emulated noise model, not from a physical quantum computer.*
