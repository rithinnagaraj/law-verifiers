"""Checkpointed parallel jobs.

`run(jobs, fn, out)` runs fn(job) -> list of rows for each job dict (each
with a unique "id") in a process pool and appends {"id", "rows"} lines to
the JSONL file `out`; jobs already in `out` are skipped, so a killed run
resumes. Workers are forked from a parent that has already built the
PolicyEngine base system (shared copy-on-write). A fresh pool per wave
(v1: max_tasks_per_child deadlocked); a wave that loses a worker is retried
with half the workers.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Callable

from .config import MEM_GB, WORKER_GB


def default_workers() -> int:
    cpu = os.cpu_count() or 2
    n = max(1, cpu - 2)
    if MEM_GB:
        n = min(n, max(1, int((MEM_GB - 8) / WORKER_GB)))
    return n


def done_ids(out: Path) -> set:
    if not out.exists():
        return set()
    ids = set()
    for line in out.read_text().splitlines():
        try:
            ids.add(json.loads(line)["id"])
        except (json.JSONDecodeError, KeyError):
            pass
    return ids


def read_rows(out: Path) -> list:
    rows = []
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                rows += json.loads(line)["rows"]
            except (json.JSONDecodeError, KeyError):
                pass
    return rows


def _call(fn, job):
    try:
        return job["id"], fn(job), None
    except Exception:
        return job["id"], None, traceback.format_exc()


def _warm():
    from .params import pe_system

    pe_system()


def run(jobs: list[dict], fn: Callable, out: Path, workers: int | None = None, wave: int | None = None, log=print) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    have = done_ids(out)
    todo = [j for j in jobs if j["id"] not in have]
    workers = workers or default_workers()
    wave = wave or workers * 4
    log(f"[run] {len(todo)} of {len(jobs)} jobs to do, {workers} workers -> {out}")
    if not todo:
        return
    _warm()
    ctx = mp.get_context("fork")
    t0, n_done = time.time(), 0
    i = 0
    while i < len(todo):
        batch = todo[i : i + wave]
        try:
            with ProcessPoolExecutor(max_workers=min(workers, len(batch)), mp_context=ctx) as ex:
                futs = [ex.submit(_call, fn, j) for j in batch]
                with out.open("a") as f:
                    for fut in as_completed(futs):
                        jid, rows, err = fut.result()
                        if err:
                            log(f"[run] job {jid} failed:\n{err}")
                            continue
                        f.write(json.dumps({"id": jid, "rows": rows}, default=float) + "\n")
                        f.flush()
                        n_done += 1
        except BrokenProcessPool:
            workers = max(1, workers // 2)
            log(f"[run] a worker died; retrying the wave with {workers} workers")
            have = done_ids(out)
            todo = todo[:i] + [j for j in todo[i:] if j["id"] not in have]
            continue
        i += wave
        el = time.time() - t0
        log(f"[run] {n_done}/{len(todo)} jobs, {el / 60:.1f} min, {el / max(n_done, 1):.1f} s/job")
