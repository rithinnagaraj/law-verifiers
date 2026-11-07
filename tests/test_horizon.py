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


def test_scenarios_and_contingent_moves():
    from taxred.household import with_scenarios

    hh = with_scenarios(Household("x", 2024, "TX", {"a": Person("a", 62, wages=40_000, hours=2080, ira_balance=100_000)}, [TaxUnit("t", "a")]))
    down = next(s for s in hh.scenarios if s["name"] == "down")
    up = next(s for s in hh.scenarios if s["name"] == "up")
    assert household_in_year(hh, [], 2025, down).people["a"].ira_balance == pytest.approx(75_000)
    assert household_in_year(hh, [], 2024, down).people["a"].ira_balance == pytest.approx(100_000)
    conv = [{"op": "roth_convert", "person": "a", "amount": 40_000, "year": 2024},
            {"op": "recharacterize", "person": "a", "amount": 40_000, "of_year": 2024, "year": 2025, "if_scenario": ["down"]}]
    # Allowed (pre-2018 law): in the down future the 2024 conversion is undone.
    d24 = household_in_year(hh, conv, 2024, down, allow_recharacterization=True)
    u24 = household_in_year(hh, conv, 2024, up, allow_recharacterization=True)
    assert d24.people["a"].other.get("ira_distributions", 0) == 0
    assert u24.people["a"].other["ira_distributions"] == pytest.approx(40_000)
    # Not allowed (current law): the conversion stands in every future.
    assert household_in_year(hh, conv, 2024, down).people["a"].other["ira_distributions"] == pytest.approx(40_000)
    # A move cannot depend on a future that is not yet known.
    with pytest.raises(MoveError):
        household_in_year(hh, [dict(conv[0], if_scenario=["down"])], 2024, down)


def test_recharacterization_closure_has_value():
    from taxred.cases import closure_cases

    c = closure_cases(2024)["roth_recharacterization_tcja2017"]
    hh = next(h for h in c.panel(2024) if h.id == "r40000_200000")
    cfg = VerifierConfig(horizon=3, run_attribution=False)
    pre = Verifier(c.law_pre, cfg).evaluate(hh, c.witness(hh))
    post = Verifier(c.law_post, cfg).evaluate(hh, c.witness(hh))
    assert pre.gain > post.gain + 500  # the option to undo is worth something
    assert set(pre.scenario_gains) == {"up", "down", "income_drop"}
    assert pre.scenario_gains["down"] > post.scenario_gains["down"]
    assert pre.scenario_gains["up"] == pytest.approx(post.scenario_gains["up"], abs=1)
