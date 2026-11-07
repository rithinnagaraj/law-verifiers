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


def results_root() -> Path:
    """Where experiments write. On the VM, scripts/vm_run.sh points
    TAXRED_RESULTS outside the checkout so `git pull` never meets untracked
    result files; summaries are copied into results/ and committed locally."""
    return Path(os.environ.get("TAXRED_RESULTS", ROOT / "results"))


def out_dir(name: str) -> Path:
    d = results_root() / name
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


def run_jobs(fn, jobs, workers: int, checkpoint: Path | None = None, max_tasks_per_child: int = 2, retries: int = 3):
    """Run fn over jobs in a process pool, robustly.

    - Each finished job's result is appended to `checkpoint` (JSONL) and
      skipped on a rerun, so a crash loses at most the jobs in flight.
    - Jobs run in waves of `workers x max_tasks_per_child`, each wave in a
      fresh pool, which releases the PolicyEngine systems and simulations
      the workers hold. (ProcessPoolExecutor's own max_tasks_per_child
      deadlocked on the VM: workers gone, parent waiting on a futex.)
    - If a worker dies (e.g. the memory-capped scope's OOM killer), the pool
      is rebuilt with half the workers and the remaining jobs are retried.
    Returns results in job order (jobs that kept failing are left out).
    """
    import json as _json
    from concurrent.futures.process import BrokenProcessPool

    key = lambda j: _json.dumps(j, sort_keys=True, default=str)
    done: dict = {}
    if checkpoint is not None and checkpoint.exists():
        for line in checkpoint.read_text().splitlines():
            if line.strip():
                rec = _json.loads(line)
                done[rec["key"]] = rec["result"]
        print(f"[run_jobs] resuming: {len(done)} of {len(jobs)} jobs done", file=sys.stderr)
    w = safe_workers(workers)
    for attempt in range(retries + 1):
        pending = [j for j in jobs if key(j) not in done]
        if not pending:
            break
        try:
            wave = max(1, w * max_tasks_per_child)
            for start in range(0, len(pending), wave):
                _run_wave(fn, pending[start : start + wave], min(w, len(pending)), key, done, checkpoint)
        except BrokenProcessPool:
            w = max(1, w // 2)
            print(f"[run_jobs] a worker died (attempt {attempt + 1}); retrying with {w} workers", file=sys.stderr)
    return [done[key(j)] for j in jobs if key(j) in done]


def _run_wave(fn, jobs, workers, key, done, checkpoint):
    """One fresh pool for one wave of jobs; raises BrokenProcessPool if a
    worker dies (run_jobs then retries the rest with fewer workers)."""
    import json as _json
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from concurrent.futures.process import BrokenProcessPool

    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(fn, j): j for j in jobs}
        for f in as_completed(futs):
            j = futs[f]
            try:
                r = f.result()
            except BrokenProcessPool:
                raise
            except Exception as e:  # a bug in one job: report, keep going
                print(f"[run_jobs] job failed: {key(j)[:120]}: {e!r}", file=sys.stderr)
                continue
            done[key(j)] = r
            if checkpoint is not None:
                with open(checkpoint, "a") as fh:
                    fh.write(_json.dumps({"key": key(j), "result": r}, default=float) + "\n")
