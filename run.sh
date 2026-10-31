#!/usr/bin/env bash
# One-step launcher for macOS / Linux: creates a virtual environment, installs requirements, starts the console.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python run_gui.py "$@"
