"""
app.py -- interactive demo of the quantum credit-risk pipeline.

Run:   streamlit run app.py

Choose a borrower (p0, rho, LGD) and how the noisy quantum chip is handled
(calibration, mitigation, drift). The app runs the full pipeline from src/ and shows
the bank's risk numbers from the quantum circuit next to the classical answer.
"""

import json
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from src import config as C
from src.app_core import CALIBRATION_METHODS

# ---------------------------------------------------------------- style
QUANTUM, IDEAL, CLASSICAL = "#2a78d6", "#eb6834", "#52514e"
INK, MUTED, GRID = "#0b0b0b", "#6b6a66", "#e6e5e0"
plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "legend.frameon": False,
})

st.set_page_config(page_title="Quantum Credit Risk", layout="wide")


@st.cache_data(show_spinner=False)
def run(p0, rho, lgd, confidence, n, method, use_rem, use_zne, drift, loop, shots):
    # The quantum simulation runs in its own process: Qiskit is not safe to run inside
    # Streamlit's script threads, and a separate process keeps the app alive whatever happens.
    kwargs = dict(p0=p0, rho=rho, lgd=lgd, confidence=confidence, n=n, method=method,
                  use_rem=use_rem, use_zne=use_zne, drift_event=drift,
                  auto_recalibrate=loop, shots=shots)
    root = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.run([sys.executable, "-m", "src.app_worker"], input=json.dumps(kwargs),
                          capture_output=True, text=True, cwd=root, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError("The quantum simulation failed:\n" + proc.stderr[-2000:])
    return json.loads(proc.stdout)


def money(x):
    """Dollar amount for plain text (metric values, tables)."""
    return f"${x:,.0f}"


def money_md(x):
    """Dollar amount for Markdown text: '$' must be escaped or Streamlit reads it as maths."""
    return f"\\${x:,.0f}"


# ---------------------------------------------------------------- sidebar: inputs
st.sidebar.header("1 · Borrower")
p0 = st.sidebar.slider("Average default probability p₀", 0.01, 0.50, C.P0, 0.01,
                       help="Chance the borrower defaults in an average economy.")
rho = st.sidebar.slider("Correlation with the economy ρ", 0.00, 0.30, C.RHO, 0.001, format="%.3f",
                        help="How strongly the borrower's default depends on the economy. "
                             "0 = not at all.")
lgd = st.sidebar.number_input("Loss given default (LGD, $)", 100, 1_000_000, C.LGD, 100,
                              help="Money lost if the borrower defaults.")
confidence = st.sidebar.select_slider("VaR confidence", [0.90, 0.95, 0.99], C.CONFIDENCE)

st.sidebar.header("2 · Quantum chip")
n = st.sidebar.radio("Economy register", [2, 3], format_func=lambda k: f"{k} qubits ({2 ** k} economy states)",
                     horizontal=True)
method = st.sidebar.selectbox("Calibration on the noisy chip", CALIBRATION_METHODS, index=2)
use_rem = st.sidebar.checkbox("Readout-error mitigation", True)
use_zne = st.sidebar.checkbox("Zero-noise extrapolation (slower)", False)
shots = st.sidebar.select_slider("Shots", [4000, 10000, 20000], 20000)

st.sidebar.header("3 · Scenario")
drift = st.sidebar.checkbox("Chip drifts after calibration", False,
                            help="The chip gets a new miscalibration after it was calibrated "
                                 "('the next day').")
loop = st.sidebar.checkbox("Closed loop: auto re-calibrate if the check fails", False)

go = st.sidebar.button("Run analysis", type="primary", use_container_width=True)

# ---------------------------------------------------------------- header
st.title("Quantum Credit Risk on a Noisy Chip")
st.caption("A variational quantum circuit loads the GCI (Vasicek) credit-risk model, runs on an emulated "
           "noisy quantum chip, and is calibrated automatically. Its risk numbers are compared with "
           "the classical answer.")

if "result" not in st.session_state and not go:
    st.info("Choose a borrower and chip settings on the left, then press **Run analysis**. "
            "A run takes about 3–10 seconds.")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**Input** — no dataset is needed. The borrower is described by three numbers: "
                "average default probability p₀, correlation ρ with the economy, and the loss given "
                "default. The economy itself is modelled as a standard normal variable.")
    c2.markdown("**What happens** — p₀ and ρ become a default curve (Vasicek), the curve becomes "
                "rotation angles, a trained circuit loads the economy's bell curve, the circuit runs "
                "on a noisy chip, the angles are calibrated, and thousands of measurements are "
                "turned into losses.")
    c3.markdown("**Output** — default probability in each economy state, overall default "
                "probability, expected loss, Value at Risk, and a fidelity check that says "
                "whether the quantum result can be trusted.")
    st.stop()

