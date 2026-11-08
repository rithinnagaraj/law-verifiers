"""Stage 2 vocabulary (distractors, decoys) and the married filing-status rule."""

import pytest

from taxred.household import Household, Person, TaxUnit
from taxred.moves import DECOYS, DISTRACTORS, MoveError, apply_moves


def couple():
    return Household(
        "c", 2024, "TX",
        {"a": Person("a", 40, wages=90_000, hours=2080), "b": Person("b", 38, wages=30_000, hours=1500), "k": Person("k", 5)},
        [TaxUnit("t", "a", "b", ["k"])], [("a", "b")],
    )


def test_distractors_change_nothing():
    hh = couple()
    assert len(DISTRACTORS) == 15 and len(DECOYS) == 5
    for d in DISTRACTORS:
        out = apply_moves(hh, [{"op": d, "person": "a", "amount": 500}])
        assert out.to_dict() == hh.to_dict()


def test_decoys_make_intended_contributions():
    out = apply_moves(couple(), [{"op": "decoy_max_401k", "person": "a"}])
    assert out.people["a"].traditional_401k == 23_000
    out = apply_moves(couple(), [{"op": "decoy_household_max_401k"}])
    assert out.people["b"].traditional_401k == 23_000
    with pytest.raises(MoveError):  # no HDHP
        apply_moves(couple(), [{"op": "decoy_max_hsa", "person": "a"}])


def test_married_person_cannot_file_hoh_or_single():
    sep = [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}]
    apply_moves(couple(), sep)
    for status in ("HEAD_OF_HOUSEHOLD", "SINGLE"):
        with pytest.raises(MoveError):
            apply_moves(couple(), sep + [{"op": "set_filing_status", "tax_unit": "t_s", "status": status}])
