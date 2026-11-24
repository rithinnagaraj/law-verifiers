"""A7. Beam-enumeration baseline validation.

For each val family (A5 split) and magnitude: the beam proposer gets the
witness household alone and a budget equal to that household's grid size up
to the witness depth k (all grid sequences of 1..k moves). It "finds the
witness" if it reaches a match for the family's law L on that household:
labelled candidate, attributable gain >= $50 and >= R of its gain (the
same test as the A5 gate). The exact witness cannot be reproduced, because
its amounts and dates are continuous while the beam enumerates the
discretized grid; the criterion is therefore a match of the family's
mechanism on the witness household (operationalization fixed before A7 ran,
see DECISIONS.md).

Output: per family and magnitude: grid size, calls to the first match,
matches found, depth of the first match. Check: all val families found.

Usage: python experiments/a7_beam.py [--summary] [--families id,id,...]
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from taxgap.archetypes import witness_archetypes
from taxgap.config import results_dir
from taxgap.grid import sequences
from taxgap.mutations.family import _matches
from taxgap.mutations.generate import candidates
from taxgap.runner import read_rows, run
from taxgap.search.beam import BeamProposer
from taxgap.verifier import Config, Verifier

BATCH = 400


def job(j: dict) -> list:
    fam = {f.id: f for f in candidates(0)}[j["family"]]
    law = fam.laws(j["m"])["L"]
    hh = witness_archetypes()[j["household"]]
    k = j["k"]
    grid = sum(len(list(sequences(hh, d))) for d in range(1, k + 1))
    beam = BeamProposer([hh], np.random.default_rng([j["k"], int(j["m"] * 10)]), max_depth=k)
    v = Verifier(law, Config())
    calls, first, first_depth, n_match = 0, None, None, 0
    while calls < grid:
        props = beam.propose(min(BATCH, grid - calls))
        if not props:
            break
        hits = _matches([(hh, s) for _, s in props], law, v)
        if hits and first is None:
            idx = [s for _, s in props].index(hits[0][0][1])
            first, first_depth = calls + idx + 1, len(hits[0][0][1])
        n_match += len(hits)
        calls += len(props)
        if first is not None and j.get("stop_at_first", True):
            break
    return [{"family": fam.id, "m": j["m"], "household": hh.id, "k": k, "grid": grid, "calls": calls, "first_match": first, "first_depth": first_depth, "matches": n_match, "found": first is not None}]


def summarize(d) -> None:
    rows = read_rows(d / "beam.jsonl")
    lines = ["# A7: beam-enumeration baseline validation", "", "| family | m | witness household (k) | grid size | calls to first match | depth | found |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['family']} | {r['m']:g} | {r['household']} ({r['k']}) | {r['grid']} | {r['first_match'] or '-'} | {r['first_depth'] or '-'} | {'yes' if r['found'] else 'NO'} |")
    ok = bool(rows) and all(r["found"] for r in rows)
    lines += ["", f"Check: beam finds a match on every val family's witness household within its grid size: **{'yes' if ok else 'no'}**."]
    (d / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--families", default=None, help="comma-separated family ids (default: val split)")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    d = results_dir("a7")
    if not a.summary:
        a5 = results_dir("a5")
        fams = a.families.split(",") if a.families else json.load(open(a5 / "split.json"))["val"]
        rows = {r["family"]["id"]: r for r in read_rows(a5 / "a5a.jsonl") + read_rows(a5 / "a5b.jsonl")}
        jobs = []
        for fid in fams:
            for g in rows[fid]["gates"]:
                w = g["witness"]
                jobs.append({"id": f"{fid}@{g['magnitude']:g}", "family": fid, "m": g["magnitude"], "household": w["household"], "k": w["k"]})
        run(jobs, job, d / "beam.jsonl", workers=a.workers)
    summarize(d)


if __name__ == "__main__":
    main()
