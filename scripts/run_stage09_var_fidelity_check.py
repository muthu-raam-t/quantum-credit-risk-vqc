"""
Stage 9 runner: VaR and fidelity check, ACCEPT / RE-CALIBRATE loop.

Headless version of 09_var_fidelity_check.ipynb -- runs exactly the same code from
src/stages.py (the notebook adds the explanations and figures).
Reads the previous stage's JSON from results/ and writes its own.

Usage:
    python scripts/run_stage09_var_fidelity_check.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.stages import run_stage09


if __name__ == "__main__":
    run_stage09()
