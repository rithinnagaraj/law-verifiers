"""Historical-closure cases (experiment plan E0.5) and known current-law
strategies.

A closure case is a loophole that a later law closed, encoded as

  law_pre / law_post  the rules before and after the closure, as
                      counterfactual reforms on a modern base year
  closed              provisions whose switching-on *is* the closure
  panel(year)         witness households, spanning households the closure
                      should and should not affect (dose-response)
  covered(hh)         whether the closure should take away the gain for hh
  witness(hh)         the move sequence of the strategy
  coverage            how independent the verifier's view of the closure is:
                        two-calc  both calculators implement the closed rule
                        internal  the rule is implemented in this package
                        pe-only   only PolicyEngine implements it

The H1 test (amended, see results/phase0/FINDINGS.md) is run on the closed
mechanism: for covered households the closure must remove a substantial
share of the pre-closure gain; for households it does not cover it must
remove (almost) none; and under post-closure law the closed provision must
not appear in the gain's attribution signature.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace
from typing import Callable

from .household import Asset, Household, Person, TaxUnit
from .law import KIDDIE_RULES, Law


# ---------------------------------------------------------------------------
# Witness panel: parent(s) with an interest-bearing bond and one child.
# ---------------------------------------------------------------------------

CHILDREN = [(8, False), (13, False), (16, False), (18, False), (20, True), (22, True), (20, False)]
PARENTS = [(40_000, False), (100_000, False), (200_000, True), (400_000, True)]
INTEREST = [1_000, 5_000, 20_000, 60_000]


def gift_panel(year: int, state: str = "TX", children=CHILDREN, parents=PARENTS, interest=INTEREST) -> list[Household]:
    out = []
    for (wages, married), intr, (age, student) in itertools.product(parents, interest, children):
        hid = f"w{wages}_i{intr}_a{age}{'s' if student else ''}"
        people = {
            "p1": Person(
                "p1",
                45,
                wages=wages if not married else wages * 0.6,
                hours=2080,
                assets=[Asset("bond", intr / 0.05, intr / 0.05, interest_yield=0.05)],
            ),
            "kid": Person("kid", age, is_student=student),
        }
        unit = TaxUnit("t", "p1", dependents=["kid"])
        pairs = []
        if married:
            people["p2"] = Person("p2", 44, wages=wages * 0.4, hours=2080)
            unit.spouse = "p2"
            pairs = [("p1", "p2")]
        out.append(Household(hid, year, state, people, [unit], pairs))
    return out


def gift_bond(hh: Household) -> list[dict]:
    return [{"op": "gift_asset", "giver": "p1", "recipient": "kid", "asset": "bond", "fraction": 1.0}]


def _bond_interest(hh: Household) -> float:
    return hh.people["p1"].taxable_interest


def _kid(hh: Household) -> Person:
    return hh.people["kid"]


# The child has net unearned income (2024: unearned income above 2 x $1,300).
KIDDIE_ALLOWANCE_2024 = 2_600


def _has_nui(hh: Household) -> bool:
    return _bond_interest(hh) > KIDDIE_ALLOWANCE_2024


def _kiddie_covers(key: str):
    rule = KIDDIE_RULES[key]

    def f(hh: Household) -> bool:
        k = _kid(hh)
        in_age = k.age < rule.age_under or bool(k.is_student and rule.student_age_under and k.age < rule.student_age_under)
        return in_age and _has_nui(hh)

    return f


# 2024 single brackets (Rev. Proc. 2023-34), for the a-priori child-AMT test.
_SINGLE_2024 = [(11_600, 0.10), (47_150, 0.12), (100_525, 0.22), (191_950, 0.24), (243_725, 0.32), (609_350, 0.35), (1e18, 0.37)]


def _regular_tax_single(ti: float) -> float:
    tax, lo = 0.0, 0.0
    for hi, r in _SINGLE_2024:
        if ti > lo:
            tax += (min(ti, hi) - lo) * r
        lo = hi
    return tax


def _child_amt_binds(hh: Household) -> bool:
    """With the child AMT exemption limited to earned income + $9,250 (2024),
    does the child's AMT exceed the regular tax on the gifted interest (no
    kiddie tax)? Interest only; 26% bracket."""
    ui = _bond_interest(hh)
    tmt = 0.26 * max(0.0, ui - 9_250)
    return tmt > _regular_tax_single(max(0.0, ui - 1_300)) + 1


@dataclass
class ClosureCase:
    name: str
    description: str
    closure: str  # the act / rule that closed it
    closer: str  # congress | agency
    coverage: str  # two-calc | internal | pe-only
    law_pre: Law
    law_post: Law
    closed: tuple  # provisions the closure switches on
    covered: Callable[[Household], bool]
    panel: Callable[[int], list] = gift_panel
    witness: Callable[[Household], list] = gift_bond
    sources: list = field(default_factory=list)
    notes: str = ""
    horizon: int = 1  # tax years the verifier evaluates for this case


def _roth_panel(year: int) -> list:
    from .household import with_scenarios

    out = []
    for wages, bal in itertools.product((20_000, 40_000, 80_000), (100_000, 200_000, 400_000)):
        hh = Household(f"r{wages}_{bal}", year, "TX", {"p": Person("p", 62, wages=wages, hours=2080 if wages else 0, ira_balance=bal)}, [TaxUnit("t", "p")])
        out.append(with_scenarios(hh))
    return out


def _roth_witness(hh: Household) -> list:
    amt = round(0.4 * hh.people["p"].ira_balance)
    return [
        {"op": "roth_convert", "person": "p", "amount": amt, "year": hh.year},
        {"op": "recharacterize", "person": "p", "amount": amt, "of_year": hh.year, "year": hh.year + 1, "if_scenario": ["down"]},
    ]


def closure_cases(year: int = 2024) -> dict[str, ClosureCase]:
    base = Law(year)
    no_kiddie = base.with_kiddie("none")
    # Before TRA 1986: no kiddie tax, no limit on a dependent's standard
    # deduction, no limit on a child's AMT exemption.
    no_child_amt = no_kiddie.without("child_amt_exemption_limit")
    pre1987 = no_child_amt.without("dependent_std_deduction_limit")
    cases = [
        ClosureCase(
            "kiddie_tra1986",
            "Shift unearned income to a child under 14, taxed at the child's rates",
            "Tax Reform Act of 1986, s.1411 (IRC s.1(g)), children under 14",
            "congress",
            "internal",
            no_kiddie,
            base.with_kiddie("tra1986"),
            ("kiddie_tax",),
            _kiddie_covers("tra1986"),
            sources=["P.L. 99-514 s.1411", "IRS Form 8615 instructions"],
        ),
        ClosureCase(
            "kiddie_tipra2005",
            "Shift unearned income to a child aged 14-17",
            "Tax Increase Prevention and Reconciliation Act of 2005, s.510 (age 14 -> 18)",
            "congress",
            "internal",
            base.with_kiddie("tra1986"),
            base.with_kiddie("tipra2005"),
            ("kiddie_tax",),
            lambda hh: 14 <= _kid(hh).age < 18 and _has_nui(hh),
            sources=["P.L. 109-222 s.510"],
        ),
        ClosureCase(
            "kiddie_sbwota2007",
            "Shift unearned income to an 18-year-old or a full-time student under 24",
            "Small Business and Work Opportunity Tax Act of 2007, s.8241",
            "congress",
            "internal",
            base.with_kiddie("tipra2005"),
            base.with_kiddie("sbwota2007"),
            ("kiddie_tax",),
            lambda hh: (_kid(hh).age == 18 or (_kid(hh).is_student and 18 <= _kid(hh).age < 24)) and _has_nui(hh),
            sources=["P.L. 110-28 s.8241"],
            notes="The earned-income support test for ages 18-23 is not modelled.",
        ),
        ClosureCase(
            "dependent_std_tra1986",
            "A dependent child claims the full standard deduction against gifted investment income",
            "Tax Reform Act of 1986, s.102 (IRC s.63(c)(5)): a dependent's standard deduction limited to the greater of a floor and earned income",
            "congress",
            "two-calc",
            pre1987,
            no_child_amt,
            ("dependent_std_deduction_limit",),
            # Removed only where the interest exceeds the dependent floor ($1,300).
            lambda hh: _bond_interest(hh) > 1_300,
            sources=["P.L. 99-514 s.102", "IRS Pub. 501, Standard deduction for dependents"],
            notes="The pre-1987 personal exemption of a dependent is not modelled (the 2024 exemption is $0).",
        ),
        ClosureCase(
            "tra1986_package",
            "Both TRA 1986 closures together: kiddie tax (<14) and the dependent standard-deduction limit",
            "Tax Reform Act of 1986, ss.102 and 1411",
            "congress",
            "internal",
            pre1987,
            base.with_kiddie("tra1986"),
            ("kiddie_tax", "dependent_std_deduction_limit"),
            lambda hh: _bond_interest(hh) > 1_300,
            sources=["P.L. 99-514"],
        ),
        ClosureCase(
            "child_amt_tra1986",
            "A child's AMT exemption shelters gifted investment income",
            "Tax Reform Act of 1986 (IRC s.59(j)): a child's AMT exemption limited to earned income + an inflation-adjusted amount",
            "congress",
            "two-calc",
            no_child_amt,
            no_kiddie,
            ("child_amt_exemption_limit",),
            _child_amt_binds,
            sources=["IRC s.59(j)", "IRS Form 6251 instructions"],
            notes="Finding F3: PolicyEngine does not apply the limit; expect the closure to be invisible to it.",
        ),
        ClosureCase(
            "roth_recharacterization_tcja2017",
            "Convert a traditional IRA to a Roth, then undo the conversion if the assets fall",
            "Tax Cuts and Jobs Act 2017, s.13611: no recharacterization of Roth conversions after 2017",
            "congress",
            "two-calc",
            replace(base, roth_recharacterization=True),
            base,
            ("roth_recharacterization",),
            lambda hh: True,
            panel=_roth_panel,
            witness=_roth_witness,
            sources=["P.L. 115-97 s.13611", "IRS Pub. 590-A (recharacterizations)"],
            notes="Needs scenarios (assets +25% / -25% / wages halved from 2025) and terminal valuation of IRA balances; horizon 3.",
            horizon=3,
        ),
    ]
    return {c.name: c for c in cases}


# ---------------------------------------------------------------------------
# Known current-law strategies (household-level), a seed for the recall
# targets of E2.3 alongside the Shelter Check subset.
# ---------------------------------------------------------------------------


@dataclass
class KnownStrategy:
    name: str
    description: str
    witness_household: Callable[[int], Household]
    witness: list
    expected_signature: tuple  # provisions expected in the attribution signature
    status: str  # "loophole" | "intended" | "gray"


def _eitc_gift_household(year: int) -> Household:
    return Household(
        "eitc_gift",
        year,
        "TX",
        {
            "p": Person("p", 35, wages=25_000, hours=2080, assets=[Asset("cd", 300_000, 300_000, interest_yield=0.05)]),
            "kid": Person("kid", 6),
        },
        [TaxUnit("t", "p", dependents=["kid"])],
    )


def known_strategies(year: int = 2024) -> dict[str, KnownStrategy]:
    def gift_hh(wages, married, interest, age=10, student=False):
        return lambda y: gift_panel(y, children=[(age, student)], parents=[(wages, married)], interest=[interest])[0]

    s = [
        KnownStrategy(
            "eitc_limit_gift",
            "A low-wage parent above the EITC investment-income limit gifts the assets to a child and regains the EITC",
            _eitc_gift_household,
            [{"op": "gift_asset", "giver": "p", "recipient": "kid", "asset": "cd", "fraction": 1.0}],
            ("eitc_investment_income_limit",),
            "gray",
        ),
        KnownStrategy(
            "niit_child_shift",
            "A high-income parent shifts investment income to a child; the child's NIIT threshold is not reached",
            gift_hh(400_000, True, 60_000),
            gift_bond(None),
            ("niit",),
            "gray",
        ),
        KnownStrategy(
            "kiddie_allowance",
            "A parent shifts up to the kiddie-tax allowance of unearned income to a child",
            gift_hh(100_000, False, 2_600),
            gift_bond(None),
            ("kiddie_allowance", "dependent_std_deduction_floor"),
            "intended",
        ),
    ]
    return {k.name: k for k in s}
