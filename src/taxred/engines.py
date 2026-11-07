"""Calculator adapters.

Each engine takes a batch of FilingUnits (and, for PolicyEngine, the
households they come from, for benefits) and returns per-unit results. All
units in a batch must share one tax year and one Law.

The engines see only what `compile_filing_units` produces, so both
calculators receive the same returns: same filing status, same members, same
income on each return.
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Sequence

import numpy as np

from .household import FilingUnit, Household, Person
from .law import Law

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")


@dataclass
class UnitResult:
    unit_id: str
    fed_income_tax: float  # after all credits, refundable included
    regular_tax: float  # before credits, at ordinary + preferential rates, no AMT
    amt: float
    taxable_income: float
    other_tax: float  # payroll + state + local (PolicyEngine only)

    @property
    def total_tax(self) -> float:
        return self.fed_income_tax + self.other_tax


def _year_period(year: int) -> str:
    return str(year)


# ---------------------------------------------------------------------------
# PolicyEngine-US
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _pe_system(reform_items: tuple):
    """A tax-benefit system per reform, built once. Passing a reform to
    Simulation() instead rebuilds the system on every call (~16 s)."""
    from policyengine_us import CountryTaxBenefitSystem

    if not reform_items:
        return CountryTaxBenefitSystem()
    from policyengine_core.reforms import Reform

    reform = Reform.from_dict(
        {path: {"2000-01-01.2100-12-31": value} for path, value in reform_items},
        country_id="us",
    )
    return CountryTaxBenefitSystem(reform=reform)


def _pe_person_inputs(p: Person, year: int, income_on: bool, role: str) -> dict:
    Y = _year_period(year)
    d = {
        "age": {Y: p.age},
        "is_full_time_student": {Y: bool(p.is_student)},
        "tax_unit_role_input": {Y: role},
        "weekly_hours_worked": {Y: p.hours / 52.0},
    }
    if income_on:
        d.update(
            {
                "employment_income": {Y: p.wages},
                "self_employment_income": {Y: p.self_employment},
                "taxable_interest_income": {Y: p.taxable_interest},
                "qualified_dividend_income": {Y: p.qualified_dividends},
                "long_term_capital_gains": {Y: p.long_term_gains},
                "charitable_cash_donations": {Y: p.charitable_cash},
                "home_mortgage_interest": {Y: p.mortgage_interest},
            }
        )
    else:
        for v in (
            "employment_income",
            "self_employment_income",
            "taxable_interest_income",
            "qualified_dividend_income",
            "long_term_capital_gains",
        ):
            d[v] = {Y: 0.0}
    return d


class PolicyEngineEngine:
    name = "policyengine"

    def _simulate(self, situation: dict, law: Law):
        from policyengine_us import Simulation

        return Simulation(situation=situation, tax_benefit_system=_pe_system(law.pe_reform))

    def evaluate_units(self, units: Sequence[FilingUnit], law: Law) -> list[UnitResult]:
        if not units:
            return []
        year = units[0].year
        Y = _year_period(year)
        sit = {"people": {}, "tax_units": {}, "families": {}, "spm_units": {}, "marital_units": {}, "households": {}}
        for i, fu in enumerate(units):
            assert fu.year == year, "one year per batch"
            ids = []
            childcare = 0.0
            for m in fu.members:
                pid = f"u{i}_{m.person.id}"
                ids.append(pid)
                inp = _pe_person_inputs(m.person, year, m.income_on_return, m.role)
                if fu.is_dependent_filer:
                    inp["claimed_as_dependent_on_another_return"] = {Y: True}
                sit["people"][pid] = inp
                if m.role != "DEPENDENT":
                    childcare += m.person.childcare_expenses
            tu = {"members": ids, "filing_status": {Y: fu.filing_status}}
            if fu.itemize is not None:
                tu["tax_unit_itemizes"] = {Y: bool(fu.itemize)}
            sit["tax_units"][f"t{i}"] = tu
            sit["families"][f"f{i}"] = {"members": ids}
            sit["spm_units"][f"s{i}"] = {"members": ids, "spm_unit_pre_subsidy_childcare_expenses": {Y: childcare}}
            sit["households"][f"h{i}"] = {"members": ids, "state_name": {Y: fu.state}}
            filers = [f"u{i}_{m.person.id}" for m in fu.members if m.role in ("HEAD", "SPOUSE")]
            sit["marital_units"][f"m{i}"] = {"members": filers}
            for m in fu.members:
                if m.role == "DEPENDENT":
                    sit["marital_units"][f"m{i}_{m.person.id}"] = {"members": [f"u{i}_{m.person.id}"]}
        sim = self._simulate(sit, law)
        calc = lambda v: np.asarray(sim.calculate(v, Y), dtype=float)
        fed = calc("income_tax")
        regular = calc("income_tax_main_rates") + calc("capital_gains_tax")
        amt = calc("alternative_minimum_tax")
        ti = calc("taxable_income")
        hh_tax = calc("household_tax")
        assert len(fed) == len(units) == len(hh_tax)
        return [
            UnitResult(fu.id, fed[i], regular[i], amt[i], ti[i], hh_tax[i] - fed[i])
            for i, fu in enumerate(units)
        ]

    def evaluate_benefits(self, households: Sequence[Household], law: Law) -> list[float]:
        """household_benefits for each household, with its real structure and incomes."""
        if not households:
            return []
        year = households[0].year
        Y = _year_period(year)
        sit = {"people": {}, "tax_units": {}, "families": {}, "spm_units": {}, "marital_units": {}, "households": {}}
        for i, hh in enumerate(households):
            ids = [f"b{i}_{pid}" for pid in hh.people]
            childcare = 0.0
            for tu_i, tu in enumerate(hh.tax_units):
                for pid in tu.members:
                    role = "HEAD" if pid == tu.head else "SPOUSE" if pid == tu.spouse else "DEPENDENT"
                    sit["people"][f"b{i}_{pid}"] = _pe_person_inputs(hh.people[pid], year, True, role)
                    if role != "DEPENDENT":
                        childcare += hh.people[pid].childcare_expenses
                sit["tax_units"][f"bt{i}_{tu_i}"] = {"members": [f"b{i}_{p}" for p in tu.members]}
            sit["families"][f"bf{i}"] = {"members": ids}
            sit["spm_units"][f"bs{i}"] = {"members": ids, "spm_unit_pre_subsidy_childcare_expenses": {Y: childcare}}
            sit["households"][f"bh{i}"] = {"members": ids, "state_name": {Y: hh.state}}
            paired = set()
            for a, b in hh.married_pairs:
                sit["marital_units"][f"bm{i}_{a}"] = {"members": [f"b{i}_{a}", f"b{i}_{b}"]}
                paired |= {a, b}
            for pid in hh.people:
                if pid not in paired:
                    sit["marital_units"][f"bm{i}_{pid}"] = {"members": [f"b{i}_{pid}"]}
        sim = self._simulate(sit, law)
        ben = np.asarray(sim.calculate("household_benefits", Y), dtype=float)
        assert len(ben) == len(households)
        return list(ben)


# ---------------------------------------------------------------------------
# Tax-Calculator (PSL)
# ---------------------------------------------------------------------------

_MARS = {"SINGLE": 1, "JOINT": 2, "SEPARATE": 3, "HEAD_OF_HOUSEHOLD": 4}


def _tc_record(rec_id: int, fu: FilingUnit) -> dict:
    head, spouse = fu.head, fu.spouse
    filers = [p for p in (head, spouse) if p is not None]
    deps = fu.dependents
    s = lambda attr: float(sum(getattr(p, attr) for p in filers))
    qd = s("qualified_dividends")
    eitc_kids = [d for d in deps if d.age < 19 or (d.is_student and d.age < 24)]
    return dict(
        RECID=rec_id,
        FLPDYR=fu.year,
        MARS=_MARS[fu.filing_status],
        XTOT=len(filers) + len(deps),
        DSI=int(fu.is_dependent_filer),
        age_head=head.age,
        age_spouse=spouse.age if spouse else 0,
        e00200p=float(head.wages),
        e00200s=float(spouse.wages) if spouse else 0.0,
        e00200=s("wages"),
        e00900p=float(head.self_employment),
        e00900s=float(spouse.self_employment) if spouse else 0.0,
        e00900=s("self_employment"),
        e00300=s("taxable_interest"),
        e00600=qd,
        e00650=qd,
        p23250=s("long_term_gains"),
        e19800=s("charitable_cash"),
        e19200=s("mortgage_interest"),
        e32800=s("childcare_expenses"),
        f2441=min(2, sum(1 for d in deps if d.age < 13)),
        n24=sum(1 for d in deps if d.age < 17),
        nu18=sum(1 for d in deps if d.age < 18),
        nu13=sum(1 for d in deps if d.age < 13),
        nu06=sum(1 for d in deps if d.age < 6),
        EIC=min(3, len(eitc_kids)),
        elderly_dependents=sum(1 for d in deps if d.age >= 65),
    )


_TC_INT_COLS = {"RECID", "FLPDYR", "MARS", "XTOT", "DSI", "age_head", "age_spouse", "f2441", "n24", "nu18", "nu13", "nu06", "EIC", "elderly_dependents"}


class TaxCalculatorEngine:
    name = "taxcalc"

    def evaluate_units(self, units: Sequence[FilingUnit], law: Law) -> list[UnitResult]:
        if not units:
            return []
        import pandas as pd
        import taxcalc as tc

        year = units[0].year
        df = pd.DataFrame([_tc_record(i + 1, fu) for i, fu in enumerate(units)])
        for c in df.columns:
            df[c] = df[c].astype(int if c in _TC_INT_COLS else float)
        pol = tc.Policy()
        reform = law.tc_reform_dict()
        if reform:
            pol.implement_reform({k: {year: v} for k, v in reform.items()})
        rec = tc.Records(data=df, start_year=year, gfactors=None, weights=None)
        calc = tc.Calculator(policy=pol, records=rec, verbose=False)
        if calc.current_year != year:
            calc.advance_to_year(year)
        calc.calc_all()
        out = calc.dataframe(["iitax", "taxbc", "c09600", "c04800"])
        return [
            UnitResult(fu.id, float(r.iitax), float(r.taxbc), float(r.c09600), float(r.c04800), 0.0)
            for fu, r in zip(units, out.itertuples(index=False))
        ]

    def evaluate_benefits(self, households, law) -> Optional[list]:
        return None  # Tax-Calculator models no benefits.


ENGINES = {"policyengine": PolicyEngineEngine, "taxcalc": TaxCalculatorEngine}
