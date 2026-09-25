"""
Stage 8 runner: Classical post-processing (bitstrings -> loss PDF -> CDF).

Headless version of 08_classical_postprocessing.ipynb -- runs exactly the same code from
src/stages.py (the notebook adds the explanations and figures).
Reads the previous stage's JSON from results/ and writes its own.

Usage:
    python scripts/run_stage08_postprocessing.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.stages import run_stage08


if __name__ == "__main__":
    run_stage08()
