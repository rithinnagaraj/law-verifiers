"""E0.3 Verifier throughput benchmark.

Proposals evaluated per second (both calculators + reality check), by batch
size, with and without attribution. Each proposal = one household + one
random valid move.

    python experiments/e0_3_throughput.py --sizes 1 10 50 200 500
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from common import out_dir, run_metadata, write_json

from taxred.generate import random_households
from taxred.law import Law
from taxred.verifier import Verifier, VerifierConfig


def proposal(hh, rng):
    adults = [p for p in hh.people.values() if p.age >= 18]
    holders = [p for p in hh.people.values() if p.assets]
    if holders and len(hh.people) > 1:
        g = holders[0]
        r = next(p for p in hh.people.values() if p.id != g.id)
        return [{"op": "gift_asset", "giver": g.id, "recipient": r.id, "asset": g.assets[0].id, "fraction": 0.5}]
    w = [p for p in adults if p.hours > 0 and p.wages > 0]
    if w:
        return [{"op": "set_hours", "person": w[0].id, "hours": w[0].hours * 0.9}]
    return [{"op": "itemize_or_standard", "tax_unit": hh.tax_units[0].id, "itemize": True}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[1, 10, 50, 200])
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--attribution", action="store_true")
    args = ap.parse_args()
    rng = np.random.default_rng(0)
    law = Law(2024)
    v = Verifier(law, VerifierConfig(run_attribution=args.attribution))
    # Warm up: imports, system construction.
    hh = random_households(2, 99)
    v.evaluate_many([(h, proposal(h, rng)) for h in hh])
    rows = []
    for n in args.sizes:
        for rep in range(args.repeats):
            hhs = random_households(n, 1000 + rep)
            props = [(h, proposal(h, rng)) for h in hhs]
            t = time.perf_counter()
            verdicts = v.evaluate_many(props)
            dt = time.perf_counter() - t
            rows.append({"batch": n, "repeat": rep, "seconds": dt, "proposals_per_s": n / dt,
                         "labels": {l: sum(x.label == l for x in verdicts) for l in {x.label for x in verdicts}}})
            print(rows[-1], flush=True)
    od = out_dir("phase0/e0_3")
    name = "throughput_attr.json" if args.attribution else "throughput.json"
    write_json(od / name, {"meta": run_metadata(), "attribution": args.attribution, "rows": rows})


if __name__ == "__main__":
    main()
