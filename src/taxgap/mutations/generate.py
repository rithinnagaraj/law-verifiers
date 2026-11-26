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

`candidates_v2(seed)`: all v2 candidates (spike 1), operators round-robin, each
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
    ok = [p for p in ok if p.gen <= 2]  # v2 is frozen to its own catalog
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


def candidates_v2(seed: int = 0) -> list[Family]:
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


# --- generator v3 (G0 revision 1, 2026-11-25, before spike 2; DECISIONS.md) ---
#
# AND structures only: two parameters of one benefit, from different
# statutory subsections, each of which alone caps or denies the benefit.
#
#   eitc_gate      EITC investment-income limit (s.32(i)) x each EITC range
#                  parameter (max, phase-out start, phase-out rate; s.32(b)),
#                  0-3 children
#   eitc_age       childless-EITC min or max age (s.32(c)(1)(A)(ii)) x the
#                  childless range parameters (s.32(b))
#   ctc_phase_out  CTC or ODC amount (s.24(h)(2), (h)(4)) x CTC phase-out
#                  threshold (s.24(b), (h)(3)), each filing status
#   qbi_phase_in   two of QBI rate (s.199A(b)(2)), threshold (s.199A(e)(2)),
#                  phase-in range (s.199A(b)(3)(B)), each filing status
#
# Spike 1's candidates (v2) are excluded. Same selection as v2: operators
# round-robin, each operator's candidates in a seeded order.

OPERATORS_V3 = ("eitc_gate", "eitc_age", "ctc_phase_out", "qbi_phase_in")
MECHANISM_V3 = {"eitc_gate": "eitc_investment_test", "eitc_age": "eitc_age_test", "ctc_phase_out": "credit_phase_out", "qbi_phase_in": "qbi_phase_in"}
ALL_STATUSES = ("SINGLE", "JOINT", "SEPARATE", "HEAD_OF_HOUSEHOLD")


def _by_op_v3() -> dict[str, list]:
    ok, _ = verify()
    by = {p.key: p for p in ok}
    ops: dict[str, list] = {o: [] for o in OPERATORS_V3}

    def add(op, a, b):
        if a in by and b in by:
            ops[op].append((by[a], by[b]))

    for k in range(4):
        for x in (f"eitc_max{k}", f"eitc_ps{k}", f"eitc_prt{k}"):
            add("eitc_gate", "eitc_inv", x)
    for g in ("eitc_age_min", "eitc_age_max"):
        for x in ("eitc_max0", "eitc_ps0", "eitc_prt0"):
            add("eitc_age", g, x)
    for s in ALL_STATUSES:
        for a in ("ctc_amt", "odc"):
            add("ctc_phase_out", a, f"ctc_ps.{s}")
        for a, b in (("qbi_rt", f"qbi_thd.{s}"), ("qbi_rt", f"qbi_gap.{s}"), (f"qbi_thd.{s}", f"qbi_gap.{s}")):
            add("qbi_phase_in", a, b)
    return ops


def candidates_v3(seed: int = 0) -> list[Family]:
    excluded = {f.id.split(":", 1)[1] for f in candidates_v2(seed)[:10]}  # spike 1, stays rejected
    rng = np.random.default_rng(seed)
    lists = {}
    for op, pairs in _by_op_v3().items():
        fams = [Family(f"{op}:{a.key}+{b.key}", MECHANISM_V3[op], a, b, MAGNITUDES) for a, b in pairs if f"{a.key}+{b.key}" not in excluded]
        lists[op] = [fams[i] for i in rng.permutation(len(fams))]
    out = []
    for i in range(max((len(v) for v in lists.values()), default=0)):
        for op in OPERATORS_V3:
            if i < len(lists[op]):
                out.append(lists[op][i])
    return out


GENERATORS = {2: candidates_v2, 3: candidates_v3}


def candidates(seed: int = 0, gen: int = 3) -> list[Family]:
    """Candidates of generator `gen` (2: spike 1; 3: since G0 revision 1)."""
    return GENERATORS[gen](seed)


def all_families(seed: int = 0) -> dict[str, Family]:
    """Every candidate of every generator version, by id (for re-lookup)."""
    out: dict[str, Family] = {}
    for g in GENERATORS.values():
        out.update({f.id: f for f in g(seed)})
    return out


# --- generator v4 (G0 revision 2, 2026-11-26, before spike 3; DECISIONS.md) ---
#
# Spike 2's diagnosis: rescaling a parameter that ordinary households are
# near makes the mutation reachable in one move, so check 2 fails whatever
# the structure. v4 keeps the operator (two parameters from different
# provisions, both moved the tax-lowering way, x2 and x4) but draws from
# every cross-provision pair of the verified catalog, and screens each
# candidate, in a seeded order, with two necessary conditions of the gate
# (mutations/screen.py) before it is gated:
#   hidden  no one-move grid sequence on the 9 gate households is a match
#           under L at either magnitude (check 2's own test, minus the
#           witness household, which is not known yet)
#   alive   at both magnitudes, some reality-preserving two-move grid
#           sequence (sampled) on the witness households has gain > $50 and
#           an attributable gain >= $50 and >= 0.3 of its gain, and each
#           mutation alone < R of it (interacting; amended before spike 3)
# Spike 3 gates the first 10 candidates that pass the screen. Spike 1 and 2
# candidates stay rejected and are excluded.

