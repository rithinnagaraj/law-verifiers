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
import copy
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
from taxred.llm import LLMPoolProposer, LLMProposer
from taxred.verifier import Verifier, VerifierConfig

PROPOSERS = {"random": RandomProposer, "greedy": GreedyProposer}
POOL_PROPOSERS = {"random": RandomPoolProposer, "greedy": GreedyPoolProposer}
FLAGGED = ("candidate", "code_disagreement")
BUDGETS = [10, 25, 50, 100, 200, 400, 1000, 3000]
BASE_RULES = "US federal individual income tax and benefit law for the tax year shown, as in force, except:"
HIST_RULES = {
    "kiddie_tra1986": "There is no special tax on a child's unearned income: a child's investment income is taxed at the child's own rates.",
    "kiddie_tipra2005": "A child's net unearned income is taxed at the parent's rate only for children under 14.",
    "kiddie_sbwota2007": "A child's net unearned income is taxed at the parent's rate only for children under 18.",
    "dependent_std_tra1986": "There is no special tax on a child's unearned income, and a dependent filer gets the full standard deduction.",
    "roth_recharacterization_tcja2017": "A conversion of a traditional IRA to a Roth IRA may be recharacterized (undone) until October 15 of the following year.",
}
HIST_WITNESS = {
    "kiddie_tra1986": "w200000_i20000_a8",
    "kiddie_tipra2005": "w200000_i20000_a16",
    "kiddie_sbwota2007": "w200000_i20000_a20s",
    "dependent_std_tra1986": "w100000_i20000_a13",
    "roth_recharacterization_tcja2017": "r40000_200000",
}


def targets(year: int, disguised: bool = False):
    """(target id, kind, law, closure, household, horizon, rules text)"""
    out = []
    man = Path(out_dir("phase2/planted")) / "variants.json"
    valid = {m["id"] for m in json.loads(man.read_text()) if m["valid"]} if man.exists() else None
    for v in variants(year):
        if valid is None or v.id in valid:
            rules = f"{BASE_RULES} {v.disguised if disguised else v.description}"
            out.append((f"planted:{v.id}", "planted", v.law, v.closure, v.witness_household, v.horizon, rules))
    cases = closure_cases(year)
    for name, hid in HIST_WITNESS.items():
        c = cases[name]
        hh = next(h for h in c.panel(year) if h.id == hid)
        out.append((f"hist:{name}", "historical", c.law_pre, c.law_post, hh, c.horizon, f"{BASE_RULES} {HIST_RULES[name]}"))
    return out


ECPS_BANK = (2000, 7)  # stage 1: pools are drawn from one cached survey sample


def make_pool(tid: str, hh, n: int, year: int, stage: int = 0):
    """n-1 other households plus the witness, at a seeded position; the same
    for every condition and seed of a target. Stage 0: synthetic draws.
    Stage 1: enhanced-CPS survey households, and every household gets a
    neutral id (h0, h1, ...) so the witness does not stand out.
    Returns (pool, witness id)."""
    s = int(hashlib.sha1(tid.encode()).hexdigest(), 16) % 10_000
    pos = s % n
    if stage == 0:
        pool = random_households(n - 1, seed=1000 + s, year=year)
        return pool[:pos] + [hh] + pool[pos:], hh.id
    from taxred.ecps import load_households

    bank = load_households(*ECPS_BANK)
    rng = np.random.default_rng(1000 + s)
    others = [bank[i] for i in rng.choice(len(bank), n - 1, replace=False)]
    pool = others[:pos] + [hh] + others[pos:]
    from taxred.household import with_scenarios

    renamed = []
    for k, h in enumerate(pool):
        c = h if h.scenarios else with_scenarios(h)  # every household gets the same possible futures
        c = copy.copy(c)
        c.id = f"h{k}"
        renamed.append(c)
    return renamed, f"h{pos}"


def run(args):
    tid, cond, seed, budget, year, r_min, pool_n, model, disguised, batch, stage = args
    _, kind, law, closure, hh, horizon, rules = next(t for t in targets(year, disguised) if t[0] == tid)
    if stage == 1:
        horizon = max(horizon, 3)
    opts = dict(continuous=True, horizon=horizon) if stage == 1 else {}
    witness_id = hh.id
    ver = Verifier(law, VerifierConfig(run_attribution=False, horizon=horizon))
    if pool_n:
        pool, witness_id = make_pool(tid, hh, pool_n, year, stage)
        prop = LLMPoolProposer(rules=rules, model=model) if cond == "llm" else POOL_PROPOSERS[cond](**opts)
        hist = search_pool(pool, ver, prop, budget, batch=10 if cond == "llm" else batch, seed=seed)
    else:
        pool = [hh]
        prop = LLMProposer(rules=rules, model=model) if cond == "llm" else PROPOSERS[cond](**opts)
        hist = search_many([hh], ver, prop, budget, batch=10 if cond == "llm" else batch, seed=seed)[hh.id]
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
                witness_matched=witness_id in matched_households, stage=stage, horizon=horizon,
                labels=json.dumps(pd.Series([r.verdict.label for r in hist]).value_counts().to_dict()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--r-min", type=float, default=None, help="default: the R chosen by E0.7, else 0.3")
    ap.add_argument("--conditions", nargs="*", default=list(PROPOSERS))
    ap.add_argument("--stage", type=int, default=0, choices=[0, 1], help="1: realistic enlargement (survey households, 3-year horizon, continuous amounts, dated moves)")
    ap.add_argument("--batch", type=int, default=25, help="proposals per search round (larger amortises calculator overhead)")
    ap.add_argument("--model", default="claude-opus-5-5", help="for the llm condition (needs API credentials)")
    ap.add_argument("--disguised", action="store_true", help="planted targets show the disguised rule description (H3)")
    ap.add_argument("--pool", type=int, default=0, help="search over a pool of this many households (witness hidden among random ones); 0 = witness only")
    a = ap.parse_args()
    if a.r_min is None:
        e07 = Path(out_dir("phase0/e0_7")) / "summary.json"
        a.r_min = float(json.loads(e07.read_text())["best"]["R"]) if e07.exists() else 0.3
    od = out_dir("phase2/frozen" + (f"_stage{a.stage}" if a.stage else "") + (f"_pool{a.pool}" if a.pool else "") + ("_disguised" if a.disguised else ""))
    if a.stage == 1 and a.pool:
        from taxred.ecps import load_households

        load_households(*ECPS_BANK)  # build the survey-sample cache once, before the workers start
    tids = [t[0] for t in targets(a.year)]
    jobs = [(t, c, s, a.budget, a.year, a.r_min, a.pool, a.model, a.disguised, a.batch, a.stage) for t in tids for c in a.conditions for s in range(a.seeds)]
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
