"""Stage 1 moves: known answers in both calculators (2024, single filer, TX)."""

import pytest

from taxred.household import Asset, Household, Person, TaxUnit
from taxred.law import Law
from taxred.moves import MoveError, apply_moves
from taxred.taxes import evaluate_households
from taxred.verifier import Verifier, VerifierConfig

ENGINES = ["policyengine", "taxcalc"]


def single(wages, **kw):
    return Household("s", 2024, "TX", {"a": Person("a", 40, wages=wages, hours=2080, **kw)}, [TaxUnit("t", "a")])


def fed(hh, engine):
    return evaluate_households([hh], Law(2024), engine, with_benefits=False)[0].fed_income_tax


@pytest.mark.parametrize("engine", ENGINES)
def test_hsa(engine):
    # TI = 60,000 - 4,150 - 14,600 = 41,250 -> 1,160 + 12% x 29,650 = 4,718
    hh = apply_moves(single(60_000, hdhp=True), [{"op": "contribute_hsa", "person": "a", "amount": 4_150}])
    assert fed(hh, engine) == pytest.approx(4_718, abs=1)


def test_hsa_rules():
    with pytest.raises(MoveError):  # no HDHP
        apply_moves(single(60_000), [{"op": "contribute_hsa", "person": "a", "amount": 1_000}])
    with pytest.raises(MoveError):  # over the self-only limit
        apply_moves(single(60_000, hdhp=True), [{"op": "contribute_hsa", "person": "a", "amount": 4_151}])


@pytest.mark.parametrize("engine", ENGINES)
def test_roth_conversion(engine):
    # AGI 80,000; TI 65,400 -> 5,426 + 22% x 18,250 = 9,441
    hh = apply_moves(single(60_000, ira_balance=50_000), [{"op": "roth_convert", "person": "a", "amount": 20_000}])
    assert fed(hh, engine) == pytest.approx(9_441, abs=1)


@pytest.mark.parametrize("engine", ENGINES)
def test_donate_appreciated_asset(engine):
    # FMV deduction 30,000 (itemized); no gain. TI = 170,000:
    # 17,168.50 + 24% x 69,475 = 33,842.50
    hh = single(200_000, assets=[Asset("fund", 30_000, 10_000)])
    hh = apply_moves(hh, [{"op": "donate_asset", "person": "a", "asset": "fund", "fraction": 1.0}])
    assert fed(hh, engine) == pytest.approx(33_842.5, abs=1)


def test_donate_asset_vocabulary_cap():
    with pytest.raises(MoveError):  # 30k > 20% of 100k
        apply_moves(single(100_000, assets=[Asset("fund", 30_000, 10_000)]), [{"op": "donate_asset", "person": "a", "asset": "fund"}])


def test_donation_bunching_over_two_years():
    # $6k of cash giving and $8k of mortgage interest each year: always below
    # the standard deduction. Giving both years' $6k in 2024 makes 2024
    # itemized ($20k); total giving and end-of-horizon wealth are unchanged.
    hh = single(100_000, mortgage_interest=8_000, charitable_cash=6_000)
    moves = [
        {"op": "donate_cash", "person": "a", "amount": 6_000, "year": 2024},
        {"op": "reduce_donation", "person": "a", "amount": 6_000, "year": 2025},
    ]
    v = Verifier(Law(2024), VerifierConfig(horizon=2, run_attribution=False)).evaluate(hh, moves)
    assert v.reality_unchanged
    assert v.gain == pytest.approx((20_000 - 14_600) * 0.22, abs=2)
    assert v.crosscheck_pass
