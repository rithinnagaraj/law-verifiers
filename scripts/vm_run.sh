#!/usr/bin/env bash
# Run one experiment command on the VM inside a memory-capped scope, in the
# background, logging to results/logs/<name>_<stamp>.log. If the command
# exceeds MEM_MAX the kernel kills it instead of freezing the machine.
#
#   bash scripts/vm_run.sh e2_1 python experiments/e2_1_planted.py --workers 6
#   MEM_MAX=60G bash scripts/vm_run.sh ...
set -uo pipefail
cd "$(dirname "$0")/.."
name="$1"; shift
export PATH="$HOME/.local/bin:$PATH"
# shellcheck disable=SC1091
. .venv/bin/activate
export TAXRED_PE_CACHE="${TAXRED_PE_CACHE:-8}"
mkdir -p results/logs
log="results/logs/${name}_$(date -u +%Y%m%dT%H%M%SZ).log"
MEM_MAX="${MEM_MAX:-68G}"
wrap=()
if command -v systemd-run >/dev/null && systemd-run --user --scope -q true 2>/dev/null; then
  wrap=(systemd-run --user --scope -q -p "MemoryMax=$MEM_MAX" -p MemorySwapMax=0)
fi
setsid nohup "${wrap[@]}" "$@" > "$log" 2>&1 < /dev/null &
echo "$log"
