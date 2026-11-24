"""Paths and machine settings, from the environment."""

from __future__ import annotations

import os
from pathlib import Path

HOME = Path.home()
DATA_DIR = Path(os.environ.get("TAXGAP_DATA", HOME / "data"))
ECPS_PATH = Path(os.environ.get("TAXGAP_ECPS", DATA_DIR / "enhanced_cps_2024.h5"))
CACHE_DIR = Path(os.environ.get("TAXGAP_CACHE", DATA_DIR / "taxgap-cache"))
RESULTS_DIR = Path(os.environ.get("TAXGAP_RESULTS", HOME / "taxgap-results"))

# Memory per verifier worker (GB), measured; used to size process pools.
WORKER_GB = float(os.environ.get("TAXGAP_WORKER_GB", "4.0"))
# Memory available to one experiment (GB): the systemd scope's cap.
MEM_GB = float(os.environ.get("TAXGAP_MEM_GB", "0")) or None

# Tax years of the horizon and the year the futures diverge.
HORIZON_START = 2024
HORIZON_YEARS = 3
FUTURES_FROM = 2025


def results_dir(*parts: str) -> Path:
    p = RESULTS_DIR.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p
