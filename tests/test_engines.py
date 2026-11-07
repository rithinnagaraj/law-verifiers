"""Engine invariants: a return's result must not depend on what else is in
the batch or where it sits (regression test for Tax-Calculator's random
EITC/ACTC take-up model, which drops credits by row position)."""

import pytest

from taxred.engines import ENGINES
from taxred.household import Household, Person, TaxUnit, compile_filing_units
from taxred.law import Law


def eitc_unit(hid):
    hh = Household(hid, 2024, "TX", {"p": Person("p", 45, wages=40_000), "k": Person("k", 8)}, [TaxUnit("t", "p", dependents=["k"])])
    return compile_filing_units(hh)[0]


@pytest.mark.parametrize("engine", list(ENGINES))
def test_batch_position_invariance(engine):
    e = ENGINES[engine]()
    units = [eitc_unit(f"h{i}") for i in range(6)]
    alone = e.evaluate_units(units[:1], Law(2024))[0].fed_income_tax
    batch = [r.fed_income_tax for r in e.evaluate_units(units, Law(2024))]
    # HOH, $40k, 1 child: tax 2,241 before credits... EITC 1,451.66 and CTC 2,000 apply.
    assert all(x == pytest.approx(alone, abs=0.01) for x in batch)
    assert alone == pytest.approx(-1_610.66, abs=1)


def test_pe_forced_itemize_does_not_leak_across_batch():
    # Finding F8: a forced itemization choice on one unit used to switch every
    # other unit in the batch to the standard deduction.
    from taxred.household import Household, Person, TaxUnit
    from taxred.law import Law
    from taxred.moves import apply_moves
    from taxred.taxes import evaluate_households

    base = Household(
        "b", 2024, "TX",
        {"a": Person("a", 40, wages=80_000, mortgage_interest=30_000), "s": Person("s", 38), "k": Person("k", 10)},
        [TaxUnit("t", "a", "s", ["k"])], [("a", "s")],
    )
    forced = apply_moves(base, [{"op": "itemize_or_standard", "tax_unit": "t", "itemize": False}])
    forced.id = "f"
    alone = evaluate_households([base], Law(2024), "policyengine", with_benefits=False)[0].fed_income_tax
    batched = evaluate_households([base, forced], Law(2024), "policyengine", with_benefits=False)
    assert batched[0].fed_income_tax == alone  # itemizes: 3,536
    assert batched[1].fed_income_tax > alone  # forced standard: 3,632


def test_tc_mars_override_keeps_other_statuses_current():
    # A reform that changes only the MFS standard deduction must leave the
    # single amount at its current-law value in every year.
    from taxred.engines import mars_override
    from taxred.household import Household, Person, TaxUnit
    from taxred.law import Law
    from taxred.taxes import evaluate_households

    for year in (2024, 2026):
        hh = Household("s", year, "TX", {"a": Person("a", 35, wages=60_000)}, [TaxUnit("t", "a")])
        base = evaluate_households([hh], Law(year), "taxcalc", with_benefits=False)[0].fed_income_tax
        law = Law(year).with_reform({}, {"STD": mars_override(SEPARATE=50_000)})
        assert evaluate_households([hh], law, "taxcalc", with_benefits=False)[0].fed_income_tax == base


@pytest.mark.parametrize("engine", list(ENGINES))
def test_duplicate_household_ids_in_one_batch(engine):
    # Finding F12: several proposals on one household share its id; results
    # matched by unit id used to overwrite each other.
    from taxred.household import Household, Person, TaxUnit
    from taxred.moves import apply_moves
    from taxred.taxes import evaluate_households

    base = Household(
        "d", 2024, "TX",
        {"a": Person("a", 40, wages=230_000), "b": Person("b", 38), "k": Person("k", 5)},
        [TaxUnit("t", "a", "b", ["k"])], [("a", "b")],
    )
    sep = apply_moves(base, [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}])
    k401 = apply_moves(base, [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 20_000}])
    sep.id = k401.id = "d~moved"  # same id, as the verifier gives every moved copy
    alone = [evaluate_households([h], Law(2024), engine, with_benefits=False)[0].fed_income_tax for h in (sep, k401)]
    batch = [r.fed_income_tax for r in evaluate_households([sep, k401], Law(2024), engine, with_benefits=False)]
    assert alone[0] != alone[1]
    assert batch == pytest.approx(alone)
