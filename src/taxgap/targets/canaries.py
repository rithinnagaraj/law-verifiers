"""Canary bugs: documented bugs injected into PolicyEngine only, while
Tax-Calculator keeps current law. A gain that reverting the canary removes
is a code exploit by construction, so the cross-check's catch rate is
measured directly. Each has a witness (household + moves) that exploits it.

`layer`: federal_income (the cross-check can see it) or payroll (outside
the federal gain; only PolicyEngine models it).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..law import CURRENT_LAW, Change, Law
from ..model import Asset, Household, Person, TaxUnit
from ..params import pe_value

_STD = "gov.irs.deductions.standard.amount"


@dataclass(frozen=True)
class Canary:
    id: str
    description: str
    layer: str
    change: Callable[[], tuple]
    witness: Callable[[], tuple]  # () -> (household, moves)

    def law(self) -> Law:
        return CURRENT_LAW.plus(*self.change(), label=f"canary:{self.id}")


def _couple(w1, w2, kids=(), hid="w"):
    people = {"a": Person("a", 45, wages=w1, hours=2080 if w1 else 0), "b": Person("b", 43, wages=w2, hours=2080 if w2 else 0)}
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    return Household(hid, 2024, "TX", people, [TaxUnit("t", "a", "b", [f"k{i}" for i in range(len(kids))])], [("a", "b")]).with_futures()


def _hh(people: dict, units: list, pairs=()) -> Household:
    return Household("w", 2024, "TX", people, units, list(pairs)).with_futures()


SEP = [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}]

CANARIES = [
    Canary(
        "hoh_ctc_threshold",
        "CTC phase-out threshold for head of household is the joint amount ($400k)",
        "federal_income",
        lambda: (Change("gov.irs.credits.ctc.phase_out.threshold.HEAD_OF_HOUSEHOLD", kind="set", value=400_000.0),),
        lambda: (
            _hh({"a": Person("a", 35, wages=60_000, hours=2080), "k0": Person("k0", 5), "k1": Person("k1", 9), "b": Person("b", 36, wages=330_000, hours=2080)},
                [TaxUnit("t", "a", dependents=["k0", "k1"]), TaxUnit("tb", "b")]),
            [{"op": "assign_dependent", "dependent": "k0", "tax_unit": "tb"}, {"op": "assign_dependent", "dependent": "k1", "tax_unit": "tb"}, {"op": "set_filing_status", "tax_unit": "tb", "status": "HEAD_OF_HOUSEHOLD"}],
        ),
    ),
    Canary(
        "mfs_std_joint",
        "Standard deduction for married filing separately is the joint amount",
        "federal_income",
        lambda: (Change(f"{_STD}.SEPARATE", kind="copy", pe_src=f"{_STD}.JOINT"),),
        lambda: (_couple(120_000, 100_000), SEP),
    ),
    Canary(
        "single_bracket2",
        "Top of the 12% bracket for single filers is 10x too high",
        "federal_income",
        lambda: (Change("gov.irs.income.bracket.thresholds.2.SINGLE", kind="scale", value=10.0),),
        lambda: (
            _hh({"p": Person("p", 55, wages=300_000, hours=2080, assets=[Asset("bond", 2_000_000, 2_000_000, interest_yield=0.05)]), "s": Person("s", 54), "c": Person("c", 25)},
                [TaxUnit("t", "p", "s"), TaxUnit("tc", "c")], [("p", "s")]),
            [{"op": "gift_asset", "giver": "p", "recipient": "c", "asset": "bond", "fraction": 1.0}],
        ),
    ),
    Canary(
        "eitc_no_investment_limit",
        "EITC investment-income limit missing",
        "federal_income",
        lambda: (Change("gov.irs.credits.eitc.phase_out.max_investment_income", kind="set", value=1e9),),
        lambda: (
            _hh({"a": Person("a", 30, wages=20_000, hours=2080), "k": Person("k", 6), "b": Person("b", 32, wages=60_000, hours=2080, assets=[Asset("bonds", 300_000, 300_000, interest_yield=0.05)])},
                [TaxUnit("t", "a", dependents=["k"]), TaxUnit("tb", "b")]),
            [{"op": "gift_asset", "giver": "b", "recipient": "a", "asset": "bonds", "fraction": 1.0}],
        ),
    ),
    Canary(
        "dependent_full_std",
        "Dependent filers get the full standard deduction",
        "federal_income",
        lambda: (Change("gov.irs.deductions.standard.dependent.amount", kind="set", value=1_000_000.0),),
        lambda: (
            _hh({"p": Person("p", 45, wages=150_000, hours=2080, assets=[Asset("bond", 400_000, 400_000, interest_yield=0.05)]), "kid": Person("kid", 20)},
                [TaxUnit("t", "p", dependents=["kid"])]),
            [{"op": "gift_asset", "giver": "p", "recipient": "kid", "asset": "bond", "fraction": 1.0}],
        ),
    ),
    Canary(
        "hoh_ltcg_0pct",
        "0% capital-gains bracket for head of household uses the joint top",
        "federal_income",
        lambda: (Change("gov.irs.capital_gains.thresholds.1.HEAD_OF_HOUSEHOLD", kind="copy", pe_src="gov.irs.capital_gains.thresholds.1.JOINT"),),
        lambda: (
            _hh({"a": Person("a", 45, wages=40_000, hours=2080, ltcg=50_000), "b": Person("b", 44, wages=100_000, hours=2080), "k": Person("k", 12)},
                [TaxUnit("t", "a"), TaxUnit("tb", "b", dependents=["k"])]),
            [{"op": "assign_dependent", "dependent": "k", "tax_unit": "t"}, {"op": "set_filing_status", "tax_unit": "t", "status": "HEAD_OF_HOUSEHOLD"}],
        ),
    ),
    Canary(
        "addl_medicare_mfs",
        "Additional Medicare Tax threshold for married filing separately is the joint amount",
        "payroll",
        lambda: (Change("gov.irs.payroll.medicare.additional.exclusion.SEPARATE", kind="set", value=250_000.0),),
        lambda: (_couple(240_000, 240_000), SEP),
    ),
]


def canaries() -> dict[str, Canary]:
    return {c.id: c for c in CANARIES}
