#!/usr/bin/env bash
# One-time (idempotent) setup on the experiment VM: clone or update the repo,
# create a Python 3.12 environment with uv, install the package, run tests.
#
#   bash setup_vm.sh                       # default branch below
#   BRANCH=some-branch bash setup_vm.sh
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/rithinnagaraj/law-verifiers.git}"
BRANCH="${BRANCH:-docs/experiment-plan}"
DIR="${DIR:-$HOME/law-verifiers}"

if ! command -v git >/dev/null; then sudo apt-get update -y && sudo apt-get install -y git; fi
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch origin "$BRANCH"
  git -C "$DIR" checkout "$BRANCH"
  git -C "$DIR" pull --ff-only origin "$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$DIR"
fi

cd "$DIR"
[ -d .venv ] || uv venv --python 3.12 .venv
# shellcheck disable=SC1091
. .venv/bin/activate
uv pip install -e ".[dev]"
python -m pytest -q
echo "Setup OK: $(git rev-parse --short HEAD) on $BRANCH"
