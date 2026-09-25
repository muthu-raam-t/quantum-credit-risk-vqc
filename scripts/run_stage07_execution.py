"""
Stage 7 runner: Execution on the noise-emulated backend + readout mitigation + ZNE.

Headless version of 07_run_on_backend.ipynb -- runs exactly the same code from
src/stages.py (the notebook adds the explanations and figures).
Reads the previous stage's JSON from results/ and writes its own.

Usage:
    python scripts/run_stage07_execution.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.stages import run_stage07


if __name__ == "__main__":
    run_stage07()
