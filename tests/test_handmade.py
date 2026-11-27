"""Hand-authored catalog: planted provisions and the pilot families behave as
designed (DECISIONS, 2026-11-27). Known answers, PolicyEngine and
Tax-Calculator."""

from taxgap.calc import planted
from taxgap.law import CURRENT_LAW, PLANTED_BASE
from taxgap.model import Asset, Household, Person, TaxUnit
from taxgap.moves import years_of
from taxgap.mutations.handmade import hand_families
from taxgap.verifier import gains, prepare

GIFT = {"op": "gift_asset", "giver": "p", "recipient": "c", "asset": "fund", "fraction": 1.0}
SELL = {"op": "realize_gain", "person": "c", "asset": "fund@c", "fraction": 1.0}
SELL_PARENT = {"op": "realize_gain", "person": "p", "asset": "fund", "fraction": 1.0}


def hh(wages=150_000, value=60_000, basis=20_000, age=12):
    p = Person("p", 45, wages=wages, hours=2080)
    p.assets.append(Asset("fund", value, basis, dividend_yield=0.02))
    return Household("hk", 2024, "TX", {"p": p, "c": Person("c", age)}, [TaxUnit("t", "p", dependents=["c"])])


def gain(h, moves, law, tc=False):
    g = gains([prepare(h, moves)], law, with_tc=tc)[0]
    return (g["gain"], g["gain_tc"]) if tc else g["gain"]


def test_real_law_has_no_planted_provisions():
    h = hh()
    y = years_of(h, [GIFT, SELL], None)[0]
    assert planted.attribute_gifts(y, CURRENT_LAW) is y
    assert y.people["c"].gift_ltcg_y0 == 40_000 and y.people["c"].gift_donor == "p"


def test_donor_attribution_moves_the_gain():
    y = years_of(hh(), [GIFT, SELL], None)[0]
    a = planted.attribute_gifts(y, PLANTED_BASE)
    assert a.people["c"].ltcg == 0 and a.people["p"].ltcg == 40_000
    # next year's sale is still in the base window; two years later it is not
    y2 = years_of(hh(), [GIFT, dict(SELL, year=2025)], None)[1]
    assert planted.attribute_gifts(y2, PLANTED_BASE).people["p"].ltcg == 40_000
    y3 = years_of(hh(), [GIFT, dict(SELL, year=2026)], None)[2]
    assert y3.people["c"].gift_ltcg_y0 == 0 and y3.people["c"].gift_ltcg_y1 == 0


def test_saver_limits():
    assert round(planted.agi_limit("JOINT", 2024)) == 76_501
    assert round(planted.agi_limit("SINGLE", 2024)) == round(76_501 * 0.5)
    assert round(planted.agi_limit("HEAD_OF_HOUSEHOLD", 2024)) == round(76_501 * 0.75)


def _scores(fid, m, h, moves):
    laws = hand_families()[fid].laws(m)
    b = gain(h, moves, laws["base"])
    return {k: gain(h, moves, laws[k]) - b for k in ("L", "L1", "L2")}


def test_kid_gain_needs_both_changes_and_both_moves():
    h = hh()
    s = _scores("h:kid_gain", 1.0, h, [GIFT, SELL])
    assert s["L"] > 2_000  # the child's 0% rate instead of the parent's 15%
    assert abs(s["L1"]) < 0.1 * s["L"] and abs(s["L2"]) < 0.1 * s["L"]
    for one in ([GIFT], [SELL_PARENT]):
        assert abs(_scores("h:kid_gain", 1.0, h, one)["L"]) < 50


def test_kid_credit_is_given_to_the_child():
    # Implementation check only; whether the family interacts is for the gate.
    h = hh(value=30_000, basis=20_000)
    s = _scores("h:kid_credit", 1.0, h, [GIFT, SELL])
    assert abs(s["L1"]) < 50  # the gain still moves to the parent
    assert 900 <= s["L"] - s["L2"] <= 1_000  # 10% of $10,000, offsetting the child's kiddie tax


def test_kid_gain_timing_needs_next_year_sale():
    h = hh()
    same = _scores("h:kid_gain_timing", 1.0, h, [GIFT, SELL])
    later = _scores("h:kid_gain_timing", 1.0, h, [GIFT, dict(SELL, year=2025)])
    assert abs(same["L"]) < 50
    assert later["L"] > 2_000
    assert abs(later["L1"]) < 0.1 * later["L"] and abs(later["L2"]) < 0.1 * later["L"]


def test_calculators_agree_on_the_exploits():
    h = hh()
    for fid, mv in (("h:kid_gain", [GIFT, SELL]), ("h:kid_credit", [GIFT, SELL])):
        law = hand_families()[fid].laws(1.0)["L"]
        gp, gt = gain(h, mv, law, tc=True)
        assert abs(gp - gt) <= max(10.0, 0.02 * abs(gp)), (fid, gp, gt)