if go:
    with st.spinner("Running the quantum pipeline…"):
        st.session_state.result = run(p0, rho, float(lgd), confidence, n, method,
                                      use_rem, use_zne, drift, loop, shots)
r = st.session_state.result
inp = r["inputs"]
q, cl, ideal = r["quantum"], r["classical"], r["ideal"]

# ---------------------------------------------------------------- headline numbers
ok = r["decision"] == "ACCEPT"
cols = st.columns(5)
cards = [
    ("Default probability", f"{q['p_default']:.3f}", f"classical {cl['p_default']:.3f}"),
    ("Expected loss", money(q["expected_loss"]), f"classical {money_md(cl['expected_loss'])}"),
    (f"VaR {inp['confidence']:.0%}", money(q["var"]), f"classical {money_md(cl['var'])}"),
    ("Fidelity vs perfect chip", f"{r['fidelity_vs_ideal']:.3f}", f"threshold {r['threshold']:.2f}"),
]
for col, (label, value, note) in zip(cols, cards):
    col.metric(label, value)
    col.caption(note)
with cols[4]:
    st.markdown("Decision")
    (st.success if ok else st.error)(r["decision"])
    st.caption(inp["method"].split(" (")[0] + (" · drift" if inp["drift_event"] else ""))

if q["var"] != cl["var"]:
    st.warning(f"The quantum VaR ({money_md(q['var'])}) differs from the classical VaR "
               f"({money_md(cl['var'])}). This happens when the default probability is close to "
               f"{1 - inp['confidence']:.0%}: a small error in the default probability flips the "
               "VaR. Low default probabilities are the hardest case for the noisy chip.")
elif abs(q["p_default"] - cl["p_default"]) > 0.15 * cl["p_default"] + 0.005:
    st.warning("The quantum default probability is more than 15 % away from the classical one. "
               "Try a calibration method, readout mitigation, or a borrower closer to the paper's "
               "setting (p₀ = 0.25, ρ = 0.027).")

tab_res, tab_how, tab_about = st.tabs(["Results", "How it was computed", "About the inputs and outputs"])

