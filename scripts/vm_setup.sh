#!/usr/bin/env bash
# One-time VM setup: clone the v2 branch and build its environment.
# Usage (on the VM): bash vm_setup.sh
set -euo pipefail
REPO=https://github.com/rithinnagaraj/law-verifiers.git
DIR="$HOME/taxgap"
UV="$HOME/.local/bin/uv"
if [ ! -d "$DIR/.git" ]; then
  git clone --branch v2 --single-branch "$REPO" "$DIR"
fi
cd "$DIR"
git pull --ff-only
"$UV" venv --python 3.12 .venv
"$UV" pip install --python .venv/bin/python -e ".[dev]"
mkdir -p "$HOME/taxgap-results" "$HOME/data/taxgap-cache"
.venv/bin/python -c "import policyengine_us, taxcalc; print('ok', taxcalc.__version__)"
