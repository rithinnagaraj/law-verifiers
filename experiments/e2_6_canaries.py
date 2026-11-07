"""E2.6b canary bugs: how often does search exploit a calculator bug, and how
much of it does the cross-check catch? Also E2.6a: the share of
PolicyEngine-positive proposals failing the cross-check as the budget grows.

The verifier runs with each canary (PolicyEngine-only reform; Tax-Calculator
correct). A flagged proposal is a canary exploit when the canary creates
> $50 and >= 20% of its gain (re-evaluated under the correct law). Caught =
labelled code_disagreement (ratio cross-check); the stricter tolerance test
is reported alongside.

    python experiments/e2_6_canaries.py --budget 400 --seeds 2 --pool 40 --workers 6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
from common import out_dir, run_jobs, run_metadata, write_json

from taxred.canaries import canaries
from taxred.generate import random_households
from taxred.law import Law
from taxred.search import GreedyPoolProposer, RandomPoolProposer, search_pool
from taxred.verifier import Verifier, VerifierConfig

FLAGGED = ("candidate", "code_disagreement")
PROPOSERS = {"random": RandomPoolProposer, "greedy": GreedyPoolProposer}
CFG = VerifierConfig(run_attribution=False)


def _pool(cid, hh, n, year):
    s = int(hashlib.sha1(cid.encode()).hexdigest(), 16) % 10_000
    pool = random_households(n - 1, seed=2000 + s, year=year)
    pos = s % n
    return pool[:pos] + [hh] + pool[pos:]


def _score(records, hh_by_id, correct: Verifier):
    """Rows for flagged records with the canary-created share of the gain."""
    flagged = [r for r in records if r.verdict.label in FLAGGED]
    rows = []
    if not flagged:
        return rows
    ok = correct.evaluate_many([(hh_by_id[r.household_id], r.moves) for r in flagged])
    for r, c in zip(flagged, ok):
        v = r.verdict
        created = v.gain - c.gain
        rows.append(dict(call=r.call, household_id=r.household_id, label=v.label, gain=v.gain, gain_correct=c.gain,
                         created=created, exploit=bool(created > 50 and created >= 0.2 * v.gain),
                         caught_ratio=v.label == "code_disagreement", tolerance_pass=bool(v.crosscheck_tolerance_pass),
                         coverage=v.coverage, moves=json.dumps(r.moves)))
    return rows


def run(args):
    kind, cid, cond, seed, budget, pool_n, year, batch = args
    c = canaries()[cid]
    law = c.law(year)
    bug, correct = Verifier(law, CFG), Verifier(Law(year), CFG)
    hh, moves = c.witness(year)
    if kind == "witness":
        a = bug.evaluate(hh, moves)
        b = correct.evaluate(hh, moves)
        return dict(kind=kind, canary=cid, layer=c.layer, label=a.label, gain=a.gain, gain_correct=b.gain, created=a.gain - b.gain,
                    fed_pe=a.gain_federal_pe, fed_tc=a.gain_federal_tc, tolerance_pass=a.crosscheck_tolerance_pass)
    pool = _pool(cid, hh, pool_n, year)
    recs = search_pool(pool, bug, PROPOSERS[cond](), budget, batch=batch, seed=seed)
    pos = [(r.call, bool(r.verdict.gain > 50 and r.verdict.reality_unchanged), r.verdict.label == "code_disagreement") for r in recs]
    rows = _score(recs, {h.id: h for h in pool}, correct)
    return dict(kind=kind, canary=cid, layer=c.layer, condition=cond, seed=seed, calls=len(recs), flagged=rows, positives=pos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--pool", type=int, default=40)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    od = out_dir("phase2/canaries")
    ids = list(canaries())
    jobs = [("witness", c, "", 0, 0, 0, a.year, 0) for c in ids]
    jobs += [("search", c, cond, s, a.budget, a.pool, a.year, a.batch) for c in ids for cond in PROPOSERS for s in range(a.seeds)]
    res = run_jobs(run, jobs, a.workers, checkpoint=od / f"checkpoint_b{a.budget}_p{a.pool}.jsonl", max_tasks_per_child=4)

    wit = pd.DataFrame([r for r in res if r["kind"] == "witness"])
    wit["exploit"] = (wit.created > 50) & wit.label.isin(FLAGGED)
    wit["caught"] = wit.label == "code_disagreement"
    rows, pos = [], []
    for r in res:
        if r["kind"] != "search":
            continue
        for f in r["flagged"]:
            rows.append(dict(canary=r["canary"], layer=r["layer"], condition=r["condition"], seed=r["seed"], **f))
        for call, p, dis in r["positives"]:
            pos.append(dict(canary=r["canary"], layer=r["layer"], condition=r["condition"], call=call, pe_positive=p, disagree=dis))
    fl = pd.DataFrame(rows)
    fl.to_csv(od / "flagged.csv.gz", index=False)
    ex = fl[fl.exploit] if len(fl) else fl
    by = []
    if len(fl):
        for (cid, layer, cond), g in fl.groupby(["canary", "layer", "condition"]):
            e = g[g.exploit]
            by.append(dict(canary=cid, layer=layer, condition=cond, flagged=len(g), exploits=len(e),
                           found_by_seeds=float(e.groupby("seed").size().reindex(range(a.seeds), fill_value=0).gt(0).mean()),
                           caught_ratio=float(e.caught_ratio.mean()) if len(e) else np.nan,
                           caught_tolerance=float((~e.tolerance_pass).mean()) if len(e) else np.nan))
    bt = pd.DataFrame(by)
    pdf = pd.DataFrame(pos)
    pressure = None
    if len(pdf):
        pdf["bin"] = pd.cut(pdf.call, [0, 50, 100, 200, 400, 1000, 1e9])
        pressure = pdf[pdf.pe_positive].groupby(["condition", "bin"], observed=True).disagree.mean().unstack(0)
    summary = dict(meta=run_metadata(), budget=a.budget, pool=a.pool, seeds=a.seeds,
                   witnesses=wit.to_dict(orient="records"), by_canary=by,
                   overall={layer: dict(exploits=int(len(g)), caught_ratio=float(g.caught_ratio.mean()) if len(g) else None,
                                        caught_tolerance=float((~g.tolerance_pass).mean()) if len(g) else None)
                            for layer, g in (ex.groupby("layer") if len(ex) else [])})
    write_json(od / "summary.json", summary)
    md = (
        f"# E2.6b canary bugs (pool {a.pool}, budget {a.budget}, {a.seeds} seeds)\n\n"
        "## Witnesses (canary law vs correct law)\n\n" + wit[["canary", "layer", "label", "gain", "gain_correct", "created", "fed_pe", "fed_tc", "exploit", "caught", "tolerance_pass"]].to_markdown(index=False, floatfmt=".0f")
        + "\n\n## Search: canary exploits found and caught\n\n" + (bt.to_markdown(index=False, floatfmt=".2f") if len(bt) else "no flagged proposals")
        + "\n\n## Overall by layer (exploits pooled over canaries, conditions, seeds)\n\n" + json.dumps(summary["overall"], indent=1)
        + "\n\n## E2.6a: share of PE-positive proposals failing the cross-check, by call index\n\n" + (pressure.to_markdown(floatfmt=".3f") if pressure is not None else "n/a") + "\n"
    )
    (od / "summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
