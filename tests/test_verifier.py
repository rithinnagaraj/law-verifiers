"""Verifier labels on cases whose answer is known by construction."""

import pytest

from taxgap.law import CURRENT_LAW, Change, by_status
from taxgap.model import Asset, Person, TaxUnit
from taxgap.verifier import Config, Verifier, label
from helpers import H, couple, parent_child, single

SEP = [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}]


def test_401k_is_an_intended_concession():
    v = Verifier(CURRENT_LAW).one(single(100_000), [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 10_000}])
    assert v.gain > 1_000 and v.label == "intended_concession", v


def test_working_less_is_a_sacrifice():
    v = Verifier(CURRENT_LAW).one(single(200_000), [{"op": "set_hours", "person": "a", "hours": 1_000}])
    assert v.label == "sacrifice"


def test_wash_sale_no_gain():
    hh = single(60_000)
    hh.people["a"].assets.append(Asset("fund", 50_000, 70_000))
    assert Verifier(CURRENT_LAW).one(hh, [{"op": "realize_gain", "person": "a", "asset": "fund"}]).label == "no_gain"


def test_planted_mfs_std_is_a_candidate():
    law = CURRENT_LAW.plus(by_status("gov.irs.deductions.standard.amount", "STD", "SEPARATE", "scale", 2.0))
    v = Verifier(law).one(couple(120_000, 100_000), SEP)
    assert v.label == "candidate" and v.gain > 3_000 and v.coverage == "two-calc"
    assert abs(v.gain - v.gain_tc) < 10 and v.recheck_gain == pytest.approx(v.gain)


def test_canary_is_a_code_disagreement():
    # PolicyEngine-only bug: MFS standard deduction = joint amount.
    law = CURRENT_LAW.plus(Change("gov.irs.deductions.standard.amount.SEPARATE", kind="copy", pe_src="gov.irs.deductions.standard.amount.JOINT"))
    v = Verifier(law).one(couple(120_000, 100_000), SEP)
    assert v.label == "code_disagreement" and v.gain > 5_000 and abs(v.gain_tc) < 100


def test_gift_to_child_beats_kiddie_floor_is_shared_code():
    # A gift of a bond to a 10-year-old above the allowance: the kiddie tax
    # takes most of it back; what is left is the allowance (intended).
    hh = parent_child(interest=20_000, on_child=False)
    v = Verifier(CURRENT_LAW).one(hh, [{"op": "gift_asset", "giver": "p", "recipient": "c", "asset": "bond"}])
    assert v.gain > 0 and v.coverage == "shared-code"


def test_futures_weighted():
    hh = couple(120_000, 100_000).with_futures()
    law = CURRENT_LAW.plus(by_status("gov.irs.deductions.standard.amount", "STD", "SEPARATE", "scale", 2.0))
    v = Verifier(law).one(hh, SEP)
    assert set(v.future_gains) == {"up", "down", "income_drop"}
    assert v.gain == pytest.approx(sum(v.future_gains.values()) / 3, rel=1e-6)


def test_relabel_is_pure():
    law = CURRENT_LAW.plus(Change("gov.irs.deductions.standard.amount.SEPARATE", kind="copy", pe_src="gov.irs.deductions.standard.amount.JOINT"))
    v = Verifier(law).one(couple(120_000, 100_000), SEP)
    assert label(v, Config(use_crosscheck=False)) == "candidate"
