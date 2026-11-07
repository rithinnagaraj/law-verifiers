#!/usr/bin/env bash
# Chain 5 (after the F12 fix): rerun everything that batches several proposals
# per household: E0.7 -> E2.3 witness-only -> E2.6 canaries -> E2.3 pool ->
# E0.1 2024-2026 -> E1.4. Reuses the E2.1 manifest. Run through vm_run.sh:
#   bash scripts/vm_run.sh chain5 bash scripts/chain_phase2e.sh
set -uo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
f() { grep -v -E "Warning|share = where"; }
echo "== $(date -u) commit $(git rev-parse --short HEAD) results=$TAXRED_RESULTS"
echo "== E0.7 $(date -u +%T)"; python experiments/e0_7_matching.py --workers 6 2>&1 | f | head -20
echo "== E2.3 witness $(date -u +%T)"; python experiments/e2_3_frozen.py --budget 200 --seeds 3 --workers 6 2>&1 | f | head -12
echo "== E2.6 $(date -u +%T)"; python experiments/e2_6_canaries.py --budget 400 --seeds 2 --pool 40 --batch 50 --workers 6 2>&1 | f | head -45
echo "== E2.3 pool $(date -u +%T)"; python experiments/e2_3_frozen.py --budget 1000 --seeds 2 --pool 40 --batch 50 --workers 6 2>&1 | f | head -40
for y in 2025 2026; do echo "== E0.1 $y $(date -u +%T)"; python experiments/e0_1_agreement.py --n 2000 --year $y --out phase0/e0_1_$y --workers 6 2>&1 | f | tail -3; done
echo "== E0.1 2024 $(date -u +%T)"; python experiments/e0_1_agreement.py --n 5000 --workers 6 2>&1 | f | tail -3
echo "== E1.4 $(date -u +%T)"; python experiments/e1_4_search_smoke.py --n 120 --budget 100 --workers 6 2>&1 | f | head -40
echo "== DONE $(date -u +%T)"
