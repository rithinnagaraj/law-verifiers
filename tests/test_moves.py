"""Move vocabulary and the horizon (no calculator needed)."""

import pytest

from taxgap.model import Asset, Future, Person, TaxUnit
from taxgap.moves import MoveError, years_of
from helpers import H, couple, single


def test_static_household_repeats():
    hh = single(50_000)
    ys = years_of(hh, [], None)
    assert [h.year for h in ys] == [2024, 2025, 2026]
    assert all(h.people["a"].wages == 50_000 for h in ys)


def test_one_time_flow_only_in_its_year_stock_persists():
    hh = single(80_000)
    hh.people["a"].assets.append(Asset("fund", 100_000, 40_000, dividend_yield=0.02))
    ys = years_of(hh, [{"op": "realize_gain", "person": "a", "asset": "fund", "year": 2025}], None)
    assert [h.people["a"].ltcg for h in ys] == [0, 60_000, 0]
    assert ys[2].people["a"].asset("fund").basis == 100_000


def test_persistent_move_from_its_year_on():
    hh = single(80_000)
    ys = years_of(hh, [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 10_000, "year": 2025}], None)
    assert [h.people["a"].k401 for h in ys] == [0, 10_000, 10_000]


def test_future_shock_and_contingent_move():
    hh = single(80_000).with_futures()
    hh.people["a"].ira_balance = 100_000
    drop = next(f for f in hh.futures if f.name == "income_drop")
    up = next(f for f in hh.futures if f.name == "up")
    mv = [{"op": "roth_convert", "person": "a", "amount": 20_000, "year": 2025, "if_future": "income_drop"}]
    d = years_of(hh, mv, drop)
    u = years_of(hh, mv, up)
    assert d[1].people["a"].wages == 40_000 and d[1].people["a"].other["ira_distributions"] == 20_000
    assert "ira_distributions" not in d[2].people["a"].other and d[2].people["a"].roth_balance == 20_000
    assert "ira_distributions" not in u[1].people["a"].other and u[1].people["a"].ira_balance == 125_000


def test_contingent_move_before_futures_known():
    hh = single(80_000).with_futures()
    with pytest.raises(MoveError):
        years_of(hh, [{"op": "donate_cash", "person": "a", "amount": 100, "year": 2024, "if_future": "up"}], hh.futures[0])


def test_married_cannot_file_single_or_hoh():
    hh = couple(50_000, 50_000, kids=(5,))
    with pytest.raises(MoveError):
        years_of(hh, [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}, {"op": "set_filing_status", "tax_unit": "t", "status": "HEAD_OF_HOUSEHOLD"}], None)


def test_separate_split_and_assign():
    hh = couple(50_000, 50_000, kids=(5,))
    ys = years_of(hh, [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}, {"op": "assign_dependent", "dependent": "k0", "tax_unit": "t_s"}], None)
    units = {tu.id: tu for tu in ys[0].tax_units}
    assert units["t"].spouse is None and units["t_s"].head == "b" and units["t_s"].dependents == ["k0"]


def test_wash_sale_is_a_no_op():
    hh = single(60_000)
    hh.people["a"].assets.append(Asset("fund", 50_000, 70_000))
    ys = years_of(hh, [{"op": "realize_gain", "person": "a", "asset": "fund"}], None)
    assert ys[0].people["a"].ltcg == 0 and ys[0].people["a"].asset("fund").basis == 70_000


def test_limits_enforced():
    hh = single(20_000)
    with pytest.raises(MoveError):
        years_of(hh, [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 25_000}], None)
    with pytest.raises(MoveError):
        years_of(hh, [{"op": "contribute_hsa", "person": "a", "amount": 1_000}], None)  # no HDHP


def test_dates_outside_horizon():
    with pytest.raises(MoveError):
        years_of(single(1), [{"op": "donate_cash", "person": "a", "amount": 1, "year": 2027}], None)


def test_bunching_leaves_wealth_unchanged():
    hh = single(150_000)
    hh.people["a"].charitable_cash = 10_000
    mv = [{"op": "reduce_donation", "person": "a", "amount": 10_000, "year": 2024}, {"op": "donate_cash", "person": "a", "amount": 10_000, "year": 2025}]
    ys = years_of(hh, mv, None)
    assert [h.people["a"].charitable_cash for h in ys] == [0, 20_000, 10_000]
    assert ys[-1].people["a"].given_away == 0
