"""Moves and the economic-reality snapshot (no calculators needed)."""

import pytest

from taxred.household import Asset, Household, Person, TaxUnit, compile_filing_units, economic_snapshot
from taxred.moves import MoveError, apply_moves


def base():
    return Household(
        "h", 2024, "TX",
        {
            "a": Person("a", 45, wages=100_000, self_employment=50_000, hours=2500,
                        assets=[Asset("fund", 100_000, 40_000, 0.02, 0.01)]),
            "b": Person("b", 43, wages=30_000, hours=1000),
            "k": Person("k", 12),
        },
        [TaxUnit("t", "a", "b", ["k"])],
        [("a", "b")],
    )


def test_gift_keeps_wealth_and_yield():
    h = base()
    m = apply_moves(h, [{"op": "gift_asset", "giver": "a", "recipient": "k", "asset": "fund", "fraction": 0.5}])
    assert economic_snapshot(m) == economic_snapshot(h)
    assert m.people["k"].taxable_interest == pytest.approx(1_000)
    assert m.people["k"].assets[0].basis == pytest.approx(20_000)
    assert h.people["k"].assets == []  # input not mutated


def test_dependent_with_income_files_own_return():
    m = apply_moves(base(), [{"op": "gift_asset", "giver": "a", "recipient": "k", "asset": "fund"}])
    units = compile_filing_units(m)
    assert [u.id for u in units] == ["h:t", "h:t:dep:k"]
    assert units[1].claimed_by == "h:t"
    parent_k = next(x for x in units[0].members if x.person.id == "k")
    assert parent_k.income_on_return is False


def test_separate_then_joint_roundtrip():
    h = base()
    s = apply_moves(h, [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}])
    assert sorted(u.filing_status for u in compile_filing_units(s)) == ["SEPARATE", "SEPARATE"]
    j = apply_moves(s, [{"op": "set_filing_status", "tax_unit": "t", "status": "JOINT"}])
    assert [u.filing_status for u in compile_filing_units(j)] == ["JOINT"]


def test_realize_gain_keeps_reality():
    h = base()
    m = apply_moves(h, [{"op": "realize_gain", "person": "a", "asset": "fund", "fraction": 0.5}])
    assert m.people["a"].long_term_gains == pytest.approx(30_000)
    assert economic_snapshot(m) == economic_snapshot(h)


def test_shift_income_keeps_totals():
    h = base()
    m = apply_moves(h, [{"op": "shift_income", "payer": "a", "payee": "k", "amount": 10_000}])
    a, b = economic_snapshot(h), economic_snapshot(m)
    assert b.labor_income == pytest.approx(a.labor_income)
    assert b.hours == pytest.approx(a.hours)


def test_set_hours_changes_reality():
    h = base()
    m = apply_moves(h, [{"op": "set_hours", "person": "b", "hours": 500}])
    assert m.people["b"].wages == pytest.approx(15_000)
    assert economic_snapshot(m).labor_income < economic_snapshot(h).labor_income


@pytest.mark.parametrize(
    "move",
    [
        {"op": "nope"},
        {"op": "gift_asset", "giver": "a", "recipient": "zz", "asset": "fund"},
        {"op": "gift_asset", "giver": "a", "recipient": "k", "asset": "fund", "fraction": 2},
        {"op": "shift_income", "payer": "b", "payee": "k", "amount": 1},
        {"op": "set_filing_status", "tax_unit": "t", "status": "HEAD_OF_HOUSEHOLD"},
        {"op": "assign_dependent", "dependent": "a", "tax_unit": "t"},
    ],
)
def test_invalid_moves(move):
    with pytest.raises(MoveError):
        apply_moves(base(), [move])
