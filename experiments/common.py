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
