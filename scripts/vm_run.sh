#!/usr/bin/env bash
# Run one experiment on the VM in a memory-capped systemd user scope that
# survives logout (lingering is enabled). One experiment at a time: the
# script refuses to start if another taxgap scope is running.
# Usage: bash scripts/vm_run.sh <name> <command...>
# Log: ~/taxgap-results/logs/<name>.log
set -euo pipefail
NAME="$1"; shift
MEM="${TAXGAP_MEM_GB:-230}"
cd "$HOME/taxgap"
if systemctl --user list-units --type=scope --state=running --no-legend | grep -q "taxgap-"; then
  echo "another taxgap experiment is running:"; systemctl --user list-units --type=scope --no-legend | grep taxgap-
  exit 1
fi
mkdir -p "$HOME/taxgap-results/logs"
LOG="$HOME/taxgap-results/logs/$NAME.log"
export TAXGAP_MEM_GB="$MEM" PYTHONUNBUFFERED=1
systemd-run --user --scope --unit="taxgap-$NAME-$(date +%s)" -p MemoryMax="${MEM}G" -p MemorySwapMax=0 \
  nohup "$@" > "$LOG" 2>&1 &
echo "started $NAME; log $LOG"
