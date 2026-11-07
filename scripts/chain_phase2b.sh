#!/usr/bin/env bash
# Rerun after the planted-variant fixes: E2.1 -> E0.7 -> E2.3, then E1.4 and
# E0.1 (sales-tax fix). Run through vm_run.sh:
#   bash scripts/vm_run.sh chain2b bash scripts/chain_phase2b.sh
set -uo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
f() { grep -v -E "Warning|share = where"; }
echo "== $(date -u) commit $(git rev-parse --short HEAD)"
echo "== tests $(date -u +%T)"; python -m pytest -q -rxX 2>&1 | tail -4
echo "== E2.1 $(date -u +%T)"; python experiments/e2_1_planted.py --workers 6 2>&1 | f | head -25
echo "== E0.7 $(date -u +%T)"; python experiments/e0_7_matching.py --workers 6 2>&1 | f | head -22
echo "== E2.3 $(date -u +%T)"; python experiments/e2_3_frozen.py --budget 200 --seeds 3 --workers 6 2>&1 | f | head -30
echo "== E1.4 $(date -u +%T)"; python experiments/e1_4_search_smoke.py --n 120 --budget 100 --workers 6 2>&1 | f | head -40
echo "== E0.1 $(date -u +%T)"; python experiments/e0_1_agreement.py --n 5000 --workers 6 2>&1 | f | tail -5
echo "== DONE $(date -u +%T)"
