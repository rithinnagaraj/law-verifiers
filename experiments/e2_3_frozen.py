"""E2.3 frozen comparison (non-LLM conditions so far): recall vs budget.

Targets: valid planted variants (results/phase2/planted/variants.json) and
historical closure cases (pre-closure law, one covered witness household).
For each target x condition x seed, search the target household under the
target law for `budget` verifier calls. A proposal rediscovers the target
when it is flagged and the target's closure removes >= R of its gain
(matching rule, closure-test half; R from E0.7). Recall@b = share of targets
rediscovered within b calls; the primary metric is the normalised area under
the recall-vs-log-budget curve.

Attribution is off during search: a match already implies the gain is not
fully explained by intended provisions (the closure, which is not intended,
removes >= R > intended_residual_max of it).

    python experiments/e2_3_frozen.py --budget 200 --seeds 3 --workers 6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
from common import out_dir, run_jobs, run_metadata, write_json

from taxred.cases import closure_cases
from taxred.planted import variants
from taxred.generate import random_households
from taxred.search import GreedyPoolProposer, GreedyProposer, RandomPoolProposer, RandomProposer, search_many, search_pool
from taxred.verifier import Verifier, VerifierConfig

PROPOSERS = {"random": RandomProposer, "greedy": GreedyProposer}
POOL_PROPOSERS = {"random": RandomPoolProposer, "greedy": GreedyPoolProposer}
FLAGGED = ("candidate", "code_disagreement")
BUDGETS = [10, 25, 50, 100, 200, 400, 1000, 3000]
HIST_WITNESS = {
    "kiddie_tra1986": "w200000_i20000_a8",
    "kiddie_tipra2005": "w200000_i20000_a16",
    "kiddie_sbwota2007": "w200000_i20000_a20s",
    "dependent_std_tra1986": "w100000_i20000_a13",
}


def targets(year: int):
    """(target id, kind, law, closure, household, horizon)"""
    out = []
    man = Path(out_dir("phase2/planted")) / "variants.json"
    valid = {m["id"] for m in json.loads(man.read_text()) if m["valid"]} if man.exists() else None
    for v in variants(year):
        if valid is None or v.id in valid:
            out.append((f"planted:{v.id}", "planted", v.law, v.closure, v.witness_household, v.horizon))
    cases = closure_cases(year)
    for name, hid in HIST_WITNESS.items():
        c = cases[name]
        hh = next(h for h in c.panel(year) if h.id == hid)
        out.append((f"hist:{name}", "historical", c.law_pre, c.law_post, hh, 1))
    return out


def make_pool(tid: str, hh, n: int, year: int):
    """n-1 random households plus the witness, at a seeded position. The pool
    is the same for every condition and seed of a target."""
    s = int(hashlib.sha1(tid.encode()).hexdigest(), 16) % 10_000
    pool = random_households(n - 1, seed=1000 + s, year=year)
    pos = s % n
    return pool[:pos] + [hh] + pool[pos:]


def run(args):
    tid, cond, seed, budget, year, r_min, pool_n = args
    _, kind, law, closure, hh, horizon = next(t for t in targets(year) if t[0] == tid)
    ver = Verifier(law, VerifierConfig(run_attribution=False, horizon=horizon))
    if pool_n:
        pool = make_pool(tid, hh, pool_n, year)
        hist = search_pool(pool, ver, POOL_PROPOSERS[cond](), budget, batch=25, seed=seed)
    else:
        pool = [hh]
        hist = search_many([hh], ver, PROPOSERS[cond](), budget, batch=25, seed=seed)[hh.id]
    by_id = {h.id: h for h in pool}
    flagged = [r for r in hist if r.verdict.label in FLAGGED]
    first = None
    n_match = 0
    matched_households = set()
    if flagged:
        post = Verifier(closure, VerifierConfig(run_attribution=False, horizon=horizon)).evaluate_many([(by_id[r.household_id], r.moves) for r in flagged])
        for r, b in zip(flagged, post):
            red = (r.verdict.gain - b.gain) / r.verdict.gain if r.verdict.gain > 0 else 0.0
            if red >= r_min:
                n_match += 1
                matched_households.add(r.household_id)
                first = r.call if first is None else min(first, r.call)
    return dict(target=tid, kind=kind, condition=cond, seed=seed, pool=pool_n, calls=len(hist), n_flagged=len(flagged),
                n_match=n_match, first_match_call=first, matched_households=sorted(matched_households),
                witness_matched=hh.id in matched_households,
                labels=json.dumps(pd.Series([r.verdict.label for r in hist]).value_counts().to_dict()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--r-min", type=float, default=None, help="default: the R chosen by E0.7, else 0.3")
    ap.add_argument("--conditions", nargs="*", default=list(PROPOSERS))
    ap.add_argument("--pool", type=int, default=0, help="search over a pool of this many households (witness hidden among random ones); 0 = witness only")
    a = ap.parse_args()
    if a.r_min is None:
        e07 = Path(out_dir("phase0/e0_7")) / "summary.json"
        a.r_min = float(json.loads(e07.read_text())["best"]["R"]) if e07.exists() else 0.3
    od = out_dir("phase2/frozen" + (f"_pool{a.pool}" if a.pool else ""))
    tids = [t[0] for t in targets(a.year)]
    jobs = [(t, c, s, a.budget, a.year, a.r_min, a.pool) for t in tids for c in a.conditions for s in range(a.seeds)]
    rows = run_jobs(run, jobs, a.workers, checkpoint=od / f"checkpoint_r{a.r_min:g}_b{a.budget}.jsonl", max_tasks_per_child=8)
    df = pd.DataFrame(rows)
    df.to_csv(od / "runs.csv", index=False)
    budgets = [b for b in BUDGETS if b <= a.budget]
    rec = []
    for (cond, kind), g in df.groupby(["condition", "kind"]):
        row = dict(condition=cond, kind=kind, n_targets=g.target.nunique())
        curve = []
        for b in budgets:
            per_seed = g.assign(hit=g.first_match_call.fillna(1e9) <= b).groupby("seed").hit.mean()
            row[f"recall@{b}"] = float(per_seed.mean())
            curve.append(per_seed.mean())
        x = np.log(budgets)
        row["auc_log_budget"] = float(np.trapezoid(curve, x) / (x[-1] - x[0])) if len(x) > 1 else float(curve[0])
        rec.append(row)
    rt = pd.DataFrame(rec)
    per_target = df.assign(hit=df.first_match_call.notna()).pivot_table(index="target", columns="condition", values="hit", aggfunc="mean")
    write_json(od / "summary.json", {"meta": run_metadata(), "r_min": a.r_min, "budget": a.budget, "seeds": a.seeds, "recall": rec})
    md = (
        f"# E2.3 frozen comparison (non-LLM): budget {a.budget}, {a.seeds} seeds, R = {a.r_min}\n\n"
        + rt.to_markdown(index=False, floatfmt=".2f")
        + "\n\n## Rediscovery rate per target (share of seeds)\n\n" + per_target.to_markdown(floatfmt=".2f") + "\n"
    )
    (od / "summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
