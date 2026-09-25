"""
Stage 6 runner: Hardware / noise-model retuning (6A grid sweep vs 6B automated calibration).

Headless version of 06_hardware_retuning.ipynb -- runs exactly the same code from
src/stages.py (the notebook adds the explanations and figures).
Reads the previous stage's JSON from results/ and writes its own.

Usage:
    python scripts/run_stage06_hardware_retuning.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.stages import run_stage06


if __name__ == "__main__":
    run_stage06()
