"""E1.4 smoke test against an adversary: random and greedy search over the
move vocabulary on current law. Development data (kept out of H4).

Outputs, per condition: label counts; the share of PolicyEngine-positive
proposals (gain above threshold, reality unchanged) that fail the
cross-check; candidate signatures; and the top candidates per signature,
for manual inspection of verifier bugs before Phase 2.

    python experiments/e1_4_search_smoke.py --n 120 --budget 100 --workers 8
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from common import chunks, out_dir, run_jobs, run_metadata, write_json

from taxred.generate import archetypes, random_households
from taxred.law import Law
from taxred.search import GreedyProposer, RandomProposer, search_many
from taxred.verifier import Verifier, VerifierConfig

PROPOSERS = {"random": RandomProposer, "greedy": GreedyProposer}


def households(n: int, seed: int, year: int):
    return archetypes(year) + random_households(n, seed=seed, year=year)


def run(args):
    ids, cond, budget, seed, n, year = args
    by_id = {h.id: h for h in households(n, seed, year)}
    hhs = [by_id[i] for i in ids]
    hist = search_many(hhs, Verifier(Law(year), VerifierConfig(recheck_flagged=True)), PROPOSERS[cond](), budget, batch=25, seed=seed)
    rows = []
    for hid, recs in hist.items():
        for r in recs:
            rows.append(dict(condition=cond, seed=seed, **r.to_row()))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--budget", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--conditions", nargs="*", default=list(PROPOSERS))
    ap.add_argument("--from-csv", action="store_true")
    ap.add_argument("--tag", default="")
    ap.add_argument("--chunk", type=int, default=8, help="households per job")
    a = ap.parse_args()
    od = out_dir("phase1/search_smoke" + (f"_{a.tag}" if a.tag else ""))
    if a.from_csv:
        df = pd.read_csv(od / "records.csv.gz")
    else:
        ids = [h.id for h in households(a.n, a.seed, a.year)]
        # Small chunks bound each worker's simulation size; the checkpoint
        # makes a crash lose only the jobs in flight.
        jobs = [(list(c), cond, a.budget, a.seed, a.n, a.year) for cond in a.conditions for c in chunks(ids, a.chunk)]
        rows = [row for r in run_jobs(run, jobs, a.workers, checkpoint=od / "checkpoint.jsonl") for row in r]
        df = pd.DataFrame(rows)
        df.to_csv(od / "records.csv.gz", index=False)

    df["pe_positive"] = (df.gain > 50) & df.reality.fillna(False).astype(bool)
    out = {"meta": run_metadata(), "n_households": int(df.household_id.nunique()), "budget": a.budget, "conditions": {}}
    md = [f"# E1.4 search smoke test (current law, {df.household_id.nunique()} households, budget {a.budget})\n"]
    for cond, g in df.groupby("condition"):
        pos = g[g.pe_positive]
        cands = g[g.label == "candidate"]
        sig = cands.signature.fillna("").replace("", "(none)").value_counts()
        hh_with = cands.household_id.nunique()
        out["conditions"][cond] = dict(
            proposals=len(g),
            labels=g.label.value_counts().to_dict(),
            pe_positive=len(pos),
            crosscheck_fail_share_of_pe_positive=float((pos.label == "code_disagreement").mean()) if len(pos) else None,
            households_with_candidate=int(hh_with),
            candidate_signatures=sig.to_dict(),
            candidate_coverage=cands.coverage.value_counts().to_dict(),
        )
        md.append(f"## {cond}\n")
        md.append(f"- proposals {len(g)}; labels {g.label.value_counts().to_dict()}")
        md.append(f"- PE-positive (gain > $50, reality unchanged): {len(pos)}; of these failing the cross-check: {out['conditions'][cond]['crosscheck_fail_share_of_pe_positive']}")
        md.append(f"- households with >= 1 candidate: {hh_with} / {g.household_id.nunique()}")
        md.append(f"- candidate coverage: {cands.coverage.value_counts().to_dict()}\n")
        md.append("### Candidate signatures\n\n" + sig.to_frame("n").to_markdown() + "\n")
        top = (
            cands.sort_values("gain", ascending=False)
            .assign(sig=lambda d: d.signature.fillna(""))
            .groupby("sig")
            .head(2)
            .head(25)[["household_id", "gain", "gain_federal_pe", "gain_federal_tc", "gain_other_tax", "gain_benefits", "coverage", "sig", "residual_without_intended", "moves"]]
        )
        md.append("### Top candidates (2 per signature)\n\n" + top.to_markdown(index=False, floatfmt=".0f") + "\n")
        dis = g[g.label == "code_disagreement"].sort_values("gain", ascending=False).head(10)
        md.append("### Top cross-check failures\n\n" + dis[["household_id", "gain", "gain_federal_pe", "gain_federal_tc", "moves"]].to_markdown(index=False, floatfmt=".0f") + "\n")
    write_json(od / "summary.json", out)
    (od / "summary.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
