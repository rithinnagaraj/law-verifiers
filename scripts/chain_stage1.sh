#!/usr/bin/env bash
# Chain 6: everything under the federal-only gain scope, then stage 1 search.
#   bash scripts/vm_run.sh chain6 bash scripts/chain_stage1.sh
set -uo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
f() { grep -v -E "Warning|share = where"; }
echo "== $(date -u) commit $(git rev-parse --short HEAD) results=$TAXRED_RESULTS (gain scope: federal)"
echo "== E1.1 $(date -u +%T)"; python experiments/e1_closures.py --workers 6 2>&1 | f | head -22
echo "== E0.6 $(date -u +%T)"; python experiments/e0_6_legit.py --workers 6 2>&1 | f | head -12
echo "== E2.1 $(date -u +%T)"; python experiments/e2_1_planted.py --workers 6 2>&1 | f | head -26
echo "== E0.7 $(date -u +%T)"; python experiments/e0_7_matching.py --workers 6 2>&1 | f | head -18
echo "== E2.3 stage1 $(date -u +%T)"; python experiments/e2_3_frozen.py --stage 1 --pool 40 --budget 400 --seeds 2 --batch 50 --workers 6 2>&1 | f | head -40
echo "== DONE $(date -u +%T)"