GROUP = {
    "eitc": "eitc", "eitc_age": "eitc", "eitc_investment_limit": "eitc",
    "ctc": "child_credits", "actc": "child_credits", "odc": "child_credits",
    "qbi_rate": "qbi", "qbi_threshold": "qbi", "qbi_phase_in": "qbi",
    "amt": "amt", "capital_gains_rates": "investment_income", "niit": "investment_income",
    "dependent_std": "dependents", "standard_deduction": "rate_structure", "rate_brackets": "rate_structure",
    "salt_cap": "itemized",
}


def mechanism_v4(a: Param, b: Param) -> str:
    g = sorted({GROUP.get(a.provision, a.provision), GROUP.get(b.provision, b.provision)})
    return "+".join(g) if len(g) == 2 else f"within_{g[0]}"


def candidates_v4(seed: int = 0) -> list[Family]:
    excluded = {f.id.split(":", 1)[1] for g in (candidates_v2, candidates_v3) for f in g(seed)[:10]}  # spikes 1-2 stay rejected
    ok, _ = verify()
    ok = sorted(ok, key=lambda p: p.key)
    pairs = [(a, b) for a, b in itertools.combinations(ok, 2) if a.provision != b.provision
             and f"{a.key}+{b.key}" not in excluded and f"{b.key}+{a.key}" not in excluded]
    rng = np.random.default_rng(seed)
    return [Family(f"v4:{a.key}+{b.key}", mechanism_v4(a, b), a, b, MAGNITUDES) for a, b in (pairs[i] for i in rng.permutation(len(pairs)))]


GENERATORS[4] = candidates_v4


# --- generator v5 (G0 revision 3, 2026-11-26, before spike 3; DECISIONS.md) ---
#
# Beyond the plan's two G0 revisions; authorized by the user's grant of
# autonomy (2026-11-26) and logged as a plan deviation. Diagnosis: the v4
# screen passed 0 of 600 random cross-provision pairs (no pair with an
# interacting two-move sequence: random pairs act additively), while spike 2's
# AND pairs did yield interacting two-move witnesses whose failure was the old
# search (witnesses that change hours, labelled sacrifice). v5 returns to
# structures where each parameter alone caps or denies the benefit, keeps
# witness search v2, and drops the screen: every selected candidate is gated
# in full.
#
#   eitc_gate, eitc_age, ctc_phase_out, qbi_phase_in   v3's operators
#   amt_max      a regular-tax parameter x the AMT exemption or its phase-out
#                start, same filing status (s.55(a): tax = regular + the excess
#                of tentative minimum tax over regular, i.e. max(regular, TMT))
#   dep_std_cap  dependent standard-deduction earned-income add-on x the
#                single basic standard deduction (s.63(c)(5): min(basic,
#                max(floor, earned + add-on)))
#
# Operators round-robin, each in a seeded order; spike 1-2 candidates
# excluded. A candidate whose mutated law a calculator rejects (a bracket
# threshold scaled past the next one) is not a law: `valid_law` drops it at
# selection, before it is gated (a property of the law, not an outcome).

OPERATORS_V5 = (*OPERATORS_V3, "amt_max", "dep_std_cap")
MECHANISM_V5 = {**MECHANISM_V3, "amt_max": "regular_vs_amt", "dep_std_cap": "dependent_std_cap"}


def _by_op_v5() -> dict[str, list]:
    ops = {**_by_op_v3(), "amt_max": [], "dep_std_cap": []}
    ok, _ = verify()
    by = {p.key: p for p in ok}
    for s in ALL_STATUSES:
        for r in REGULAR:
            for a in AMT:
                if f"{r}.{s}" in by and f"{a}.{s}" in by:
                    ops["amt_max"].append((by[f"{r}.{s}"], by[f"{a}.{s}"]))
    if "dep_std_add" in by and "std.SINGLE" in by:
        ops["dep_std_cap"].append((by["dep_std_add"], by["std.SINGLE"]))
    return ops


def candidates_v5(seed: int = 0) -> list[Family]:
    excluded = {f.id.split(":", 1)[1] for g in (candidates_v2, candidates_v3) for f in g(seed)[:10]}  # spikes 1-2 stay rejected
    rng = np.random.default_rng(seed)
    lists = {}
    for op, pairs in _by_op_v5().items():
        fams = [Family(f"v5:{op}:{a.key}+{b.key}", MECHANISM_V5[op], a, b, MAGNITUDES) for a, b in pairs
                if f"{a.key}+{b.key}" not in excluded and f"{b.key}+{a.key}" not in excluded]
        lists[op] = [fams[i] for i in rng.permutation(len(fams))]
    out = []
    for i in range(max((len(v) for v in lists.values()), default=0)):
        for op in OPERATORS_V5:
            if i < len(lists[op]):
                out.append(lists[op][i])
    return out


GENERATORS[5] = candidates_v5


def valid_law(fam: Family) -> tuple[bool, str]:
    """Every law the gate builds (L, L1, L2, Lrev at both magnitudes) is
    accepted by Tax-Calculator in every horizon year."""
    import taxcalc as tc

    from ..config import HORIZON_START, HORIZON_YEARS

    for m in fam.magnitudes:
        for name, law in fam.laws(m).items():
            ref: dict = {}
            for y in range(HORIZON_START, HORIZON_START + HORIZON_YEARS):
                for k, v in law.tc_reform(y).items():
                    ref.setdefault(k, {}).update(v)
            if not ref:
                continue
            try:
                tc.Policy().implement_reform(ref)
            except Exception as e:  # noqa: BLE001 - only parameter validation is caught
                if type(e).__name__ != "ValidationError":
                    raise
                return False, f"{name}@{m:g}: {str(e)[:300]}"
    return True, ""
