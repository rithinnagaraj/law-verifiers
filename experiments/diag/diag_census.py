"""Diagnostic census (not an experiment; changes nothing in the gate).

After spike 3 triggered the plan's stop rule, this measures, for the next 20
valid v5 candidates in the seeded order (the first 20 A5b would have gated),
on the dense 416-household pool of diag_pool.py, at magnitude x2, over every
reality-preserving 1-2 move grid sequence:
  - households with an interacting sequence, and how many sequences;
  - one-move interacting sequences (any -> shallow under the counting rule);
  - households whose interacting sequences all need 2 moves.
Selection, pool and magnitude fixed before it ran (DECISIONS, 2026-11-27).
Writes ~/diag_census/census.jsonl, one row per family.
"""
import json, os, sys, time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import diag_pool2 as d2  # noqa: E402
from a5_catalog import valid_candidates  # noqa: E402

OUT = Path(os.path.expanduser("~/diag_census"))

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    m = 2.0
    fams = [f.id for f in valid_candidates(OUT, 30)[10:30]]
    json.dump(fams, open(OUT / "families.json", "w"), indent=1)
    done = {json.loads(l)["family"] for l in open(OUT / "census.jsonl")} if (OUT / "census.jsonl").exists() else set()
    t = time.time()
    print("families", fams, flush=True)
    with Pool(28) as p:
        for fid in fams:
            if fid in done:
                continue
            res = p.map(d2.work, [(fid, m, h) for h in d2.HH], chunksize=1)
            inter = {hid: f for hid, f in res if f}
            one = {hid: [x for x in f if x[0] == 1] for hid, f in inter.items()}
            deep = sorted(h for h, f in inter.items() if all(x[0] >= 2 for x in f))
            row = {
                "family": fid, "magnitude": m, "households": len(d2.HH),
                "households_interacting": len(inter),
                "sequences_interacting": sum(len(f) for f in inter.values()),
                "one_move_interacting": sum(len(v) for v in one.values()),
                "households_one_move": sorted(h for h, v in one.items() if v),
                "households_depth2_only": deep,
                "examples_depth2": [[h, max(inter[h], key=lambda x: x[2]["attr"])[1:]] for h in deep[:5]],
                "examples_one_move": [[h, v[0][1:]] for h, v in list(one.items()) if v][:3],
                "seconds": round(time.time() - t),
            }
            with open(OUT / "census.jsonl", "a") as fh:
                fh.write(json.dumps(row) + "\n")
            print(f"== {fid}: interacting households {row['households_interacting']}, sequences {row['sequences_interacting']}, "
                  f"one-move {row['one_move_interacting']}, depth-2-only households {len(deep)}, {row['seconds']}s", flush=True)