# ---------------------------------------------------------------- results
with tab_res:
    z = np.array(r["z_grid"])
    left, right = st.columns(2)

    with left:
        st.subheader("Default probability in each economy state")
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.plot(r["pd_curve"]["z"], r["pd_curve"]["pd"], color=CLASSICAL, lw=2, label="Classical (Vasicek)")
        ax.plot(z, ideal["conditional_pd"], "s", color=IDEAL, ms=8, mec="white", mew=1.5,
                label="Circuit on a perfect chip")
        weight = np.array(q["z_marginal"]) / max(q["z_marginal"])
        ax.scatter(z, q["conditional_pd"], s=40 + 80 * weight, color=QUANTUM, edgecolor="white",
                   linewidth=1.5, zorder=3, label="Circuit on the noisy chip")
        ax.set_xlabel("Economy state z   (← recession · boom →)")
        ax.set_ylabel("P(default | z)")
        ax.set_ylim(0, max(0.05, np.nanmax(q["conditional_pd"] + ideal["conditional_pd"] + r["pd_curve"]["pd"]) * 1.15))
        ax.legend(loc="upper right", fontsize=9)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
        st.caption("Dot size = how often that economy state occurs. Extreme states (z = ±3) occur rarely, "
                   "so their estimate rests on few shots and is noisier.")

    with right:
        st.subheader("Loss distribution (CDF)")
        fig, ax = plt.subplots(figsize=(6, 3.6))
        lg = inp["lgd"]
        mc = r["monte_carlo"]
        ax.step(np.r_[-0.05 * lg, mc["unique_losses"], 1.1 * lg], np.r_[0, mc["cdf"], 1],
                where="post", color=CLASSICAL, lw=2, ls="--", label="Classical Monte Carlo")
        ax.step(np.r_[-0.05 * lg, q["unique_losses"], 1.1 * lg], np.r_[0, q["cdf"], 1],
                where="post", color=QUANTUM, lw=2, label="Quantum circuit")
        ax.axhline(inp["confidence"], color=MUTED, lw=1, ls=":")
        ax.text(0.45 * lg, inp["confidence"] + 0.015, f"{inp['confidence']:.0%} level", va="bottom",
                ha="center", color=MUTED, fontsize=9)
        ax.set_xlabel("Portfolio loss ($)")
        ax.set_ylabel("P(loss ≤ L)")
        ax.set_ylim(0, 1.05)
        ax.legend(loc="lower right", fontsize=9)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
        st.caption(f"P(loss = \\$0) = {q['p_loss_le_0']:.3f} quantum vs {cl['p_loss_le_0']:.3f} classical. "
                   "VaR is the first loss where the curve reaches the dotted line.")

    st.subheader("What the circuit measured")
    k = len(r["probs"]["quantum"])
    labels = [format(i, f"0{inp['n'] + 1}b") for i in range(k)]
    fig, ax = plt.subplots(figsize=(12, 3.0))
    x = np.arange(k)
    w = 0.38
    ax.bar(x - w / 2 - 0.01, r["probs"]["ideal"], w, color=IDEAL, label="Perfect chip")
    ax.bar(x + w / 2 + 0.01, r["probs"]["quantum"], w, color=QUANTUM, label="Noisy chip (after calibration and mitigation)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Bitstring   (left bit = default, right bits = economy state)")
    ax.set_ylabel("Probability")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", fontsize=9)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    with st.expander("Show the numbers as a table"):
        st.dataframe(pd.DataFrame({
            "economy state z": z,
            "P(default | z) classical": np.round([float(np.interp(v, r["pd_curve"]["z"], r["pd_curve"]["pd"])) for v in z], 4),
            "P(default | z) perfect chip": np.round(ideal["conditional_pd"], 4),
            "P(default | z) noisy chip": np.round(q["conditional_pd"], 4),
            "P(economy state) noisy chip": np.round(q["z_marginal"], 4),
        }), hide_index=True, use_container_width=True)
        st.dataframe(pd.DataFrame({
            "": ["Default probability", "Expected loss", "VaR", "CVaR", "P(loss = 0)"],
            "Quantum (noisy chip)": [f"{q['p_default']:.4f}", money(q["expected_loss"]), money(q["var"]),
                                     money(q["cvar"]), f"{q['p_loss_le_0']:.4f}"],
            "Classical (exact)": [f"{cl['p_default']:.4f}", money(cl["expected_loss"]), money(cl["var"]),
                                  money(cl["cvar"]), f"{cl['p_loss_le_0']:.4f}"],
            "Classical Monte Carlo": ["", money(mc["expected_loss"]), money(mc["var"]), "", ""],
        }), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- how
with tab_how:
    e = r["encoding"]
    ang = r["angles_deg"]
    st.markdown(f"""
**Stage 1 — Classical model.** p₀ = {inp['p0']:.3f} and ρ = {inp['rho']:.3f} give the Vasicek default curve
PD(z) = Φ((Φ⁻¹(p₀) − √ρ·z) / √(1 − ρ)). The economy z is discretised into {2 ** inp['n']} states on [−3, 3].

**Stage 2 — Encoding.** The curve is written as PD(z) ≈ sin²(αz + β):
α = {e['alpha_deg']:.2f}°, β = {e['beta_deg']:.2f}° (max fit error {e['fit_max_error']:.4f}).
On the register this becomes β̃ = {e['beta_tilde_deg']:.2f}° and α̃ = {e['alpha_tilde_deg']:.2f}°.

**Stages 3–4 — Circuit.** {inp['n']} economy qubits with trained angles θ* = {', '.join(f'{a:.1f}°' for a in ang['nominal'][:inp['n']])}
(they load the economy's bell curve and do not depend on the borrower) plus one default qubit rotated by the angles above.

**Stage 5 — Transpilation.** SABRE rewrites the circuit into the chip's native gates (rz, sx, x, cz) on a line of qubits.

**Stage 6 — Noisy chip and calibration.** The chip has gate noise, readout errors and hidden drift.
Method: *{inp['method']}* — {r['calibration_runs']} circuit runs.
Angles sent to the chip: {', '.join(f'{a:.1f}°' for a in ang['used'])}  (nominal: {', '.join(f'{a:.1f}°' for a in ang['nominal'])}).

**Stage 7 — Execution.** {inp['shots']:,} shots; readout mitigation {'on' if inp['use_rem'] else 'off'};
zero-noise extrapolation {'on' if inp['use_zne'] else 'off'}{'; the chip drifted after calibration' if inp['drift_event'] else ''}.

**Stage 8 — Post-processing.** Each bitstring is split: left bit = default (loss = {money_md(inp['lgd'])}), right bits = economy state.
Counting gives P(default) = {q['p_default']:.4f}, the loss CDF, expected loss {money_md(q['expected_loss'])} and VaR {money_md(q['var'])}.

**Stage 9 — Check.** Hellinger fidelity against a perfect chip = {r['fidelity_vs_ideal']:.4f}
(against the classical model: {r['fidelity_vs_classical']:.4f}). Threshold {r['threshold']:.2f} → **{r['decision']}**.
""")
    if len(r["loop"]) > 1 or inp["drift_event"]:
        st.markdown("**Closed loop log**")
        st.dataframe(pd.DataFrame([{"round": l["round"], "fidelity": round(l["fidelity"], 4),
                                    "decision": l["decision"]} for l in r["loop"]]),
                     hide_index=True, use_container_width=True)
        if r["recalibration_runs"]:
            st.caption(f"Automatic re-calibration used {r['recalibration_runs']} circuit runs.")
    st.caption(f"Run time {r['seconds']:.1f} s on this machine.")

# ---------------------------------------------------------------- about
with tab_about:
    st.markdown("""
**Is there a dataset?** No. The project follows the base paper: the input is a *model*, not data.
A borrower is described by its average default probability p₀ and its correlation ρ with the economy —
in a bank these two numbers come from the borrower's credit rating and the Basel formula, which were
themselves estimated from historical default data. The economy is a standard normal variable N(0, 1).
Everything else — the default curve, the circuit's training target, and the classical answer used for
checking — is computed from those numbers.

**What the quantum circuit does.** Each run of the circuit is one possible future: the economy qubits
pick an economy state with bell-curve probabilities, and the default qubit says whether the borrower
defaulted in that economy. Thousands of runs give the full loss distribution. Today this is a demonstration;
in a full quantum algorithm (amplitude estimation) the same circuit would give risk numbers with
quadratically fewer runs than classical Monte Carlo.

**What the outputs mean.**
- *Default probability* — overall chance the borrower defaults.
- *Expected loss* — average loss = default probability × LGD.
- *VaR* — the loss the bank is that confident it will not exceed. With one borrower it is either \\$0
  (if the default probability is below 1 − confidence) or the full LGD.
- *Fidelity* — how closely the noisy chip's output matches a perfect chip (1 = identical).
- *Decision* — ACCEPT if fidelity ≥ 0.97, otherwise RE-CALIBRATE.

**Things to try.**
1. Set calibration to *none*: fidelity falls and the default probability comes out wrong.
2. Switch to *6B automated*: it is corrected. Compare with *6A grid sweep*, the base paper's method.
3. Tick *Chip drifts after calibration*: the check says RE-CALIBRATE. Then tick *Closed loop*: it repairs itself.
4. Lower p₀ to around 0.04: the VaR becomes sensitive, the hardest case for a noisy chip.

*All results come from a simulator with an emulated noise model, not a physical quantum computer.*
""")
