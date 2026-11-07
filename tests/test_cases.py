"""Closure cases, anti-abuse provisions and the intended-concession rule."""

import pytest

from taxred.cases import closure_cases, known_strategies
from taxred.household import Asset, Household, Person, TaxUnit
from taxred.law import PROVISIONS, Law
from taxred.taxes import evaluate_households
from taxred.verifier import Verifier, VerifierConfig

ENGINES = ["policyengine", "taxcalc"]


def child_household():
    return Household(
        "c",
        2024,
        "TX",
        {"p": Person("p", 45, wages=300_000), "c": Person("c", 10, assets=[Asset("bond", 20_000, 20_000, interest_yield=1.0)])},
        [TaxUnit("t", "p", dependents=["c"])],
    )


def child_tax(law, engine):
    r = evaluate_households([child_household()], law, engine, with_benefits=False)[0]
    u = next(u for u in r.units if u.unit_id.endswith(":dep:c"))
    return u.fed_income_tax


@pytest.mark.parametrize("engine", ENGINES)
def test_pre1987_child_full_standard_deduction(engine):
    # Pre-TRA 1986 counterfactual: the child takes the full 2024 single
    # standard deduction. TI = 20,000 - 14,600 = 5,400; 10% -> 540. No AMT
    # (full exemption).
    law = closure_cases(2024)["dependent_std_tra1986"].law_pre
    assert child_tax(law, engine) == pytest.approx(540, abs=1)


@pytest.mark.parametrize("engine", ENGINES)
def test_dependent_std_limit_closure(engine):
    # Post: dependent floor 1,300. TI = 18,700; 1,160 + 12% x 7,100 = 2,012.
    # The child AMT limit is off in this case's laws.
    law = closure_cases(2024)["dependent_std_tra1986"].law_post
    assert child_tax(law, engine) == pytest.approx(2_012, abs=1)


def test_provision_kinds():
    assert PROVISIONS["kiddie_tax"].anti_abuse
    assert PROVISIONS["eitc_investment_income_limit"].anti_abuse
    assert PROVISIONS["eitc"].intended
    assert not PROVISIONS["niit"].intended and not PROVISIONS["niit"].anti_abuse


def test_eitc_limit_gift_is_not_intended():
    # Parent: $25k wages, $15k interest (> $11,600 limit) -> no EITC. Gifting
    # the CD to the child moves the interest off the parent's return and the
    # EITC comes back. EITC is an intended provision, but the gain gets around
    # an anti-abuse rule, so it must stay a candidate.
    s = known_strategies(2024)["eitc_limit_gift"]
    hh = s.witness_household(2024)
    cfg = VerifierConfig(attribution_provisions=("eitc", "eitc_investment_income_limit", "kiddie_tax", "dependent_std_deduction_floor", "kiddie_allowance"))
    v = Verifier(Law(2024), cfg).evaluate(hh, s.witness)
    assert v.gain > 1_000
    assert "eitc_investment_income_limit" in v.circumvents
    assert v.label in ("candidate", "code_disagreement")
    # Without the anti-abuse override the whitelist would call it intended.
    cfg_old = VerifierConfig(attribution_provisions=cfg.attribution_provisions, anti_abuse_overrides_intended=False)
    assert Verifier(Law(2024), cfg_old).evaluate(hh, s.witness).label == "intended_concession"
