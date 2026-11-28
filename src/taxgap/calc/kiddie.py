"""Form 8615 (kiddie tax), implemented in this package for both calculators.

Neither calculator applies Form 8615 to a dependent filer in the way the
verifier needs, so this module computes it on top of each calculator's own
regular tax. Because the code is shared, gains that come from it are tagged
`shared-code` by the verifier: the cross-check cannot vouch for them.

For each claiming (parent) return, the children subject to the rule have
their net unearned income (NUI) combined; the parent's regular tax on
(taxable income + total NUI) minus the parent's regular tax is allocated to
the children pro rata (Form 8615 lines 9-13). Each child then owes
max(regular tax on TI - NUI at the child's rates + allocated parental tax,
the child's own regular tax + AMT). Variants keep the SALT of the return
they derive from (the parent's itemized deductions do not change).
"""

from __future__ import annotations

import copy
from functools import lru_cache
from typing import Callable, Sequence

from ..law import Law
from ..model import UNEARNED_OTHER, Asset, Return
from ..params import pe_value
from . import ReturnResult

FLOOR_PATH = "gov.irs.deductions.standard.dependent.amount"


def floor(law: Law, year: int) -> float:
    """The s.63(c)(5)(A) amount; values >= 100,000 are the 'no dependent
    limit' switch of the dependent_std_limit provision, not a floor."""
    v = law.pe_param(FLOOR_PATH, year)
    return float(v) if v < 100_000 else pe_value(FLOOR_PATH, year)


@lru_cache(maxsize=32)
def earned_threshold(year: int) -> float:
    """E of the hand-authored pilot 2: the single basic standard deduction."""
    return pe_value("gov.irs.deductions.standard.amount.SINGLE", year)


def applies(law: Law, age: int, is_student: bool) -> bool:
    k = law.kiddie
    if not k.enabled:
        return False
    if age < k.age_under:
        return True
    return bool(is_student and k.student_age_under and age < k.student_age_under)


def _scaled(p, keep: float):
    q = copy.deepcopy(p)
    for a in q.assets:
        a.value *= keep
        a.basis *= keep
    q.ltcg *= keep
    for k in UNEARNED_OTHER:
        if k in q.other:
            q.other[k] *= keep
    return q


def _exempt(child, share: float):
    """The child with `share` of its realized long-term gains left out (the
    planted ltcg_exempt flaw); the child itself when share is 0."""
    if share <= 0 or child.ltcg <= 0:
        return child
    q = copy.deepcopy(child)
    q.ltcg *= 1.0 - share
    return q


def _parent_plus(parent: Return, kids: list, shares: list[float]) -> Return:
    v = copy.deepcopy(parent)
    v.key = parent.key + "+nui"
    head = next(m for m in v.members if m.role == "HEAD").person
    for child, share in zip(kids, shares):
        if child.interest:
            head.assets.append(Asset(f"__nui_i_{child.id}", child.interest * share, child.interest * share, interest_yield=1.0))
        if child.dividends:
            head.assets.append(Asset(f"__nui_d_{child.id}", child.dividends * share, child.dividends * share, dividend_yield=1.0))
        head.ltcg += child.ltcg * share
        for k in UNEARNED_OTHER:
            if child.other.get(k):
                head.other[k] = head.other.get(k, 0.0) + child.other[k] * share
    return v


def adjustments(
    returns: Sequence[Return],
    results: dict[str, ReturnResult],
    law: Law,
    evaluate: Callable[[list[Return], dict], dict[str, ReturnResult]],
    salt: dict,
) -> dict[str, float]:
    """{child return key: additional tax}. `evaluate(returns, salt)` runs the
    calculator under `law`; `salt` maps return keys to their SALT."""
    if not law.kiddie.enabled or not returns:
        return {}
    allow = law.kiddie.allowance_multiple * floor(law, returns[0].year)
    by_key = {r.key: r for r in returns}
    groups: dict[str, list[tuple[Return, float]]] = {}
    for r in returns:
        if r.claimed_by is None:
            continue
        child = r.head
        if not applies(law, child.age, child.is_student):
            continue
        kr = law.kiddie
        eff = _exempt(child, kr.ltcg_exempt if (not kr.exempt_if_earned or child.earned_income >= earned_threshold(r.year)) else 0.0)
        off = kr.earned_offset * max(child.earned_income, 0.0)
        nui = min(max(eff.unearned_income - allow - off, 0.0), max(results[r.key].taxable_income, 0.0))
        if nui > 0:
            groups.setdefault(r.claimed_by, []).append((r, nui, eff))
    if not groups:
        return {}
    variants: list[Return] = []
    vsalt: dict = {}
    plan = []
    for parent_key, kids in groups.items():
        parent = by_key[parent_key]
        shares = [nui / eff.unearned_income for _, nui, eff in kids]
        pv = _parent_plus(parent, [eff for _, _, eff in kids], shares)
        variants.append(pv)
        vsalt[pv.key] = salt.get(parent.key, 0.0)
        kvs = []
        for (r, _, eff), share in zip(kids, shares):
            cv = copy.deepcopy(r)
            cv.key = r.key + "-nui"
            cv.members[0].person = _scaled(eff, 1.0 - share)
            cv.members[0].person.ltcg += r.head.ltcg - eff.ltcg  # exempt gains stay at the child's rates
            variants.append(cv)
            vsalt[cv.key] = salt.get(r.key, 0.0)
            kvs.append(cv)
        plan.append((parent, pv, kids, kvs))
    vres = evaluate(variants, vsalt)
    out: dict[str, float] = {}
    for parent, pv, kids, kvs in plan:
        parental = max(vres[pv.key].regular_tax - results[parent.key].regular_tax, 0.0)
        total = sum(n for _, n, _ in kids)
        for (r, nui, _), cv in zip(kids, kvs):
            kiddie_regular = vres[cv.key].regular_tax + parental * nui / total
            orig = results[r.key]
            before = orig.regular_tax + orig.amt
            out[r.key] = max(kiddie_regular, before) - before
    return out
