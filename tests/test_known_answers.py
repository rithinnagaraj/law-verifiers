"""A1 known-answer tests: hand-computed 2024 federal income tax, in both
calculators. Expected values are worked out from 2024 IRS parameters
(Rev. Proc. 2023-34) beside each case. A case a calculator gets wrong is an
expected failure with the reason (a finding, not a test bug)."""

import pytest

from taxgap.calc import pe, tc
from taxgap.calc.evaluate import evaluate
from taxgap.law import CURRENT_LAW
from taxgap.model import Person, TaxUnit, compile_returns
from helpers import H, couple, parent_child, single


def both(hh, law=CURRENT_LAW):
    r = evaluate([hh], law, fresh=True)[0]
    return r.pe, r.tc


def per_return(hh, engine, law=CURRENT_LAW):
    rs = compile_returns(hh, "x", hh.year)
    if engine == "pe":
        return pe.evaluate(rs, law)
    salt = {k: v.salt for k, v in pe.evaluate(rs, law).items()}
    return tc.evaluate(rs, law, salt)


def test_single_50k():
    # TI = 50,000 - 14,600 = 35,400; tax = 1,160 + 12% x 23,800 = 4,016
    p, t = both(single(50_000))
    assert p == pytest.approx(4_016, abs=1) and t == pytest.approx(4_016, abs=1)


def test_mfj_100k_two_kids():
    # TI = 100,000 - 29,200 = 70,800; tax = 2,320 + 12% x 47,600 = 8,032; CTC 4,000 -> 4,032
    p, t = both(couple(60_000, 40_000, kids=(5, 8)))
    assert p == pytest.approx(4_032, abs=1) and t == pytest.approx(4_032, abs=1)


def test_hoh_20k_one_child():
    # TI = 0. EITC (1 child) 4,213 (phase-out starts 22,720); ACTC = min(1,700, 15% x 17,500) = 1,700.
    hh = H("h", {"a": Person("a", 30, wages=20_000, hours=2080), "k": Person("k", 6)}, TaxUnit("t", "a", dependents=["k"]))
    p, t = both(hh)
    assert p == pytest.approx(-5_913, abs=1) and t == pytest.approx(-5_913, abs=1)


@pytest.mark.parametrize("engine", ["pe", "tc"])
def test_kiddie_parent_hoh(engine):
    # Parent HOH: TI = 300,000 - 21,900 = 278,100 -> 66,017 (CTC phased out).
    res = per_return(parent_child(), engine)
    assert res["x.0"].fed_tax == pytest.approx(66_017, abs=1)


def test_kiddie_child_current_law():
    # Child: TI = 20,000 - 1,300 = 18,700; NUI = 20,000 - 2,600 = 17,400.
    # Parental tax on NUI at 35% = 6,090; child's tax on 1,300 at 10% = 130 -> 6,220.
    # Child AMT 26% x (20,000 - 9,250) = 2,795 < 6,220. Household: 66,017 + 6,220.
    p, t = both(parent_child())
    assert p == pytest.approx(66_017 + 6_220, abs=2) and t == pytest.approx(66_017 + 6_220, abs=2)


@pytest.mark.parametrize(
    "engine",
    [pytest.param("pe", marks=pytest.mark.xfail(strict=True, reason="F3: PolicyEngine-US lacks the child AMT exemption limit (computes 2,012)")), "tc"],
)
def test_child_amt_without_kiddie_tax(engine):
    # Without the kiddie tax: regular 1,160 + 12% x 7,100 = 2,012; child AMT 26% x 10,750 = 2,795.
    law = CURRENT_LAW.without("kiddie_tax")
    res = per_return(parent_child(), engine, law)
    assert res["x.0.d0"].fed_tax == pytest.approx(2_795, abs=1)


def test_dependent_income_files_own_return():
    rs = compile_returns(parent_child(), "x", 2024)
    assert [r.key for r in rs] == ["x.0", "x.0.d0"]
    assert rs[1].claimed_by == "x.0" and not rs[0].members[1].income_on_return
