"""Evaluate households under a Law with one engine, including rules this
package implements on top of the calculators (the kiddie tax).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, Sequence

from .engines import ENGINES, UnitResult
from .household import Asset, FilingUnit, Household, compile_filing_units
from .law import KiddieTaxRule, Law


@dataclass
class HouseholdResult:
    household_id: str
    engine: str
    fed_income_tax: float
    other_tax: float
    benefits: Optional[float]  # None when the engine models no benefits
    units: list[UnitResult] = field(default_factory=list)
    kiddie_adjustment: float = 0.0  # included in fed_income_tax

    @property
    def total_tax(self) -> float:
        return self.fed_income_tax + self.other_tax

    @property
    def net_resources(self) -> float:
        """Benefits minus taxes (pre-tax resources are handled by the reality check)."""
        return (self.benefits or 0.0) - self.total_tax


@lru_cache(maxsize=32)
def dependent_std_floor(year: int) -> float:
    p = _pe_params()
    return float(p.gov.irs.deductions.standard.dependent.amount(f"{year}-01-01"))


@lru_cache(maxsize=1)
def _pe_params():
    from .engines import _pe_system

    return _pe_system(()).parameters


def kiddie_applies(rule: KiddieTaxRule, age: int, is_student: bool) -> bool:
    if not rule.enabled:
        return False
    if age < rule.age_under:
        return True
    return bool(is_student and rule.student_age_under and age < rule.student_age_under)


def _scaled_person(p, keep_share: float):
    q = copy.deepcopy(p)
    for a in q.assets:
        a.value *= keep_share
        a.basis *= keep_share
    q.long_term_gains *= keep_share
    return q


def _parent_plus_nui(parent: FilingUnit, child_people: list, nui_shares: list[float]) -> FilingUnit:
    """Parent's return with the children's net unearned income added, by character."""
    fu = copy.deepcopy(parent)
    head = next(m for m in fu.members if m.role == "HEAD")
    for child, share in zip(child_people, nui_shares):
        if share <= 0:
            continue
        head.person.assets.append(
            Asset(f"__nui_int_{child.id}", child.taxable_interest * share, child.taxable_interest * share, interest_yield=1.0)
        )
        head.person.assets.append(
            Asset(
                f"__nui_qd_{child.id}",
                child.qualified_dividends * share,
                child.qualified_dividends * share,
                qualified_dividend_yield=1.0,
            )
        )
        head.person.long_term_gains += child.long_term_gains * share
    fu.id = parent.id + ":+nui"
    return fu


def apply_kiddie_tax(
    units: Sequence[FilingUnit], results: dict[str, UnitResult], law: Law, engine
) -> dict[str, float]:
    """Return {child unit id: additional tax} under law.kiddie (Form 8615).

    For each claiming (parent) unit, the children subject to the rule have
    their net unearned income (NUI) combined; the parent's regular tax on
    (taxable income + total NUI) minus the parent's regular tax is allocated
    to children pro rata (Form 8615 lines 9-13). Each child then owes
    max(regular tax on TI - NUI at child's rates + allocated parental tax,
        child's original regular tax + AMT).
    """
    rule = law.kiddie
    if not rule.enabled:
        return {}
    floor2 = rule.allowance_multiple * dependent_std_floor(units[0].year)
    by_id = {u.id: u for u in units}
    groups: dict[str, list[tuple[FilingUnit, float]]] = {}
    for fu in units:
        if not fu.is_dependent_filer:
            continue
        child = fu.head
        if not kiddie_applies(rule, child.age, child.is_student):
            continue
        r = results[fu.id]
        nui = min(max(child.unearned_income - floor2, 0.0), max(r.taxable_income, 0.0))
        if nui > 0:
            groups.setdefault(fu.claimed_by, []).append((fu, nui))
    if not groups:
        return {}

    variants: list[FilingUnit] = []
    plan = []
    for parent_id, kids in groups.items():
        parent = by_id[parent_id]
        shares = [nui / fu.head.unearned_income for fu, nui in kids]
        pv = _parent_plus_nui(parent, [fu.head for fu, _ in kids], shares)
        variants.append(pv)
        kid_variants = []
        for (fu, nui), share in zip(kids, shares):
            cv = copy.deepcopy(fu)
            cv.members[0].person = _scaled_person(fu.head, 1.0 - share)
            cv.id = fu.id + ":-nui"
            variants.append(cv)
            kid_variants.append(cv)
        plan.append((parent, pv, kids, kid_variants))

    vres = {r.unit_id: r for r in engine.evaluate_units(variants, law)}
    adjustments: dict[str, float] = {}
    for parent, pv, kids, kid_variants in plan:
        parental_tax = max(vres[pv.id].regular_tax - results[parent.id].regular_tax, 0.0)
        total_nui = sum(n for _, n in kids)
        for (fu, nui), cv in zip(kids, kid_variants):
            allocated = parental_tax * nui / total_nui
            kiddie_regular = vres[cv.id].regular_tax + allocated
            orig = results[fu.id]
            orig_pre_credit = orig.regular_tax + orig.amt
            new_pre_credit = max(kiddie_regular, orig_pre_credit)
            adjustments[fu.id] = new_pre_credit - orig_pre_credit
    return adjustments


def evaluate_households(
    households: Sequence[Household], law: Law, engine_name: str = "policyengine", with_benefits: bool = True
) -> list[HouseholdResult]:
    if not households:
        return []
    years = {h.year for h in households}
    if len(years) != 1:
        raise ValueError("evaluate_households: one tax year per batch")
    engine = ENGINES[engine_name]()
    law_year = law.year
    if law_year != households[0].year:
        raise ValueError(f"law year {law_year} != household year {households[0].year}")
    units_per_hh = [compile_filing_units(h) for h in households]
    all_units = [u for us in units_per_hh for u in us]
    results = {r.unit_id: r for r in engine.evaluate_units(all_units, law)}
    adjustments = apply_kiddie_tax(all_units, results, law, engine)
    benefits = engine.evaluate_benefits(households, law) if with_benefits else None
    out = []
    for i, (h, us) in enumerate(zip(households, units_per_hh)):
        ur = [results[u.id] for u in us]
        adj = sum(adjustments.get(u.id, 0.0) for u in us)
        out.append(
            HouseholdResult(
                household_id=h.id,
                engine=engine.name,
                fed_income_tax=sum(r.fed_income_tax for r in ur) + adj,
                other_tax=sum(r.other_tax for r in ur),
                benefits=None if benefits is None else float(benefits[i]),
                units=ur,
                kiddie_adjustment=adj,
            )
        )
    return out
