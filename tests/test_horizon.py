"""Multi-year horizon: dated moves, one-time events, planned sales."""

import pytest

from taxred.household import Asset, Household, Person, TaxUnit
from taxred.law import Law
from taxred.moves import MoveError, household_in_year
from taxred.verifier import Verifier, VerifierConfig


def retiree():
    # Single retiree, no other income; a fund with a $100k gain that is sold in 2026.
    return Household(
        "r", 2024, "TX",
        {"a": Person("a", 70, assets=[Asset("fund", 100_000, 0.0, sale_year=2026)])},
        [TaxUnit("t", "a")],
    )


HARVEST = [{"op": "realize_gain", "person": "a", "asset": "fund", "fraction": 0.4, "year": 2024}]


def test_household_in_year_one_time_and_sale():
    hh = retiree()
    y24 = household_in_year(hh, HARVEST, 2024)
    y25 = household_in_year(hh, HARVEST, 2025)
    y26 = household_in_year(hh, HARVEST, 2026)
    assert y24.people["a"].long_term_gains == pytest.approx(40_000)
    assert y25.people["a"].long_term_gains == 0  # one-time event
    assert y25.people["a"].asset("fund").basis == pytest.approx(40_000)  # step-up persists
    assert y26.people["a"].long_term_gains == pytest.approx(60_000)  # planned sale of the rest
    base26 = household_in_year(hh, [], 2026)
    assert base26.people["a"].long_term_gains == pytest.approx(100_000)
    with pytest.raises(MoveError):
        household_in_year(hh, [dict(HARVEST[0], year=2023)], 2024)


def test_gain_harvesting_needs_the_horizon():
    hh = retiree()
    cfg = dict(run_attribution=False)
    one = Verifier(Law(2024), VerifierConfig(horizon=1, **cfg)).evaluate(hh, HARVEST)
    three = Verifier(Law(2024), VerifierConfig(horizon=3, **cfg)).evaluate(hh, HARVEST)
    # Within 2024 the harvest only realizes a gain taxed at 0%: no gain.
    assert one.gain <= 50
    # Over 2024-2026 it moves $40k of the 2026 sale out of the 15% bracket.
    assert three.gain > 1_000
    assert three.reality_unchanged
    assert three.crosscheck_pass


def test_move_after_horizon_is_invalid():
    v = Verifier(Law(2024), VerifierConfig(horizon=2, run_attribution=False)).evaluate(retiree(), [dict(HARVEST[0], year=2026)])
    assert v.label == "invalid"
