"""Retirement-contribution move (known answers in both calculators) and the
wash-sale rule in realize_gain."""

import pytest

from taxred.household import Asset, Household, Person, TaxUnit
from taxred.law import Law
from taxred.moves import MoveError, apply_moves
from taxred.taxes import evaluate_households

ENGINES = ["policyengine", "taxcalc"]


def single(wages, age=35, **kw):
    return Household("s", 2024, "TX", {"a": Person("a", age, wages=wages, hours=2080, **kw)}, [TaxUnit("t", "a")])


def fed(hh, engine):
    return evaluate_households([hh], Law(2024), engine, with_benefits=False)[0].fed_income_tax


@pytest.mark.parametrize("engine", ENGINES)
def test_401k_deferral(engine):
    # TI = 60,000 - 10,000 - 14,600 = 35,400 -> 1,160 + 12% x 23,800 = 4,016
    hh = apply_moves(single(60_000), [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 10_000}])
    assert fed(hh, engine) == pytest.approx(4_016, abs=1)


@pytest.mark.parametrize("engine", ENGINES)
def test_ira_deduction(engine):
    # AGI = 43,000 (no saver's credit for single above $38,250).
    # TI = 43,000 - 14,600 = 28,400 -> 1,160 + 12% x 16,800 = 3,176
    hh = apply_moves(single(50_000), [{"op": "contribute_retirement", "person": "a", "account": "ira", "amount": 7_000}])
    assert fed(hh, engine) == pytest.approx(3_176, abs=1)


def test_limits():
    with pytest.raises(MoveError):
        apply_moves(single(100_000), [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 23_001}])
    # catch-up at 50+: 23,000 + 7,500
    apply_moves(single(100_000, age=55), [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 30_500}])
    with pytest.raises(MoveError):
        apply_moves(single(100_000), [{"op": "contribute_retirement", "person": "a", "account": "ira", "amount": 7_001}])
    with pytest.raises(MoveError):  # active participant
        apply_moves(
            single(100_000),
            [
                {"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 5_000},
                {"op": "contribute_retirement", "person": "a", "account": "ira", "amount": 5_000},
            ],
        )


def test_wash_sale_loss_disallowed():
    hh = single(60_000, assets=[Asset("fund", 50_000, 70_000)])
    out = apply_moves(hh, [{"op": "realize_gain", "person": "a", "asset": "fund"}])
    assert out.people["a"].long_term_gains == 0
    assert out.people["a"].asset("fund").basis == 70_000
