"""Legitimate-planning set (experiment plan E0.6).

Scenarios that use intended incentives as designed (expected: not flagged,
i.e. `intended_concession` or `no_gain`), plus labelled negatives whose
expected label is known: real sacrifices, benefit cliffs, and a wash sale.

Each scenario: (id, family, household, moves, expected) where expected is a
set of acceptable labels. A positive scenario counts as a false positive if
the verifier labels it `candidate` or `code_disagreement`.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass

from .household import Asset, Household, Person, TaxUnit

NOT_FLAGGED = {"intended_concession", "no_gain"}


@dataclass
class Scenario:
    id: str
    family: str
    household: Household
    moves: list
    expected: set
    positive: bool  # True: legitimate planning (should not be flagged)

    @property
    def split(self) -> str:
        h = int(hashlib.sha1(self.id.encode()).hexdigest(), 16)
        return "dev" if h % 2 == 0 else "test"


def _single(hid, year, wages, age=35, state="TX", kids=(), **kw):
    people = {"a": Person("a", age, wages=wages, hours=2080 if wages else 0, **kw)}
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    return Household(hid, year, state, people, [TaxUnit("t", "a", dependents=[f"k{i}" for i in range(len(kids))])])


def _married(hid, year, w1, w2, age=40, state="TX", kids=()):
    people = {"a": Person("a", age, wages=w1, hours=2080 if w1 else 0), "b": Person("b", age - 2, wages=w2, hours=2080 if w2 else 0)}
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    return Household(hid, year, state, people, [TaxUnit("t", "a", "b", [f"k{i}" for i in range(len(kids))])], [("a", "b")])


def scenarios(year: int = 2024) -> list[Scenario]:
    out: list[Scenario] = []
    add = lambda *a: out.append(Scenario(*a))

    # --- positives: 401(k) deferrals -------------------------------------
    for wages, age, amount, kids in itertools.product(
        [30_000, 60_000, 100_000, 200_000, 400_000], [35, 55], ["part", "max"], [(), (6,)]
    ):
        lim = 23_000 + (7_500 if age >= 50 else 0)
        amt = min(lim, wages * 0.5) if amount == "max" else min(5_000, wages * 0.1)
        hid = f"k401_s_w{wages}_a{age}_{amount}_c{len(kids)}"
        add(hid, "401k", _single(hid, year, wages, age, kids=kids), [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": amt}], NOT_FLAGGED, True)
    for (w1, w2), amount in itertools.product([(50_000, 30_000), (120_000, 80_000), (300_000, 150_000)], ["part", "max"]):
        amt = 23_000 if amount == "max" else 5_000
        hid = f"k401_m_w{w1}_{w2}_{amount}"
        add(hid, "401k", _married(hid, year, w1, w2, kids=(4, 9)), [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": amt}], NOT_FLAGGED, True)

    # --- positives: traditional IRA (no workplace plan) --------------------
    for wages, age, kids in itertools.product([20_000, 30_000, 45_000, 70_000, 120_000], [30, 60], [(), (3,)]):
        lim = 7_000 + (1_000 if age >= 50 else 0)
        hid = f"ira_s_w{wages}_a{age}_c{len(kids)}"
        add(hid, "ira", _single(hid, year, wages, age, kids=kids), [{"op": "contribute_retirement", "person": "a", "account": "ira", "amount": min(lim, wages)}], NOT_FLAGGED, True)

    # --- positives: unmarried parents choose who claims the child ----------
    # Both are the child's parents and live together; either may claim the
    # child (the tie-breaker applies only if both claim).
    for (w1, w2), kids in itertools.product([(90_000, 25_000), (60_000, 15_000), (150_000, 35_000), (45_000, 20_000)], [(5,), (2, 7)]):
        hid = f"claim_w{w1}_{w2}_c{len(kids)}"
        people = {"a": Person("a", 34, wages=w1, hours=2080), "b": Person("b", 32, wages=w2, hours=1500)}
        for i, k in enumerate(kids):
            people[f"k{i}"] = Person(f"k{i}", k)
        hh = Household(hid, year, "TX", people, [TaxUnit("ta", "a", dependents=[f"k{i}" for i in range(len(kids))]), TaxUnit("tb", "b")])
        moves = [{"op": "assign_dependent", "dependent": f"k{i}", "tax_unit": "tb"} for i in range(len(kids))]
        add(hid, "claim_child", hh, moves, NOT_FLAGGED, True)

    # --- positives: a gift to a child within the kiddie-tax allowance ------
    # Parents below the NIIT threshold only: above it, part of the gain is
    # NIIT avoidance (the child's own MAGI is tested), which is not an
    # intended concession. Those cases are the gray family below. (Label
    # correction after the first E0.6 run, 2026-11-07; see FINDINGS.)
    for wages, interest, age in itertools.product([60_000, 150_000], [1_000, 2_000, 2_600], [8, 15]):
        hid = f"gift_allow_w{wages}_i{interest}_a{age}"
        hh = _single(hid, year, wages, kids=(age,))
        hh.people["a"].assets.append(Asset("bond", interest / 0.05, interest / 0.05, interest_yield=0.05))
        add(hid, "gift_allowance", hh, [{"op": "gift_asset", "giver": "a", "recipient": "k0", "asset": "bond"}], NOT_FLAGGED, True)

    # --- gray: the same gift from a parent above the NIIT threshold --------
    for wages, interest, age in itertools.product([300_000, 500_000], [5_000, 10_000, 20_000], [8, 15]):
        hid = f"gift_niit_w{wages}_i{interest}_a{age}"
        hh = _single(hid, year, wages, kids=(age,))
        hh.people["a"].assets.append(Asset("bond", interest / 0.05, interest / 0.05, interest_yield=0.05))
        add(hid, "gift_niit", hh, [{"op": "gift_asset", "giver": "a", "recipient": "k0", "asset": "bond"}], {"candidate"}, False)

    # --- positives: itemize vs standard (calculators already pick the best) -
    for wages, mortgage in itertools.product([80_000, 250_000], [5_000, 30_000]):
        hid = f"itemize_w{wages}_m{mortgage}"
        hh = _married(hid, year, wages, 0, kids=(10,))
        hh.people["a"].mortgage_interest = mortgage
        add(hid, "itemize", hh, [{"op": "itemize_or_standard", "tax_unit": "t", "itemize": mortgage > 20_000}], NOT_FLAGGED, True)

    # --- negatives: real sacrifice (work less) -----------------------------
    for wages, hours in itertools.product([80_000, 200_000, 500_000], [1_000, 1_600]):
        hid = f"sacrifice_w{wages}_h{hours}"
        add(hid, "sacrifice", _single(hid, year, wages), [{"op": "set_hours", "person": "a", "hours": hours}], {"sacrifice", "no_gain"}, False)

    # --- negatives: benefit cliffs (cut hours across a phase-out) ----------
    for wages, hours, kids in itertools.product([25_000, 35_000, 50_000], [1_000, 1_500], [(2,), (2, 6)]):
        hid = f"cliff_w{wages}_h{hours}_c{len(kids)}"
        add(hid, "benefit_cliff", _single(hid, year, wages, 30, kids=kids), [{"op": "set_hours", "person": "a", "hours": hours}], {"benefit_cliff", "sacrifice", "no_gain"}, False)

    # --- negatives: wash sale (sell at a loss and buy back) ----------------
    for wages in [60_000, 200_000]:
        hid = f"wash_w{wages}"
        hh = _single(hid, year, wages)
        hh.people["a"].assets.append(Asset("fund", 50_000, 70_000, qualified_dividend_yield=0.02))
        add(hid, "wash_sale", hh, [{"op": "realize_gain", "person": "a", "asset": "fund"}], {"no_gain"}, False)
    return out
