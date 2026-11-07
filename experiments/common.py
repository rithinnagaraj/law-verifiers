"""Shared helpers for experiment scripts."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def out_dir(name: str) -> Path:
    d = ROOT / "results" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_metadata() -> dict:
    def git(*a):
        try:
            return subprocess.check_output(["git", *a], cwd=ROOT, text=True).strip()
        except Exception:
            return None

    versions = {}
    for mod in ("policyengine_us", "taxcalc", "numpy", "pandas"):
        try:
            from importlib.metadata import version

            versions[mod] = version(mod.replace("_", "-"))
        except Exception:
            versions[mod] = None
    return {
        "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "host": platform.node(),
        "python": sys.version.split()[0],
        "cpus": os.cpu_count(),
        "versions": versions,
        "argv": sys.argv,
    }


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=float))


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def pe_worker_gb() -> float:
    """Peak memory of one worker: base PolicyEngine system (~1.5 GB) plus
    ~1.15 GB per cached reformed system (TAXRED_PE_CACHE); measured on the VM
    (10.7 GB RSS with a cache of 8)."""
    return 1.5 + 1.15 * int(os.environ.get("TAXRED_PE_CACHE", "6")) + 0.5


def safe_workers(requested: int) -> int:
    """Cap the worker count by available memory (MemAvailable, Linux) so that
    parallel PolicyEngine workers cannot push the machine into thrashing.
    Two experiments started at once on the VM froze it (2026-11-07)."""
    try:
        with open("/proc/meminfo") as f:
            avail_kb = next(int(l.split()[1]) for l in f if l.startswith("MemAvailable"))
    except (OSError, StopIteration):
        return requested
    avail_gb = avail_kb / 1048576
    # Inside a memory-capped scope (scripts/vm_run.sh) the cap is the limit.
    if os.environ.get("TAXRED_MEM_GB"):
        avail_gb = min(avail_gb, float(os.environ["TAXRED_MEM_GB"]))
    cap = max(1, int((avail_gb * 0.85) // pe_worker_gb()))
    if cap < requested:
        print(f"[safe_workers] {requested} workers requested, {cap} fit in available memory", file=sys.stderr)
    return min(requested, cap)
