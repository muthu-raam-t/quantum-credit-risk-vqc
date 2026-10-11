"""
run_comparison.py -- one command for the base paper vs proposed work comparison.

    python run_comparison.py              # run both pipelines once
    python run_comparison.py --repeats 3  # run both 3 times and show the average

1. runs base_paper/base_paper.ipynb       (timed, outputs saved in the notebook)
2. runs proposed_work/proposed_work.ipynb (timed, outputs saved in the notebook)
3. prints the total time of each pipeline (and the average over repeats)
4. rebuilds comparison.ipynb and the charts in comparison_figures/
"""

import argparse
import json
import os
import sys

import nbformat
from nbclient import NotebookClient

ROOT = os.path.dirname(os.path.abspath(__file__))
PIPELINES = [("base_paper", "BASE PAPER"), ("proposed_work", "PROPOSED WORK")]


def run_notebook(path, workdir):
    os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "")
    nb = nbformat.read(path, as_version=4)
    NotebookClient(nb, timeout=3600, kernel_name="python3",
                   resources={"metadata": {"path": workdir}}).execute()
    nbformat.write(nb, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=1, help="how many times to run both pipelines")
    args = ap.parse_args()

    os.chdir(ROOT)
    totals = {label: [] for _, label in PIPELINES}
    for r in range(1, args.repeats + 1):
        for folder, label in PIPELINES:
            print(f"Run {r}/{args.repeats}: {folder} ...", flush=True)
            run_notebook(os.path.join(ROOT, folder, f"{folder}.ipynb"), os.path.join(ROOT, folder))
            with open(os.path.join(ROOT, folder, "timing.json")) as f:
                totals[label].append(json.load(f)["total_seconds"])

    print("\n" + "=" * 60)
    for label, values in totals.items():
        runs = "  ".join(f"{v:6.2f}" for v in values)
        avg = sum(values) / len(values)
        print(f"{label:14s} total time : {avg:6.2f} s" + (f"   (runs: {runs})" if len(values) > 1 else ""))
    print("=" * 60)

    print("\nUpdating comparison.ipynb and comparison_figures/ ...", flush=True)
    run_notebook(os.path.join(ROOT, "comparison.ipynb"), ROOT)
    print("Done. Open comparison.ipynb to see the tables and charts.")


if __name__ == "__main__":
    main()
