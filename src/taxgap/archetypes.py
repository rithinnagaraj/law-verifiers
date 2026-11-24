"""Hand-built households.

`gate_archetypes()`: the 9 stratified archetypes of the non-decomposability
gate (income tercile x {single, married, single parent}); the gate adds the
family's witness household as the 10th.

`witness_archetypes()`: a broader set used to search for a family's
witness (couples with and without children, unmarried partners, parents
with minor and adult children, business owners, retirees), at three income
levels. All have the standard futures.
"""

from __future__ import annotations

from .model import Asset, Household, Person, TaxUnit

INCOME = {"low": 32_000, "mid": 95_000, "high": 320_000}


def _p(pid, age, wages=0.0, se=0.0, bond=0.0, fund=0.0, basis=0.4, ira=0.0, give=0.0, mortgage=0.0, student=False):
    p = Person(pid, age, is_student=student, wages=wages, self_employment=se, hours=2080 if (wages or se) else 0.0)
    if bond:
        p.assets.append(Asset(f"{pid}_bond", bond, bond, interest_yield=0.04))
    if fund:
        p.assets.append(Asset(f"{pid}_fund", fund, fund * basis, dividend_yield=0.02))
    p.ira_balance = ira
    p.charitable_cash = give
    p.mortgage_interest = mortgage
    return p


def _hh(hid, people, units, pairs=(), state="TX"):
    return Household(hid, 2024, state, {p.id: p for p in people}, units, list(pairs)).with_futures()


def gate_archetypes() -> list[Household]:
    out = []
    for lvl, inc in INCOME.items():
        a = inc / 32_000
        # single
        out.append(_hh(f"g_single_{lvl}", [_p("a", 40, wages=0.8 * inc, se=0.2 * inc, bond=20_000 * a, fund=40_000 * a, ira=30_000 * a, give=0.01 * inc, mortgage=0.03 * inc)], [TaxUnit("t", "a")]))
        # married, one child
        out.append(
            _hh(
                f"g_married_{lvl}",
                [_p("a", 44, wages=0.6 * inc, se=0.1 * inc, bond=20_000 * a, fund=60_000 * a, ira=50_000 * a, give=0.01 * inc, mortgage=0.04 * inc), _p("b", 42, wages=0.3 * inc, fund=20_000 * a), _p("k", 12)],
                [TaxUnit("t", "a", "b", ["k"])],
                [("a", "b")],
            )
        )
        # single parent, two children
        out.append(
            _hh(
                f"g_parent_{lvl}",
                [_p("a", 38, wages=0.9 * inc, se=0.1 * inc, bond=10_000 * a, fund=30_000 * a, ira=20_000 * a, give=0.01 * inc, mortgage=0.03 * inc), _p("k0", 6), _p("k1", 15)],
                [TaxUnit("t", "a", dependents=["k0", "k1"])],
            )
        )
    return out


def witness_archetypes() -> list[Household]:
    out = list(gate_archetypes())
    for lvl, inc in INCOME.items():
        a = inc / 32_000
        # married, unequal earners, two children, investment income
        out.append(_hh(f"w_couple_kids_{lvl}", [_p("a", 45, wages=0.85 * inc, bond=60_000 * a, fund=80_000 * a, ira=60_000 * a), _p("b", 43, wages=0.15 * inc), _p("k0", 4), _p("k1", 9)], [TaxUnit("t", "a", "b", ["k0", "k1"])], [("a", "b")]))
        # married, equal earners, no children
        out.append(_hh(f"w_couple_{lvl}", [_p("a", 50, wages=0.5 * inc, fund=100_000 * a, basis=0.2), _p("b", 50, wages=0.5 * inc, bond=40_000 * a)], [TaxUnit("t", "a", "b")], [("a", "b")]))
        # married, one self-employed spouse
        out.append(_hh(f"w_business_{lvl}", [_p("a", 48, se=inc, fund=50_000 * a), _p("b", 46), _p("k", 10)], [TaxUnit("t", "a", "b", ["k"])], [("a", "b")]))
        # unmarried partners, children claimed by the lower earner
        out.append(
            _hh(f"w_partners_{lvl}", [_p("a", 36, wages=0.25 * inc, bond=5_000 * a), _p("b", 37, wages=0.75 * inc, bond=40_000 * a, fund=40_000 * a), _p("k0", 3), _p("k1", 8)], [TaxUnit("ta", "a", dependents=["k0", "k1"]), TaxUnit("tb", "b")])
        )
        # parents with an adult child filing alone (no income)
        out.append(_hh(f"w_adult_child_{lvl}", [_p("p", 56, wages=inc, fund=150_000 * a, basis=0.25, bond=50_000 * a), _p("s", 54), _p("c", 24)], [TaxUnit("t", "p", "s"), TaxUnit("tc", "c")], [("p", "s")]))
        # single parent with a minor child and a full-time student
        out.append(_hh(f"w_parent_student_{lvl}", [_p("p", 50, wages=inc, bond=80_000 * a, fund=60_000 * a), _p("c0", 13), _p("c1", 20, student=True)], [TaxUnit("t", "p", dependents=["c0", "c1"])]))
        # retired couple with an IRA and Social Security
        r = _hh(f"w_retired_{lvl}", [_p("a", 68, bond=100_000 * a, fund=100_000 * a, ira=200_000 * a), _p("b", 66)], [TaxUnit("t", "a", "b")], [("a", "b")])
        r.people["a"].other["social_security"] = 0.4 * inc
        r.people["b"].other["social_security"] = 0.2 * inc
        out.append(r)
    return out
