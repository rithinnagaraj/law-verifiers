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
export TAXRED_PE_CACHE="${TAXRED_PE_CACHE:-6}"
mkdir -p results/logs
log="results/logs/${name}_$(date -u +%Y%m%dT%H%M%SZ).log"
MEM_MAX="${MEM_MAX:-68G}"
export TAXRED_MEM_GB="${MEM_MAX%G}"
# A user scope dies with the user manager when the last ssh session closes
# unless lingering is on (it killed a chain on 2026-11-07).
if command -v loginctl >/dev/null && [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]; then
  sudo -n loginctl enable-linger "$USER" 2>/dev/null || echo "warning: lingering is off; run with nohup only" >&2
fi
wrap=()
if command -v systemd-run >/dev/null && systemd-run --user --scope -q true 2>/dev/null; then
  wrap=(systemd-run --user --scope -q -p "MemoryMax=$MEM_MAX" -p MemorySwapMax=0)
fi
setsid nohup "${wrap[@]}" "$@" > "$log" 2>&1 < /dev/null &
echo "$log"
