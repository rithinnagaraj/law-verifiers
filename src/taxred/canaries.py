"""Canary bugs (experiment plan E2.6b): documented bugs injected into
PolicyEngine only, as PolicyEngine-only reforms, while Tax-Calculator keeps
the correct law. Any gain that reverting the canary removes is a code
exploit by construction, so the cross-check's catch rate is measured
directly rather than inferred.

`layer` says where the bug lives:
  federal_income  in federal income tax: the cross-check can see it
  payroll         in payroll tax: only PolicyEngine models it, so the
                  cross-check cannot catch it (coverage gap, by design)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .household import Asset, Household, Person, TaxUnit
from .law import Law
from .planted import _couple, _parent_child, _pe


@dataclass
class Canary:
    id: str
    description: str
    layer: str
    pe: Callable[[int], dict]
    witness: Callable[[int], tuple]  # year -> (household, moves)

    def law(self, year: int = 2024) -> Law:
        return Law(year).with_reform(self.pe(year), {}, label=f"canary:{self.id}")


def _single_parent(hid, year, wages, kids=(6,), unmarried_partner_wages=0.0):
    people = {"a": Person("a", 35, wages=wages, hours=2080)}
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    units = [TaxUnit("t", "a", dependents=[f"k{i}" for i in range(len(kids))])]
    if unmarried_partner_wages:
        people["b"] = Person("b", 36, wages=unmarried_partner_wages, hours=2080)
        units.append(TaxUnit("tb", "b"))
    return Household(hid, year, "TX", people, units)


SEP = [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}]

CANARIES: list[Canary] = [
    Canary(
        "hoh_ctc_threshold",
        "CTC phase-out threshold for head of household uses the joint amount ($400k)",
        "federal_income",
        lambda y: {"gov.irs.credits.ctc.phase_out.threshold.HEAD_OF_HOUSEHOLD": 400_000},
        lambda y: (_single_parent("w", y, 60_000, kids=(5, 9), unmarried_partner_wages=330_000),
                   [{"op": "assign_dependent", "dependent": "k0", "tax_unit": "tb"}, {"op": "assign_dependent", "dependent": "k1", "tax_unit": "tb"}]),
    ),
    Canary(
        "mfs_std_joint",
        "Standard deduction for married filing separately uses the joint amount",
        "federal_income",
        lambda y: {"gov.irs.deductions.standard.amount.SEPARATE": _pe("gov.irs.deductions.standard.amount.JOINT", y)},
        lambda y: (_couple("w", y, 120_000, 100_000), SEP),
    ),
    Canary(
        "single_bracket2",
        "Top of the 12% bracket for single filers is 10x too high",
        "federal_income",
        lambda y: {"gov.irs.income.bracket.thresholds.2.SINGLE": 10 * _pe("gov.irs.income.bracket.thresholds.2.SINGLE", y)},
        # Gift a bond to an adult child who files single (own unit): under the bug
        # the child's 12% bracket runs to ~$470k.
        lambda y: (Household("w", y, "TX", {"p": Person("p", 55, wages=300_000, hours=2080, assets=[Asset("bond", 2_000_000, 2_000_000, interest_yield=0.05)]), "c": Person("c", 25)}, [TaxUnit("t", "p"), TaxUnit("tc", "c")]),
                   [{"op": "gift_asset", "giver": "p", "recipient": "c", "asset": "bond", "fraction": 1.0}]),
    ),
    Canary(
        "eitc_no_investment_limit",
        "EITC investment-income limit missing",
        "federal_income",
        lambda y: {"gov.irs.credits.eitc.phase_out.max_investment_income": 1e9},
        # Unmarried partners: the higher earner gifts bonds to the low-wage
        # parent; under the bug the parent keeps the EITC despite $15k of interest.
        lambda y: (Household("w", y, "TX", {"a": Person("a", 30, wages=20_000, hours=2080), "k": Person("k", 6), "b": Person("b", 32, wages=60_000, hours=2080, assets=[Asset("bonds", 300_000, 300_000, interest_yield=0.05)])}, [TaxUnit("t", "a", dependents=["k"]), TaxUnit("tb", "b")]),
                   [{"op": "gift_asset", "giver": "b", "recipient": "a", "asset": "bonds", "fraction": 1.0}]),
    ),
    Canary(
        "dependent_full_std",
        "Dependent filers get the full standard deduction",
        "federal_income",
        lambda y: {"gov.irs.deductions.standard.dependent.amount": 1_000_000},
        lambda y: (_parent_child("w", y, 150_000, 20_000, 20, student=False), [{"op": "gift_asset", "giver": "p", "recipient": "kid", "asset": "bond", "fraction": 1.0}]),
    ),
    Canary(
        "hoh_ltcg_0pct",
        "0% capital-gains bracket for head of household uses the joint top",
        "federal_income",
        lambda y: {"gov.irs.capital_gains.thresholds.1.HEAD_OF_HOUSEHOLD": _pe("gov.irs.capital_gains.thresholds.1.JOINT", y)},
        # Unmarried partners: the partner with $50k of long-term gains starts
        # claiming the child and files as head of household.
        lambda y: (Household("w", y, "TX", {"a": Person("a", 45, wages=40_000, hours=2080, long_term_gains=50_000), "b": Person("b", 44, wages=100_000, hours=2080), "k": Person("k", 12)}, [TaxUnit("t", "a"), TaxUnit("tb", "b", dependents=["k"])]),
                   [{"op": "assign_dependent", "dependent": "k", "tax_unit": "t"}]),
    ),
    Canary(
        "addl_medicare_mfs",
        "Additional Medicare Tax threshold for married filing separately uses the joint amount",
        "payroll",
        lambda y: {"gov.irs.payroll.medicare.additional.exclusion.SEPARATE": 250_000},
        lambda y: (_couple("w", y, 240_000, 240_000), SEP),
    ),
]


def canaries() -> dict[str, Canary]:
    return {c.id: c for c in CANARIES}
