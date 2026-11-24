"""A6. Matching re-validation on the A5 families.

For each passing family and magnitude, proposals evaluated under the
family's law L:
  witness                    the family's witness
  other households           the witness moves on archetypes of the same structure
  extra move                 witness + one random valid move (5 draws)
  reordered                  witness moves in reverse order
  split amounts              each amount/fraction split into two moves
  cross-family               the witnesses of the other families (their households)
Ground truth: the mutation creates >= $50 of a positive gain
(gain under L - gain under current law >= 50, and gain under L > 0).
Predicted match at R: labelled candidate, attributable >= $50 and >= R of the gain.
Output: precision and recall for R in {0.05, 0.1, 0.2, ..., 0.9}.

Usage: python experiments/a6_matching.py [--summary]
"""

from __future__ import annotations

import argparse
import copy
import json

import numpy as np

from taxgap.archetypes import witness_archetypes
from taxgap.config import results_dir
from taxgap.law import CURRENT_LAW
from taxgap.moves import MoveError, years_of
from taxgap.mutations.generate import candidates
from taxgap.runner import read_rows, run
from taxgap.search.sample import random_move
from taxgap.verifier import Config, Verifier

RS = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def _valid(hh, mv) -> bool:
    try:
        for f in hh.futures or [None]:
            years_of(hh, mv, f)
        return True
    except (MoveError, KeyError, ValueError):
        return False


def _split(mv: list) -> list:
    out = []
    for m in mv:
        if m["op"] == "gift_asset":
            f = float(m.get("fraction", 1.0))
            a = dict(m, fraction=f / 2)
            b = dict(m, fraction=(f / 2) / (1 - f / 2) if f < 2 else 1.0)
            b["asset"] = m["asset"]
            out += [a, b]
        elif m["op"] in ("shift_income", "donate_cash", "contribute_retirement", "roth_convert") and "amount" in m:
            out += [dict(m, amount=m["amount"] / 2), dict(m, amount=m["amount"] / 2)]
        else:
            out.append(m)
    return out


def proposals_for(w: dict, others: list, pool: list, rng) -> list:
    hh = pool[w["household"]]
    mv = w["moves"]
    out = [("witness", hh, mv)]
    stem = hh.id.rsplit("_", 1)[0]
    for a in pool:
        if a.id != hh.id and a.id.rsplit("_", 1)[0] == stem and _valid(a, mv):
            out.append(("other_household", a, mv))
    for _ in range(5):
        m = random_move(hh, rng, hh.year)
        if m and _valid(hh, mv + [m]):
            out.append(("extra_move", hh, mv + [m]))
    if len(mv) > 1 and _valid(hh, mv[::-1]):
        out.append(("reordered", hh, mv[::-1]))
    sp = _split(mv)
    if sp != mv and _valid(hh, sp):
        out.append(("split_amounts", hh, sp))
    for ow in others:
        out.append(("cross_family", pool[ow["household"]], ow["moves"]))
    return out


def job(j: dict) -> list:
    pool = witness_archetypes()
    fam = {f.id: f for f in candidates(0)}[j["family"]]
    law = fam.laws(j["m"])["L"]
    rng = np.random.default_rng([len(j["family"]), int(j["m"] * 10)])
    props = proposals_for(j["witness"], j["others"], pool, rng)
    vL = Verifier(law, Config()).evaluate([(h, m) for _, h, m in props])
    v0 = Verifier(CURRENT_LAW, Config(attribute=False, recheck=False)).evaluate([(h, m) for _, h, m in props])
    return [{"family": fam.id, "m": j["m"], "kind": k, "hh": h.id, "moves": m, "label": a.label, "gain": a.gain, "gain0": b.gain} for (k, h, m), a, b in zip(props, vL, v0)]


def summarize(d) -> None:
    rows = read_rows(d / "proposals.jsonl")
    truth = np.array([(r["gain"] > 0) and (r["gain"] - r["gain0"] >= 50) for r in rows])
    lines = ["# A6: matching re-validation", "", f"Proposals: {len(rows)}; ground-truth positives: {int(truth.sum())}.", "", "| R | precision | recall | matches |", "|---|---|---|---|"]
    out = {}
    for R in RS:
        pred = np.array([r["label"] == "candidate" and r["gain"] - r["gain0"] >= 50 and r["gain"] - r["gain0"] >= R * r["gain"] for r in rows])
        tp = int((pred & truth).sum())
        p = tp / pred.sum() if pred.sum() else float("nan")
        rc = tp / truth.sum() if truth.sum() else float("nan")
        out[R] = (p, rc)
        lines.append(f"| {R:g} | {p:.3f} | {rc:.3f} | {int(pred.sum())} |")
    p, rc = out[0.1]
    lines.append("")
    lines.append(f"Check: R = 0.1 keeps precision >= 0.95 and recall >= 0.95: **{'yes' if p >= 0.95 and rc >= 0.95 else 'no'}**.")
    lines.append("")
    lines.append("| kind | n | positives | recall at R = 0.1 |")
    lines.append("|---|---|---|---|")
    for kind in sorted({r["kind"] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r["kind"] == kind]
        t = truth[idx]
        pr = np.array([rows[i]["label"] == "candidate" and rows[i]["gain"] - rows[i]["gain0"] >= max(50, 0.1 * rows[i]["gain"]) for i in idx])
        rec = (pr & t).sum() / t.sum() if t.sum() else float("nan")
        lines.append(f"| {kind} | {len(idx)} | {int(t.sum())} | {rec:.3f} |")
    (d / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    d = results_dir("a6")
    if not a.summary:
        a5 = read_rows(results_dir("a5") / "a5a.jsonl") + read_rows(results_dir("a5") / "a5b.jsonl")
        passed = [r for r in a5 if r["passed"]]
        ws = [(r["family"]["id"], g["magnitude"], g["witness"]) for r in passed for g in r["gates"]]
        jobs = []
        for fid, m, w in ws:
            others = [w2 for f2, m2, w2 in ws if f2 != fid and m2 == m]
            jobs.append({"id": f"{fid}@{m:g}", "family": fid, "m": m, "witness": w, "others": others})
        run(jobs, job, d / "proposals.jsonl", workers=a.workers)
    summarize(d)


if __name__ == "__main__":
    main()
