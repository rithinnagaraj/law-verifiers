#!/usr/bin/env bash
# Phase 1 verifier validation on the VM. Results stay uncommitted on the VM;
# copy them back (scp) and commit from the development checkout.
#
#   bash scripts/run_phase1.sh                 # tests + E0.6/E1.2 + E1.1 + E1.4
#   STEPS="e11 e14" bash scripts/run_phase1.sh # selected steps
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
# shellcheck disable=SC1091
. .venv/bin/activate
export TAXRED_PE_CACHE="${TAXRED_PE_CACHE:-16}"
W="${WORKERS:-6}"
STEPS="${STEPS:-tests e06 e11 e14}"
mkdir -p results/logs
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="results/logs/phase1_${STAMP}.log"
{
  echo "== commit $(git rev-parse --short HEAD) workers=$W steps=$STEPS"
  for s in $STEPS; do
    case $s in
      tests) echo "== tests"; python -m pytest -q -rxX 2>&1 | tail -20 ;;
      e06) echo "== E0.6 / E1.2"; python experiments/e0_6_legit.py --workers "$W" ;;
      e11) echo "== E1.1 closures"; python experiments/e1_closures.py --workers "$W" ;;
      e14) echo "== E1.4 search smoke"; python experiments/e1_4_search_smoke.py --n "${N_SEARCH:-120}" --budget "${BUDGET:-100}" --workers "$W" ;;
    esac
  done
  echo "== DONE"
} 2>&1 | grep -v -E "RuntimeWarning|share = where" > "$LOG"
echo "log: $LOG"
