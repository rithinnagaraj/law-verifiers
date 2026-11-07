#!/usr/bin/env bash
# Chain 3: planted variants (new families, validity 0.3) -> matching rule ->
# frozen search (witness-only and pool targets) -> canary bugs -> smoke
# search -> E0.1 rerun. Run through vm_run.sh:
#   bash scripts/vm_run.sh chain3 bash scripts/chain_phase2c.sh
set -uo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
f() { grep -v -E "Warning|share = where"; }
echo "== $(date -u) commit $(git rev-parse --short HEAD) results=$TAXRED_RESULTS"
echo "== tests $(date -u +%T)"; python -m pytest -q tests/test_engines.py tests/test_search.py tests/test_llm.py tests/test_horizon.py 2>&1 | tail -2
echo "== E2.1 $(date -u +%T)"; python experiments/e2_1_planted.py --workers 6 2>&1 | f | head -24
echo "== E0.7 $(date -u +%T)"; python experiments/e0_7_matching.py --workers 6 2>&1 | f | head -20
echo "== E2.3 witness $(date -u +%T)"; python experiments/e2_3_frozen.py --budget 200 --seeds 3 --workers 6 2>&1 | f | head -12
echo "== E2.3 pool $(date -u +%T)"; python experiments/e2_3_frozen.py --budget 1000 --seeds 3 --pool 40 --workers 6 2>&1 | f | head -30
echo "== E2.6 $(date -u +%T)"; python experiments/e2_6_canaries.py --budget 400 --seeds 2 --pool 40 --workers 6 2>&1 | f | head -40
echo "== E1.4 $(date -u +%T)"; python experiments/e1_4_search_smoke.py --n 120 --budget 100 --workers 6 2>&1 | f | head -40
echo "== E0.1 $(date -u +%T)"; python experiments/e0_1_agreement.py --n 5000 --workers 6 2>&1 | f | tail -5
echo "== DONE $(date -u +%T)"
