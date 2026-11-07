#!/usr/bin/env bash
# Sequential experiment chain (one PolicyEngine experiment at a time):
# tests, E2.1, E0.6/E1.2, E0.7, E1.4, E2.3. Run through vm_run.sh:
#   bash scripts/vm_run.sh chain bash scripts/chain_phase2.sh
set -uo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
# TAXRED_PE_CACHE and TAXRED_MEM_GB come from scripts/vm_run.sh
echo "== $(date -u) commit $(git rev-parse --short HEAD)"
echo "== tests"; python -m pytest -q -rxX tests/test_engines.py tests/test_llm.py 2>&1 | tail -4
echo "== E2.1 $(date -u +%T)"; python experiments/e2_1_planted.py --workers 6 2>&1 | grep -v -E "Warning|share = where" | head -40
echo "== E0.6 $(date -u +%T)"; python experiments/e0_6_legit.py --workers 6 2>&1 | grep -v -E "Warning|share = where" | head -12
echo "== E0.7 $(date -u +%T)"; python experiments/e0_7_matching.py --workers 6 2>&1 | grep -v -E "Warning|share = where" | head -30
echo "== E1.4 $(date -u +%T)"; python experiments/e1_4_search_smoke.py --n 120 --budget 100 --workers 6 2>&1 | grep -v -E "Warning|share = where" | head -30
echo "== E2.3 $(date -u +%T)"; python experiments/e2_3_frozen.py --budget 200 --seeds 3 --workers 6 2>&1 | grep -v -E "Warning|share = where" | head -40
echo "== DONE $(date -u +%T)"
