"""E0.2 known-answer tests: hand-computed 2024 federal income tax.

Each expected value is worked out from 2024 IRS parameters (Rev. Proc.
2023-34) in the comment beside it. A case that a calculator gets wrong is
marked xfail with the reason; those are findings, not test bugs.
"""

import pytest

from taxred.household import Asset, Household, Person, TaxUnit
from taxred.law import Law
from taxred.taxes import evaluate_households

ENGINES = ["policyengine", "taxcalc"]


def H(hid, people, unit, pairs=()):
    return Household(hid, 2024, "TX", people, [unit], list(pairs))


def fed(hh, engine, law=None):
    return evaluate_households([hh], law or Law(2024), engine, with_benefits=False)[0]


@pytest.mark.parametrize("engine", ENGINES)
def test_single_50k(engine):
    # TI = 50,000 - 14,600 = 35,400; tax = 1,160 + 12% x 23,800 = 4,016
    hh = H("s", {"a": Person("a", 35, wages=50_000)}, TaxUnit("t", "a"))
    assert fed(hh, engine).fed_income_tax == pytest.approx(4_016, abs=1)


@pytest.mark.parametrize("engine", ENGINES)
def test_mfj_100k_two_kids(engine):
    # TI = 100,000 - 29,200 = 70,800; tax = 2,320 + 12% x 47,600 = 8,032; CTC 2 x 2,000 -> 4,032
    hh = H(
        "m",
        {"a": Person("a", 40, wages=60_000), "b": Person("b", 38, wages=40_000), "k1": Person("k1", 5), "k2": Person("k2", 8)},
        TaxUnit("t", "a", "b", ["k1", "k2"]),
        [("a", "b")],
    )
    assert fed(hh, engine).fed_income_tax == pytest.approx(4_032, abs=1)


@pytest.mark.parametrize("engine", ENGINES)
def test_hoh_20k_one_child_eitc_actc(engine):
    # TI = 0. EITC (1 child): max 4,213, phase-out starts at 22,720 -> 4,213.
    # ACTC = min(1,700, 15% x (20,000 - 2,500) = 2,625) = 1,700. Total -5,913.
    hh = H("h", {"a": Person("a", 30, wages=20_000), "k": Person("k", 6)}, TaxUnit("t", "a", dependents=["k"]))
    assert fed(hh, engine).fed_income_tax == pytest.approx(-5_913, abs=1)


def kiddie_household():
    return H(
        "k",
        {"p": Person("p", 45, wages=300_000), "c": Person("c", 10, assets=[Asset("bond", 20_000, 20_000, interest_yield=1.0)])},
        TaxUnit("t", "p", dependents=["c"]),
    )


@pytest.mark.parametrize("engine", ENGINES)
def test_kiddie_parent_hoh(engine):
    # Parent HOH: TI = 300,000 - 21,900 = 278,100.
    # 1,655 + 5,586 + 8,228 + 21,948 + 16,560 + 35% x 34,400 = 66,017. CTC fully phased out.
    r = fed(kiddie_household(), engine)
    parent = next(u for u in r.units if u.unit_id == "k:t")
    assert parent.fed_income_tax == pytest.approx(66_017, abs=1)


@pytest.mark.parametrize("engine", ENGINES)
def test_kiddie_child_current_law(engine):
    # Child: TI = 20,000 - 1,300 = 18,700. NUI = 20,000 - 2,600 = 17,400.
    # Parental tax on NUI at 35% = 6,090; child's tax on 1,300 at 10% = 130 -> 6,220.
    # Child AMT: 26% x (20,000 - 9,250) = 2,795 < 6,220, so no AMT.
    r = fed(kiddie_household(), engine)
    child = next(u for u in r.units if u.unit_id.endswith(":dep:c"))
    assert child.fed_income_tax + r.kiddie_adjustment == pytest.approx(6_220, abs=1)


@pytest.mark.parametrize(
    "engine",
    [
        pytest.param(
            "policyengine",
            marks=pytest.mark.xfail(
                strict=True,
                reason="FINDING: PolicyEngine-US does not apply the child AMT exemption limit (computes 2,012)",
            ),
        ),
        "taxcalc",
    ],
)
def test_child_no_kiddie_tax_amt(engine):
    # Without the kiddie tax: regular tax = 1,160 + 12% x 7,100 = 2,012.
    # Child AMT exemption limited to earned income + 9,250: TMT = 26% x 10,750 = 2,795.
    r = fed(kiddie_household(), engine, Law(2024).with_kiddie("none"))
    child = next(u for u in r.units if u.unit_id.endswith(":dep:c"))
    assert child.fed_income_tax == pytest.approx(2_795, abs=1)


def test_pe_drops_dependent_income_inside_parent_unit():
    """FINDING (documented, not a bug in this package): if a dependent's
    income is left inside the parent's PolicyEngine tax unit, it is taxed
    nowhere. compile_filing_units avoids this by giving such dependents their
    own return. This test pins the PolicyEngine behaviour so we notice if it
    changes."""
    from policyengine_us import Simulation

    Y = "2024"
    sit = {
        "people": {"p": {"age": {Y: 45}, "employment_income": {Y: 300_000}}, "c": {"age": {Y: 10}, "taxable_interest_income": {Y: 20_000}}},
        "tax_units": {"t": {"members": ["p", "c"]}},
        "households": {"h": {"members": ["p", "c"], "state_name": {Y: "TX"}}},
    }
    s = Simulation(situation=sit)
    assert float(s.calculate("adjusted_gross_income", Y)[0]) == pytest.approx(300_000)
