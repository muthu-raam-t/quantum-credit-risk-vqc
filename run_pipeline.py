"""
run_pipeline.py -- MASTER RUNNER for the whole project.

Runs the nine stages in order (00 -> 09). Each stage reads the previous stage's
outputs, so running this one file reproduces every number and figure.

Two modes
---------
notebooks (default)  executes every stage notebook top-to-bottom with nbclient and
                     saves it IN PLACE, so every notebook afterwards contains its
                     fresh outputs and plots (this is what to show).
scripts              runs the headless scripts/run_stageXX_*.py files instead
                     (same computations, no notebook outputs; fastest).

Usage
-----
    python run_pipeline.py                     # all notebooks 00..09
    python run_pipeline.py --from 6            # only stages 6..9 (needs 1..5 done once)
    python run_pipeline.py --from 6 --to 7
    python run_pipeline.py --mode scripts      # headless run of stages 1..9

Typical run time on a laptop: ~4-6 minutes for everything.
"""

import argparse
import glob
import os
import runpy
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

NOTEBOOKS = {
    0: "00_overview.ipynb",
    1: "01_classical_gci_model.ipynb",
    2: "02_quantum_encoding.ipynb",
    3: "03_circuit_design.ipynb",
    4: "04_classical_training.ipynb",
    5: "05_transpilation.ipynb",
    6: "06_hardware_retuning.ipynb",
    7: "07_run_on_backend.ipynb",
    8: "08_classical_postprocessing.ipynb",
    9: "09_var_fidelity_check.ipynb",
}

STAGE_NAMES = {
    0: "Overview", 1: "Classical GCI model", 2: "Quantum encoding", 3: "Circuit design",
    4: "Classical training", 5: "Transpilation", 6: "Hardware retuning (6A vs 6B)",
    7: "Execution (noise-emulated backend)", 8: "Classical post-processing",
    9: "VaR & fidelity check",
}


def run_notebook(path, timeout=3600):
    # make the "python3" kernel resolve to THIS interpreter (the .venv one)
    os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")
    import nbformat
    from nbclient import NotebookClient
    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(nb, timeout=timeout, kernel_name="python3",
                            resources={"metadata": {"path": ROOT}})
    client.execute()
    nbformat.write(nb, path)


def run_script(stage):
    matches = glob.glob(os.path.join(ROOT, "scripts", f"run_stage{stage:02d}_*.py"))
    if not matches:
        print(f"   (no script for stage {stage} -- skipped)")
        return
    sys.path.insert(0, ROOT)
    runpy.run_path(matches[0], run_name="__main__")


def run_all(start=0, end=9, mode="notebooks"):
    os.chdir(ROOT)
    if mode == "scripts":
        start = max(start, 1)
    t_all = time.time()
    print("=" * 72)
    print(" Quantum Circuit-Based Adaptation for Credit Risk Analysis -- full pipeline")
    print(f" mode = {mode}, stages {start}..{end}")
    print("=" * 72)
    for stage in range(start, end + 1):
        t0 = time.time()
        print(f"\n>>> Stage {stage}: {STAGE_NAMES[stage]}")
        if mode == "notebooks":
            run_notebook(os.path.join(ROOT, NOTEBOOKS[stage]))
            print(f"    executed {NOTEBOOKS[stage]} (outputs saved in the notebook)")
        else:
            run_script(stage)
        print(f"    done in {time.time() - t0:.1f} s")
    print("\n" + "=" * 72)
    print(f" Pipeline finished in {time.time() - t_all:.1f} s")
    report = os.path.join(ROOT, "results", "FINAL_REPORT.md")
    if end == 9 and os.path.exists(report):
        print(f" Final report: {report}")
    print("=" * 72)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=int, default=0, help="first stage (0-9)")
    ap.add_argument("--to", dest="end", type=int, default=9, help="last stage (0-9)")
    ap.add_argument("--mode", choices=["notebooks", "scripts"], default="notebooks")
    a = ap.parse_args()
    run_all(a.start, a.end, a.mode)


if __name__ == "__main__":
    main()
