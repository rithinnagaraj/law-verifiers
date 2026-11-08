"""Stage 2 preparation (preregistration-stage2.md): validate the stage 2
planted variants and build their 200-household pools.

For each stage 2 variant:
  1. validity   the witness is flagged under the mutated law and the mutation
                creates >= MIN_REDUCTION of its gain;
  2. length     exhaustive search over every sequence of <= 2 moves from a
                discretised vocabulary on the witness household: the family
                fails if any such sequence is flagged with >= R of its gain
                created by the mutation (no tuning: failing families are
                dropped);
  3. rarity     the witness strategy, adapted by role, is evaluated on every
                household of the survey bank; eligible households are left
                out, and the pool is 199 ineligible households + the witness.

Writes results/phase2/stage2/{manifest.json, summary.md}.

    python experiments/e2_s2_prepare.py --workers 4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from common import out_dir, run_jobs, run_metadata, write_json

from taxred.ecps import load_households
from taxred.household import with_scenarios
from taxred.moves import DECOYS, MoveError, apply_moves
from taxred.planted import variants
from taxred.verifier import Verifier, VerifierConfig

R = 0.1  # matching threshold (E0.7)
MIN_REDUCTION = 0.3  # validity bar (as E2.1)
FLAGGED = ("candidate", "code_disagreement")
BANK = (2000, 7)
POOL = 200
CFG = VerifierConfig(run_attribution=False, horizon=3, crosscheck_mode="tolerance")


def single_moves(hh, years):
    """A discretised vocabulary of single moves on hh, each dated in `years`."""
    ms = []
    people = list(hh.people)
    for tu in hh.tax_units:
        if tu.spouse:
            ms.append({"op": "set_filing_status", "tax_unit": tu.id, "status": "SEPARATE"})
    for g in people:
        for a in hh.people[g].assets:
            for r in people:
                if r != g:
                    for f in (0.5, 1.0):
                        ms.append({"op": "gift_asset", "giver": g, "recipient": r, "asset": a.id, "fraction": f})
            if a.unrealized_gain > 0:
                ms.append({"op": "realize_gain", "person": g, "asset": a.id, "fraction": 1.0})
        se = hh.people[g].self_employment
        if se > 0:
            for r in people:
                if r != g:
                    for f in (0.1, 0.25, 0.5):
                        ms.append({"op": "shift_income", "payer": g, "payee": r, "amount": round(se * f)})
        if hh.people[g].wages > 0:
            ms.append({"op": "contribute_retirement", "person": g, "account": "401k", "amount": round(min(23_000, hh.people[g].wages) / 2)})
    for p in people:
        for d in DECOYS:
            ms.append({"op": d} if d == "decoy_household_max_401k" else {"op": d, "person": p})
    return [dict(m, year=y) for m in ms for y in years]


def short_sequences(hh, years):
    singles = single_moves(hh, years)
    seqs = [[m] for m in singles] + [[a, b] for a in singles for b in singles if a is not b]
    # assignments only make sense after a split: add (split, assign) pairs
    for y in years:
        for tu in hh.tax_units:
            if tu.spouse:
                for d in tu.dependents:
                    for y2 in years:
                        if y2 >= y:
                            seqs.append([{"op": "set_filing_status", "tax_unit": tu.id, "status": "SEPARATE", "year": y},
                                         {"op": "assign_dependent", "dependent": d, "tax_unit": f"{tu.id}_s", "year": y2}])
    ok = []
    for s in seqs:
        try:
            apply_moves(hh, s)
            ok.append(s)
        except MoveError:
            pass
    return ok


def adapt(hh, kind, y):
    """The witness strategy adapted to a survey household by role, or None."""
    for tu in hh.tax_units:
        if not (tu.spouse and tu.dependents):
            continue
        a, b = sorted([tu.head, tu.spouse], key=lambda pid: -(hh.people[pid].earned_income + hh.people[pid].unearned_income))
        # After the split the head keeps the unit and the children; the spouse
        # gets "<unit>_s". The children go to b, the lower-income spouse.
        moves = [{"op": "set_filing_status", "tax_unit": tu.id, "status": "SEPARATE", "year": y}]
        if b == tu.spouse:
            moves += [{"op": "assign_dependent", "dependent": d, "tax_unit": f"{tu.id}_s", "year": y} for d in tu.dependents]
        if kind == "bonds":
            assets = sorted(hh.people[a].assets, key=lambda x: -x.value * x.interest_yield)
            if not assets or assets[0].interest_yield <= 0:
                return None
            moves.append({"op": "gift_asset", "giver": a, "recipient": b, "asset": assets[0].id, "fraction": 1.0, "year": y})
        else:
            se = hh.people[a].self_employment
            if se <= 0:
                return None
            moves.append({"op": "shift_income", "payer": a, "payee": b, "amount": round(min(250_000, se * 0.5)), "year": y})
        return moves
    return None


def created_share(pre, post):
    out = []
    for a, b in zip(pre, post):
        created = a.gain - b.gain
        out.append((a.label in FLAGGED and a.gain > 50 and created > 50, created / a.gain if a.gain > 0 else 0.0, a, b))
    return out


def run(args):
    vid, year = args
    v = next(x for x in variants(year, stage2=True) if x.id == vid)
    kind = "bonds" if "bonds" in v.family else "business"
    mut, clo = Verifier(v.law, CFG), Verifier(v.closure, CFG)
    hh, wit = v.witness_household, v.witness
    # 1. validity
    a, b = mut.evaluate(hh, wit), clo.evaluate(hh, wit)
    red = (a.gain - b.gain) / a.gain if a.gain > 0 else 0.0
    valid = bool(a.label in FLAGGED and red >= MIN_REDUCTION)
    res = dict(variant=vid, family=v.family, valid=valid, witness_label=a.label, witness_gain=a.gain, witness_gain_closure=b.gain,
               witness_reduction=red, witness_len=len(wit), scenario_gains=a.scenario_gains, crosscheck=a.crosscheck_pass)
    # 2. no sequence of <= 2 moves gets >= R of its gain from the mutation
    seqs = short_sequences(hh, [year, year + 1])
    pre = mut.evaluate_many([(hh, s) for s in seqs])
    post = clo.evaluate_many([(hh, s) for s in seqs])
    bad = [(s, round(sh, 3), round(x.gain)) for s, (hit, sh, x, _) in zip(seqs, created_share(pre, post)) if hit and sh >= R]
    res.update(n_short=len(seqs), short_hits=bad[:10], length_ok=not bad)
    # 3. rarity: the adapted strategy on every bank household
    bank = load_households(*BANK)
    props, idx = [], []
    for i, h in enumerate(bank):
        m = adapt(h, kind, year + 1)
        if m:
            props.append((with_scenarios(h), m))
            idx.append(i)
    eligible = set()
    if props:
        for i, (hit, sh, _, _) in zip(idx, created_share(mut.evaluate_many(props), clo.evaluate_many(props))):
            if hit and sh >= R:
                eligible.add(i)
    s = int(hashlib.sha1(vid.encode()).hexdigest(), 16) % 10_000
    rng = np.random.default_rng(3000 + s)
    order = [int(i) for i in rng.permutation(len(bank)) if int(i) not in eligible]
    res.update(n_adapted=len(props), n_eligible_in_bank=len(eligible), pool_bank_indices=order[: POOL - 1], witness_position=s % POOL)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    load_households(*BANK)  # cache before workers start
    od = out_dir("phase2/stage2")
    vids = [v.id for v in variants(a.year, stage2=True)]
    res = run_jobs(run, [(v, a.year) for v in vids], a.workers, checkpoint=od / "checkpoint.jsonl")
    for r in res:
        r["passes"] = bool(r["valid"] and r["length_ok"])
    (od / "manifest.json").write_text(json.dumps(res, indent=1, default=float))
    lines = ["# Stage 2 preparation\n", "| variant | valid | witness gain | closure gain | reduction | ≤2-move sequences | hits ≥ R | eligible in bank | passes |", "|---|---|---|---|---|---|---|---|---|"]
    for r in res:
        lines.append(f"| {r['variant']} | {r['valid']} | {r['witness_gain']:.0f} | {r['witness_gain_closure']:.0f} | {r['witness_reduction']:.2f} | {r['n_short']} | {len(r['short_hits'])} | {r['n_eligible_in_bank']} of {r['n_adapted']} adapted | {r['passes']} |")
    for r in res:
        if r["short_hits"]:
            lines.append(f"\n{r['variant']} short hits (first 10): {r['short_hits']}")
    write_json(od / "summary.json", {"meta": run_metadata(), "variants": [{k: v for k, v in r.items() if k != 'pool_bank_indices'} for r in res]})
    (od / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
