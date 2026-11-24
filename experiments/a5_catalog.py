"""A5. Interaction-mutation catalog.

Stages:
  --stage a5a   spike: the first 10 candidates (seeded order); gate G0
                (>= 3 of 10 pass) decides whether A4, A5b and A7 proceed
  --stage a5b   the next 50 candidates (--extend: 80)
  --summary     family manifest, rejection reasons, G0/G2, split

Each job gates one candidate at both magnitudes (experiment plan A5).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter

import numpy as np

from taxgap.config import results_dir
from taxgap.mutations.family import gate
from taxgap.mutations.generate import candidates
from taxgap.runner import read_rows, run

SEED = 0
SPIKE = 10


def job(j: dict) -> list:
    fam = {f.id: f for f in candidates(SEED)}[j["family"]]
    rows = []
    for m in fam.magnitudes:
        rng = np.random.default_rng([int(hashlib.sha1(fam.id.encode()).hexdigest()[:8], 16), int(m * 10)])
        rows.append(gate(fam, m, rng))
    passed = all(r["passed"] for r in rows)
    return [{"family": fam.describe(), "stage": j["stage"], "passed": passed, "gates": rows}]


def summarize(d) -> None:
    rows = read_rows(d / "a5a.jsonl") + read_rows(d / "a5b.jsonl")
    lines = ["# A5: interaction-mutation catalog", ""]
    for stage in ("a5a", "a5b"):
        rs = [r for r in rows if r["stage"] == stage]
        if not rs:
            continue
        npass = sum(r["passed"] for r in rs)
        lines.append(f"## {stage}: {npass} of {len(rs)} candidates pass")
        if stage == "a5a":
            lines.append(f"**G0 ({'>= 3 of 10'}): {'PASS' if npass >= 3 else 'FAIL'}**")
        lines.append("")
        lines.append("| candidate | mechanism | m | witness (k) | 1 | 2 | 3 | 4 | 5 | result |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in rs:
            for g in r["gates"]:
                c = g.get("checks", {})
                ok = lambda k: "-" if k not in c else ("ok" if c[k]["ok"] else "FAIL")
                w = g.get("witness", {})
                wk = f"{w.get('household_id', '-')} ({w.get('k', '-')})" if w.get("found") else "none"
                lines.append(f"| {r['family']['id']} | {r['family']['mechanism']} | {g['magnitude']:g} | {wk} | {ok('1_witness')} | {ok('2_grid')} | {ok('3_ablation')} | {ok('4_spot')} | {ok('5_reverse')} | {'pass' if g['passed'] else g.get('reason', '')} |")
        lines.append("")
        reasons = Counter((g.get("reason") or "pass") for r in rs for g in r["gates"])
        lines.append("Gate outcomes (per magnitude): " + ", ".join(f"{k}: {n}" for k, n in reasons.most_common()))
        lines.append("")
    fams = [r for r in rows if r["passed"]]
    lines.append(f"Families passing so far: {len(fams)} (G2 needs >= 20).")
    (d / "summary.md").write_text("\n".join(lines) + "\n")
    json.dump([{"family": r["family"], "stage": r["stage"], "passed": r["passed"]} for r in rows], open(d / "manifest.json", "w"), indent=1)
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("a5a", "a5b"))
    ap.add_argument("--extend", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    d = results_dir("a5")
    cands = candidates(SEED)
    if a.stage == "a5a":
        sel = cands[:SPIKE]
    elif a.stage == "a5b":
        sel = cands[SPIKE : SPIKE + (80 if a.extend else 50)]
    else:
        sel = []
    if sel:
        json.dump([f.describe() for f in sel], open(d / f"{a.stage}_candidates.json", "w"), indent=1)
        run([{"id": f.id, "family": f.id, "stage": a.stage} for f in sel], job, d / f"{a.stage}.jsonl", workers=a.workers, wave=len(sel))
    summarize(d)


if __name__ == "__main__":
    main()
