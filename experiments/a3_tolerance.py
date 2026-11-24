"""A3. Tolerance sensitivity: relabel saved verdicts (no new calculator runs
for the sweep itself) under cross-check tolerances max($10, b%) for
b in {1, 2, 5, 10}% and the v1 ratio test (Tax-Calculator >= 50% of
PolicyEngine). Sources:

  A2 random proposals         false code_disagreement rate
  canary search (this script) catch rate of canary exploits
  legitimate-planning dev     false code_disagreement rate on positives

The canary search (v1 E2.6b, rebuilt): for each canary, pools of 40 survey
households with the canary's witness at a seeded position; random and
greedy search, 3 seeds x 400 calls; reward blind to the cross-check. An
exploit is a proposal whose canary-attributable gain (gain under the canary
law minus gain under current law) is >= $50 and >= 0.1 of its gain.

Usage: python experiments/a3_tolerance.py [--canary] [--legit] [--summary]
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from taxgap import ecps
from taxgap.config import results_dir
from taxgap.law import CURRENT_LAW
from taxgap.runner import read_rows, run
from taxgap.search.pool import GreedyProposer, RandomProposer, search
from taxgap.targets.canaries import canaries
from taxgap.targets.planning import scenarios
from taxgap.verifier import Config, Verdict, Verifier, label

POOL = 40
BUDGET = 400
SEEDS = (0, 1, 2)
TOLS = [("max($10,1%)", Config(tol_rel=0.01)), ("max($10,2%)", Config(tol_rel=0.02)), ("max($10,5%)", Config(tol_rel=0.05)), ("max($10,10%)", Config(tol_rel=0.10)), ("ratio 50%", Config(mode="ratio", tol_abs=25.0))]

SURVEY: list = []


def pool_for(cid: str, seed: int):
    rng = np.random.default_rng([7, seed, sum(map(ord, cid))])
    idx = rng.choice(len(SURVEY), size=POOL - 1, replace=False)
    hh, mv = canaries()[cid].witness()
    pool = [SURVEY[i] for i in idx]
    pos = int(rng.integers(POOL))
    pool.insert(pos, hh)
    for k, h in enumerate(pool):
        h = h.copy()
        h.id = f"h{k}"
        pool[k] = h
    return pool, pos, mv


def canary_job(j: dict) -> list:
    c = canaries()[j["canary"]]
    pool, pos, wmv = pool_for(c.id, j["seed"])
    rng = np.random.default_rng([j["seed"], 99])
    prop = RandomProposer(pool, rng) if j["cond"] == "random" else GreedyProposer(pool, rng, blind_crosscheck=True)
    recs = search(pool, c.law(), prop, BUDGET)
    # current-law gain for every proposal with a gain under the canary law
    need = [r for r in recs if r.verdict["gain"] > 50]
    cur = Verifier(CURRENT_LAW, Config(attribute=False, recheck=False)).evaluate([(pool[r.hh], r.moves) for r in need])
    cur_of = {id(r): v.gain for r, v in zip(need, cur)}
    rows = []
    for r in recs:
        g0 = cur_of.get(id(r))
        rows.append({**r.to_row(), "canary": c.id, "layer": c.layer, "cond": j["cond"], "seed": j["seed"], "witness_pos": pos, "gain_current": g0})
    # the witness itself, for reference
    w = Verifier(c.law()).one(pool[pos], wmv)
    w0 = Verifier(CURRENT_LAW, Config(attribute=False, recheck=False)).one(pool[pos], wmv)
    rows.append({"call": -1, "hh": pos, "moves": wmv, "verdict": w.to_dict(), "canary": c.id, "layer": c.layer, "cond": "witness", "seed": j["seed"], "witness_pos": pos, "gain_current": w0.gain})
    return rows


def legit_job(j: dict) -> list:
    ss = [s for s in scenarios() if s.split == "dev" and s.family == j["family"]]
    vs = Verifier(CURRENT_LAW, Config(attribute_all=True)).evaluate([(s.household, s.moves) for s in ss])
    return [{"id": s.id, "family": s.family, "positive": s.positive, "expected": sorted(s.expected), "verdict": v.to_dict()} for s, v in zip(ss, vs)]


def is_exploit(r: dict) -> bool:
    g, g0 = r["verdict"]["gain"], r.get("gain_current")
    return r["verdict"]["error"] is None and g0 is not None and g > 50 and g - g0 >= 50 and g - g0 >= 0.1 * g


def summarize(d) -> None:
    a2 = [Verdict.from_dict(r["verdict"]) for r in read_rows(results_dir("a2") / "proposals.jsonl") if r["verdict"]["error"] is None]
    can = read_rows(d / "canary.jsonl")
    leg = read_rows(d / "legit_dev.jsonl")
    lines = ["# A3: tolerance sensitivity", ""]
    lines.append(f"Sources: {len(a2)} A2 random proposals; canary search {len([r for r in can if r['cond'] != 'witness'])} proposals; legitimate-planning dev split {len(leg)} scenarios.")
    lines.append("")
    fed = [r for r in can if r["layer"] == "federal_income" and r["cond"] != "witness"]
    expl = [r for r in fed if is_exploit(r)]
    # one exploit per distinct (canary, seed, cond, household, moves)
    uniq = {(r["canary"], r["seed"], r["cond"], r["hh"], json.dumps(r["moves"], sort_keys=True)): r for r in expl}
    expl = list(uniq.values())
    lines.append(f"Federal canary exploits found by search: {len(expl)} distinct, in {len({r['canary'] for r in expl})} of {len({r['canary'] for r in fed})} canaries.")
    lines.append("")
    lines.append("| cross-check | canary catch rate | caught / exploits | A2 random: code_disagreement | legit positives: code_disagreement | legit positives flagged (any) |")
    lines.append("|---|---|---|---|---|---|")
    pos = [r for r in leg if r["positive"]]
    out = {}
    for name, cfg in TOLS:
        caught = sum(label(Verdict.from_dict(r["verdict"]), cfg) != "candidate" for r in expl)
        a2r = np.mean([label(v, cfg) == "code_disagreement" for v in a2]) if a2 else float("nan")
        lp = [label(Verdict.from_dict(r["verdict"]), cfg) for r in pos]
        lcd = np.mean([x == "code_disagreement" for x in lp]) if lp else float("nan")
        lfl = np.mean([x in ("candidate", "code_disagreement") for x in lp]) if lp else float("nan")
        rate = caught / len(expl) if expl else float("nan")
        out[name] = {"catch": rate, "a2_cd": a2r, "legit_cd": lcd, "legit_flagged": lfl}
        lines.append(f"| {name} | {rate:.3f} | {caught} / {len(expl)} | {a2r:.4f} | {lcd:.3f} | {lfl:.3f} |")
    lines.append("")
    lines.append("## Per canary (frozen default max($10, 2%))")
    lines.append("")
    lines.append("| canary | witness label | exploits | caught | best exploit gain | found by |")
    lines.append("|---|---|---|---|---|---|")
    cfg = Config()
    for cid in canaries():
        w = [r for r in can if r["canary"] == cid and r["cond"] == "witness"]
        e = [r for r in expl if r["canary"] == cid]
        caught = sum(label(Verdict.from_dict(r["verdict"]), cfg) != "candidate" for r in e)
        best = max((r["verdict"]["gain"] for r in e), default=0)
        conds = ",".join(sorted({r["cond"] for r in e}))
        lines.append(f"| {cid} | {w[0]['verdict']['label'] if w else '-'} | {len(e)} | {caught} | {best:,.0f} | {conds or '-'} |")
    (d / "summary.md").write_text("\n".join(lines) + "\n")
    json.dump(out, open(d / "summary.json", "w"), indent=1, default=float)
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canary", action="store_true")
    ap.add_argument("--legit", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    d = results_dir("a3")
    if a.canary:
        SURVEY.extend(ecps.load(3040, seed=0)[3000:] + ecps.load(400, seed=11))
        jobs = [{"id": f"{c}_{cond}_{s}", "canary": c, "cond": cond, "seed": s} for c in canaries() for cond in ("random", "greedy") for s in SEEDS]
        run(jobs, canary_job, d / "canary.jsonl", workers=a.workers, wave=len(jobs))
    if a.legit:
        fams = sorted({s.family for s in scenarios()})
        run([{"id": f, "family": f} for f in fams], legit_job, d / "legit_dev.jsonl", workers=a.workers)
    if a.summary or not (a.canary or a.legit):
        summarize(d)


if __name__ == "__main__":
    main()
