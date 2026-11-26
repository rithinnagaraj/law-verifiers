"""A5 positive controls: real loopholes that Congress later closed.

Purpose (DECISIONS.md, 2026-11-26, set before this script was run): check
that the A5 machinery (search, verifier, depth logic, gate) recognizes
loopholes known to have existed, before G0 revision 2 is chosen. Each control
is current law with one or two historical closures undone:

  pre1986   TRA 1986 closed income shifting to children twice: the kiddie
            tax (Form 8615) and the limit on a dependent's standard
            deduction. L = both undone; L1, L2 = each undone alone.
  pre2006   before TIPRA 2005 the kiddie tax applied under age 14 only.
  pre2008   before SBWOTA 2007: under 18, no full-time-student extension.
  pre1996   before the 1995 Act there was no EITC investment-income limit.

For each control:
  1. exhaustive one-move grid on the 30 witness households (moves that keep
     the household's real income, hours and wealth): matches under L by
     PolicyEngine (gain > $50, attributable >= $50 and >= R of the gain),
     then the full verifier on the 25 largest
  2. 1,500 random two-move grid sequences, same test
  3. pre1986 only: the A5 gate, unchanged (family.gate), with
     Lrev = current law
Nothing here changes the gate or the generator.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from multiprocessing import Pool

import numpy as np

from taxgap.config import results_dir
from taxgap.law import CURRENT_LAW, KiddieRule

R, FLOOR = 0.1, 50.0


def laws(name: str) -> dict:
    if name == "pre1986":
        return {"L": CURRENT_LAW.without("kiddie_tax", "dependent_std_limit"), "L1": CURRENT_LAW.without("kiddie_tax"),
                "L2": CURRENT_LAW.without("dependent_std_limit"), "Lrev": CURRENT_LAW}
    if name == "pre2006":
        L = replace(CURRENT_LAW, kiddie=KiddieRule(age_under=14, student_age_under=None), label="kiddie tax under 14")
    elif name == "pre2008":
        L = replace(CURRENT_LAW, kiddie=KiddieRule(age_under=18, student_age_under=None), label="kiddie tax under 18, no students")
    elif name == "pre1996":
        L = CURRENT_LAW.without("eitc_investment_limit")
    else:
        raise KeyError(name)
    return {"L": L, "L1": L, "L2": CURRENT_LAW, "Lrev": CURRENT_LAW}


CONTROLS = ("pre1986", "pre2006", "pre2008", "pre1996")


class Control:
    """Duck-typed stand-in for mutations.family.Family (gate() needs id and laws)."""

    def __init__(self, name):
        self.id, self.magnitudes = f"control:{name}", (1.0,)
        self._laws = laws(name)

    def laws(self, m):
        return self._laws


def _work(task):
    hi, k, n_rand = task
    from taxgap.archetypes import witness_archetypes
    from taxgap.grid import sequences
    from taxgap.verifier import Config, _reality, prepare

    hh = witness_archetypes()[hi]
    seqs = list(sequences(hh, k))
    if n_rand and len(seqs) > n_rand:
        idx = np.random.default_rng([hi, k]).choice(len(seqs), n_rand, replace=False)
        seqs = [seqs[i] for i in sorted(idx)]
    cfg = Config()
    return hi, [s for s in seqs if _reality(prepare(hh, s), cfg)[0]]


def _scan(name: str, seqs_by_hh: dict) -> dict:
    from taxgap.archetypes import witness_archetypes
    from taxgap.mutations.family import _pe_gains
    from taxgap.verifier import Verifier

    pool = witness_archetypes()
    lw = laws(name)
    props = [(pool[hi], s) for hi, ss in seqs_by_hh.items() for s in ss]
    g0 = _pe_gains(props, CURRENT_LAW)
    gl = _pe_gains(props, lw["L"])
    g1 = _pe_gains(props, lw["L1"])
    g2 = _pe_gains(props, lw["L2"])
    hits = [(b - a, i) for i, (a, b) in enumerate(zip(g0, gl)) if b == b and b > FLOOR and b - a >= FLOOR and b - a >= R * b]
    hits.sort(reverse=True)
    top = hits[:25]
    vs = Verifier(lw["L"]).evaluate([props[i] for _, i in top]) if top else []
    ex = []
    for (at, i), v in zip(top, vs):
        hh, s = props[i]
        ex.append({"hh": hh.id, "moves": s, "label": v.label, "gain": round(v.gain), "gain_tc": round(v.gain_tc), "attr": round(at),
                   "alone1": round(g1[i] - g0[i]), "alone2": round(g2[i] - g0[i]), "coverage": v.coverage,
                   "circumvents": {p: round(x, 2) for p, x in v.attribution.items() if x >= 0.2}})
    return {"n": len(props), "pe_matches": len(hits), "households": sorted({props[i][0].id for _, i in hits}),
            "verified_candidates": sum(e["label"] == "candidate" for e in ex), "labels": dict(__import__("collections").Counter(e["label"] for e in ex)),
            "examples": ex[:6]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", default=",".join(CONTROLS))
    ap.add_argument("--two", type=int, default=50, help="random two-move sequences per household")
    ap.add_argument("--no-gate", action="store_true")
    a = ap.parse_args()
    d = results_dir("a5")
    out_path = d / "controls.jsonl"
    t = time.time()
    with Pool(30) as p:
        one = dict(p.map(_work, [(hi, 1, 0) for hi in range(30)]))
        two = dict(p.map(_work, [(hi, 2, a.two) for hi in range(30)]))
    print(f"grid ready {time.time()-t:.0f}s: one-move {sum(map(len, one.values()))}, two-move {sum(map(len, two.values()))}", file=sys.stderr, flush=True)
    for name in a.controls.split(","):
        r = {"control": name, "one_move": _scan(name, one), "two_move": _scan(name, two)}
        if name == "pre1986" and not a.no_gate:
            from taxgap.mutations.family import gate
            r["gate"] = gate(Control(name), 1.0, np.random.default_rng(1986))
        with open(out_path, "a") as f:
            f.write(json.dumps(r, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
        print(name, json.dumps({k: (v if k == "gate" else {q: v[q] for q in ("n", "pe_matches", "verified_candidates", "labels")}) for k, v in r.items() if k != "control"}, default=str)[:1500], flush=True)
        print(f"  {time.time()-t:.0f}s", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
