"""Hand-authored pilot 2 (DECISIONS 2026-11-28): the earned-income kiddie
flaws and the selling households. Implementation checks on a test
household; whether a family passes is for the gate."""

import copy

from taxgap.archetypes import witness_archetypes
from taxgap.calc.kiddie import earned_threshold
from taxgap.law import CURRENT_LAW, PLANTED_BASE
from taxgap.model import Asset, Household, Person, TaxUnit
from taxgap.mutations.handmade import hand_families, pilot2, selling_households
from taxgap.verifier import gains, prepare


def hh(se=120_000):
    p = Person("p", 45, self_employment=se, hours=2080)
    p.assets.append(Asset("fund", 80_000, 20_000, dividend_yield=0.02, sale_year=2025))
    return Household("hs", 2024, "TX", {"p": p, "c": Person("c", 16)}, [TaxUnit("t", "p", dependents=["c"])])


GIFT = {"op": "gift_asset", "giver": "p", "recipient": "c", "asset": "fund", "fraction": 1.0}
SHIFT = {"op": "shift_income", "payer": "p", "payee": "c", "amount": 30_000.0}


def gain(h, moves, law, tc=False):
    g = gains([prepare(h, moves)], law, with_tc=tc)[0]
    return (g["gain"], g["gain_tc"]) if tc else g["gain"]


def attr(fid, m, moves, which="L"):
    laws = hand_families()[fid].laws(m)
    return gain(hh(), moves, laws[which]) - gain(hh(), moves, laws["base"])


def test_real_law_and_base_are_unchanged():
    for law in (CURRENT_LAW, PLANTED_BASE):
        assert not law.kiddie.exempt_if_earned and law.kiddie.earned_offset == 0.0 and law.kiddie.ltcg_exempt == 0.0
    assert earned_threshold(2024) == 14_600


def test_exemption_needs_earned_income():
    # gift alone: the child earns nothing, the kiddie tax applies; only the allowance leaks
    assert abs(attr("h:kid_support", 1.0, [GIFT])) < 500
    # with wages above E, the gain is taxed at the child's own rates
    assert attr("h:kid_support", 1.0, [SHIFT, GIFT]) > 2_000
    # wages below E do not open the exemption
    small = dict(SHIFT, amount=10_000.0)
    assert attr("h:kid_support", 1.0, [small, GIFT]) < attr("h:kid_support", 1.0, [SHIFT, GIFT]) / 4


def test_each_change_alone_is_blocked():
    for fid in ("h:kid_support", "h:kid_earned_offset"):
        assert abs(attr(fid, 1.0, [SHIFT, GIFT], "L1")) < 50  # donor attribution keeps the gain on the parent
        assert abs(attr(fid, 1.0, [SHIFT, GIFT], "L2")) < 500  # the kiddie tax applies; the allowance leaks


def test_timing_variant_needs_gift_before_the_sale_year():
    assert abs(attr("h:kid_support_timing", 1.0, [SHIFT, dict(GIFT, year=2025)])) < 50  # gift-year attribution
    assert attr("h:kid_support_timing", 1.0, [SHIFT, GIFT]) > 2_000  # gift in 2024, planned sale in 2025


def test_offset_scales_with_earned_income():
    a1 = attr("h:kid_earned_offset", 1.0, [SHIFT, GIFT])
    a5 = attr("h:kid_earned_offset", 0.5, [SHIFT, GIFT])
    assert a1 > a5 > 0


def test_selling_households_change_only_age_and_sale():
    src = {h.id: h for h in witness_archetypes()}
    hs = selling_households()
    assert [h.id for h in hs] == [f"s_{s}_{l}" for s in ("business", "married") for l in ("low", "mid", "high")]
    for h in hs:
        o = copy.deepcopy(src[h.id.replace("s_business", "w_business").replace("s_married", "g_married")])
        o.id = h.id
        o.people["k"].age = 16
        o.people["a"].asset("a_fund").sale_year = 2025
        assert o.key() == h.key()
    assert all(f.households == hs for f in pilot2())


def test_calculators_agree_on_the_exploit():
    for fid in ("h:kid_support", "h:kid_earned_offset"):
        gp, gt = gain(hh(), [SHIFT, GIFT], hand_families()[fid].laws(1.0)["L"], tc=True)
        assert abs(gp - gt) <= max(10.0, 0.02 * abs(gp)), (fid, gp, gt)
