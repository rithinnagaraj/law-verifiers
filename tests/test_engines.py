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
