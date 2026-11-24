"""Candidate interaction families from the verified parameter catalog.

Operators (each moves two parameters from different provisions, both in the
direction that lowers tax):

  status_pair    two provisions' parameters for the same filing status S in
                 {SEPARATE, HEAD_OF_HOUSEHOLD, SINGLE} (decouples that status
                 from its coordination with the others)
  status_child   a status-specific parameter with a dependent/child scalar
                 (CTC, ACTC, ODC, EITC, dependent standard deduction)
  scalar_pair    two scalars from different provisions (two linked tests)

Mechanism class (for the split by mechanism): filing_status for the status
operators on SEPARATE / HEAD_OF_HOUSEHOLD, income_shifting where a
parameter governs a child's or single filer's own return (dependent
standard deduction, SINGLE status, capital-gains brackets), phase_out
where a phase-out or credit amount is involved, threshold otherwise.

`candidates(seed)` returns all candidates in a seeded random order; the
spike takes the first 10, the main catalog the next ones.
"""

from __future__ import annotations

import itertools

import numpy as np

from .catalog import Param, verify
from .family import Family

STATUSES = ("SEPARATE", "HEAD_OF_HOUSEHOLD", "SINGLE")
CHILD_SCALARS = ("ctc_amt", "actc_rt", "actc_thd", "odc", "eitc_inv", "dep_std", "dep_std_add", "eitc_max1", "eitc_max2", "eitc_max3")
OTHER_SCALARS = ("niit_rt",)
PHASE = ("ctc", "actc", "amt", "eitc", "eitc_investment_limit", "odc")
SHIFT = ("dependent_std", "capital_gains_rates")


def mechanism(op: str, a: Param, b: Param) -> str:
    provs = {a.provision, b.provision}
    if op in ("status_pair", "status_child") and (a.status in ("SEPARATE", "HEAD_OF_HOUSEHOLD") or b.status in ("SEPARATE", "HEAD_OF_HOUSEHOLD")):
        return "filing_status"
    if provs & set(SHIFT) or a.status == "SINGLE" or b.status == "SINGLE":
        return "income_shifting"
    if provs & set(PHASE):
        return "phase_out"
    return "threshold"


def candidates(seed: int = 0) -> list[Family]:
    ok, _ = verify()
    by_key = {p.key: p for p in ok}
    out = []
    for s in STATUSES:
        ps = [p for p in ok if p.status == s]
        for a, b in itertools.combinations(ps, 2):
            if a.provision != b.provision:
                out.append(("status_pair", a, b))
        for a in ps:
            for c in CHILD_SCALARS:
                if c in by_key and by_key[c].provision != a.provision:
                    out.append(("status_child", a, by_key[c]))
    scal = [by_key[c] for c in CHILD_SCALARS + OTHER_SCALARS if c in by_key]
    for a, b in itertools.combinations(scal, 2):
        if a.provision != b.provision:
            out.append(("scalar_pair", a, b))
    fams = [Family(f"{op}:{a.key}+{b.key}", mechanism(op, a, b), a, b) for op, a, b in out]
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(fams))
    return [fams[i] for i in order]
