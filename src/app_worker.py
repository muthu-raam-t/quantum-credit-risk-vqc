"""
app_worker.py -- runs one analysis in a fresh Python process for the app.

    echo '{"p0": 0.25, ...}' | python -m src.app_worker

Reads the analyse() arguments as JSON on stdin and writes the result as JSON on stdout.
The app (app.py) calls this instead of running Qiskit inside Streamlit's own process,
which keeps the simulation isolated from Streamlit's threads and file watcher.
"""

import json
import sys

from .app_core import analyse


def main():
    kwargs = json.load(sys.stdin)
    result = analyse(**kwargs)
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
