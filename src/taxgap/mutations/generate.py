"""Candidate interaction families from the verified parameter catalog.

The gate's ablation check (each mutation alone < R of the gain on the
witness) cannot pass when two mutations act additively: on the witness,
each one alone then moves the gain by its full share. Interactions need a
max/min structure in the tax computation, where loosening one constraint
does nothing while the other binds. The operators target such structures
first (design note, 2026-11-24, after a one-candidate smoke test of the
first, structure-blind generator; before the A5a spike):

  amt_pair      regular-tax parameter x AMT parameter for the same filing
                status (tax = max(regular, tentative minimum tax))
  eitc_pair     EITC investment-income limit x EITC phase-out (start or
                rate, by number of children): two tests of one credit
  status_pair   two provisions' parameters for the same filing status
  status_child  a status parameter x a child/dependent scalar
  scalar_pair   two scalars from different provisions

Statuses: SEPARATE, HEAD_OF_HOUSEHOLD, SINGLE (a household can move into
them). Both parameters move in the direction that lowers tax, by the
family's magnitudes (x2 and x4).

`candidates(seed)`: all candidates, operators taken round-robin, each
operator's candidates in a seeded random order. The spike takes the first
10, the main catalog the next ones.
"""

from __future__ import annotations

import itertools

import numpy as np

from .catalog import Param, verify
from .family import Family

STATUSES = ("SEPARATE", "HEAD_OF_HOUSEHOLD", "SINGLE")
REGULAR = ("std", "brk1", "brk2", "brk3", "brk4", "brk5", "brk6", "cg0", "cg15")
AMT = ("amt_em", "amt_ps")
CHILD_SCALARS = ("ctc_amt", "actc_rt", "actc_thd", "odc", "dep_std", "dep_std_add", "eitc_max1", "eitc_max2", "eitc_max3")
OPERATORS = ("amt_pair", "eitc_pair", "status_pair", "status_child", "scalar_pair")
MAGNITUDES = (2.0, 4.0)


def mechanism(op: str, a: Param, b: Param) -> str:
    if op == "amt_pair":
        return "regular_vs_amt"
    if op == "eitc_pair":
        return "eitc_tests"
    if a.status in ("SEPARATE", "HEAD_OF_HOUSEHOLD") or b.status in ("SEPARATE", "HEAD_OF_HOUSEHOLD"):
        return "filing_status"
    if {a.provision, b.provision} & {"dependent_std", "capital_gains_rates"} or "SINGLE" in (a.status, b.status):
        return "income_shifting"
    return "phase_out"


def _by_op() -> dict[str, list]:
    ok, _ = verify()
    by = {p.key: p for p in ok}
    ops: dict[str, list] = {o: [] for o in OPERATORS}
    for s in STATUSES:
        for r in REGULAR:
            for a in AMT:
                if f"{r}.{s}" in by and f"{a}.{s}" in by:
                    ops["amt_pair"].append((by[f"{r}.{s}"], by[f"{a}.{s}"]))
        ps = [p for p in ok if p.status == s]
        for a, b in itertools.combinations(ps, 2):
            if a.provision != b.provision and not ({a.provision, b.provision} == {"amt"} or "amt" in (a.provision, b.provision) and ({a.key.split(".")[0], b.key.split(".")[0]} & set(REGULAR))):
                ops["status_pair"].append((a, b))
        for a in ps:
            for c in CHILD_SCALARS:
                if c in by and by[c].provision != a.provision:
                    ops["status_child"].append((a, by[c]))
    for k in range(4):
        for x in (f"eitc_ps{k}", f"eitc_prt{k}"):
            if "eitc_inv" in by and x in by:
                ops["eitc_pair"].append((by["eitc_inv"], by[x]))
    scal = [by[c] for c in CHILD_SCALARS + ("niit_rt",) if c in by]
    for a, b in itertools.combinations(scal, 2):
        if a.provision != b.provision:
            ops["scalar_pair"].append((a, b))
    return ops


def candidates(seed: int = 0) -> list[Family]:
    rng = np.random.default_rng(seed)
    lists = {}
    for op, pairs in _by_op().items():
        fams = [Family(f"{op}:{a.key}+{b.key}", mechanism(op, a, b), a, b, MAGNITUDES) for a, b in pairs]
        lists[op] = [fams[i] for i in rng.permutation(len(fams))]
    out = []
    for i in range(max(len(v) for v in lists.values())):
        for op in OPERATORS:
            if i < len(lists[op]):
                out.append(lists[op][i])
    return out
