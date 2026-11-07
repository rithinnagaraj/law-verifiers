#!/usr/bin/env bash
# Run the Phase 0 / Phase 1-pilot experiments on the VM and commit results.
#
#   bash scripts/run_phase0.sh              # full scale
#   N=500 bash scripts/run_phase0.sh        # smaller E0.1
#   PUSH=1 bash scripts/run_phase0.sh       # also push results to GitHub
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
# shellcheck disable=SC1091
. .venv/bin/activate
WORKERS="${WORKERS:-$(nproc)}"
N="${N:-5000}"
mkdir -p results/phase0 results/logs
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="results/logs/phase0_${STAMP}.log"

{
  echo "== commit $(git rev-parse HEAD)  workers=$WORKERS  N=$N"
  echo "== E0.2 known-answer tests"
  python -m pytest -q -rxX 2>&1 | tee results/phase0/e0_2_pytest.txt
  echo "== E0.3 throughput"
  python experiments/e0_3_throughput.py --sizes 1 10 50 200 500 1000 --repeats 2
  echo "== E0.1 calculator agreement"
  python experiments/e0_1_agreement.py --n "$N" --workers "$WORKERS"
  echo "== E1.1 pilot: kiddie tax dose-response"
  python experiments/e1_kiddie_pilot.py --workers "$WORKERS"
} 2>&1 | grep -v -E "RuntimeWarning|share = where" | tee "$LOG"

git add results
git -c user.name="law-verifiers VM" -c user.email="vm@law-verifiers.local" \
  commit -m "Phase 0 results from $(hostname) at $STAMP" || true
if [ "${PUSH:-0}" = "1" ]; then
  git push origin "$(git rev-parse --abbrev-ref HEAD)"
fi
echo "Done. Log: $LOG"
