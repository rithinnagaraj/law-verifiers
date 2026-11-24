"""PolicyEngine-US adapter.

All returns in one call share a tax year and a law. Returns that force the
itemization choice are simulated apart from returns that leave it free
(v1 finding F8). Sales tax is set to zero (F6). A return may carry a fixed
SALT amount (Form 8615 variants keep the parent's own SALT). The saver's
credit is set to zero and care expenses are given to the tax unit as paid
(no imputed subsidy); both found in A2.
"""

from __future__ import annotations

import os
import warnings
from typing import Optional, Sequence

import numpy as np

from ..law import Law
from ..model import OTHER_ITEMS, Return
from ..params import pe_patched
from . import ReturnResult

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

_INCOME_VARS = (
    "employment_income",
    "self_employment_income",
    "taxable_interest_income",
    "qualified_dividend_income",
    "long_term_capital_gains",
)


def _person_inputs(p, Y: str, income_on: bool, role: str, dependent_filer: bool) -> dict:
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
                "taxable_interest_income": {Y: p.interest},
                "qualified_dividend_income": {Y: p.dividends},
                "long_term_capital_gains": {Y: p.ltcg},
                "charitable_cash_donations": {Y: p.charitable_cash},
                "charitable_non_cash_donations": {Y: p.charitable_noncash},
                "home_mortgage_interest": {Y: p.mortgage_interest},
                "traditional_401k_contributions_desired": {Y: p.k401},
                "traditional_ira_contributions_desired": {Y: p.ira_contrib},
            }
        )
        for k, v in p.other.items():
            d[OTHER_ITEMS[k][0]] = {Y: float(v)}
    else:
        for v in _INCOME_VARS:
            d[v] = {Y: 0.0}
        for k in p.other:
            d[OTHER_ITEMS[k][0]] = {Y: 0.0}
    if dependent_filer:
        d["claimed_as_dependent_on_another_return"] = {Y: True}
    return d


def _situation(returns: Sequence[Return], law: Law, salt: dict) -> dict:
    Y = str(returns[0].year)
    hsa_on = "hsa_deduction" not in law.internal_off
    sit = {k: {} for k in ("people", "tax_units", "families", "spm_units", "marital_units", "households")}
    for i, r in enumerate(returns):
        ids, childcare = [], 0.0
        for j, m in enumerate(r.members):
            pid = f"r{i}p{j}"
            ids.append(pid)
            sit["people"][pid] = _person_inputs(m.person, Y, m.income_on_return, m.role, r.claimed_by is not None)
            if m.role != "DEPENDENT":
                childcare += m.person.childcare
        tu = {
            "members": ids,
            "filing_status": {Y: r.filing_status},
            "state_sales_tax": {Y: 0.0},
            "local_sales_tax": {Y: 0.0},
            # Saver's credit: only PolicyEngine computes it, so it is excluded
            # at the source. Adding the computed credit back afterwards is
            # wrong when the non-refundable credit is not (fully) usable (A2).
            "savers_credit": {Y: 0.0},
            # Care expenses as paid out of pocket, given to the tax unit
            # directly: PolicyEngine otherwise subtracts a child care subsidy
            # imputed by its benefit model, which Tax-Calculator does not (A2).
            "tax_unit_childcare_expenses": {Y: childcare},
            "health_savings_account_ald": {Y: float(sum(p.hsa for p in r.filers)) if hsa_on else 0.0},
        }
        if r.itemize is not None:
            tu["tax_unit_itemizes"] = {Y: bool(r.itemize)}
        if r.key in salt:
            tu["state_and_local_sales_or_income_tax"] = {Y: float(salt[r.key])}
        sit["tax_units"][f"t{i}"] = tu
        sit["families"][f"f{i}"] = {"members": ids}
        sit["spm_units"][f"s{i}"] = {"members": ids}
        sit["households"][f"h{i}"] = {"members": ids, "state_name": {Y: r.state}}
        filers = [ids[j] for j, m in enumerate(r.members) if m.role in ("HEAD", "SPOUSE")]
        sit["marital_units"][f"m{i}"] = {"members": filers}
        for j, m in enumerate(r.members):
            if m.role == "DEPENDENT":
                sit["marital_units"][f"m{i}d{j}"] = {"members": [ids[j]]}
    return sit


def _run(returns: Sequence[Return], law: Law, salt: dict) -> list[ReturnResult]:
    from policyengine_us import Simulation

    Y = str(returns[0].year)
    with pe_patched(law.pe_changes()) as system:
        sim = Simulation(situation=_situation(returns, law, salt), tax_benefit_system=system)
        calc = lambda v: np.asarray(sim.calculate(v, Y), dtype=float)
        fed = calc("income_tax")
        regular = calc("income_tax_main_rates") + calc("capital_gains_tax")
        amt = calc("alternative_minimum_tax")
        ti = calc("taxable_income")
        savers = calc("savers_credit")
        st = calc("state_and_local_sales_or_income_tax")
    if not len(fed) == len(returns):
        raise RuntimeError("PolicyEngine returned a different number of tax units")
    return [ReturnResult(r.key, fed[i], regular[i], amt[i], ti[i], savers[i], st[i]) for i, r in enumerate(returns)]


def evaluate(returns: Sequence[Return], law: Law, salt: Optional[dict] = None) -> dict[str, ReturnResult]:
    """{return key: result}. One year per call."""
    if not returns:
        return {}
    if len({r.year for r in returns}) != 1:
        raise ValueError("one tax year per PolicyEngine batch")
    if len({r.key for r in returns}) != len(returns):
        raise ValueError("duplicate return keys in a batch")
    salt = salt or {}
    out: dict[str, ReturnResult] = {}
    forced = [r for r in returns if r.itemize is not None]
    free = [r for r in returns if r.itemize is None]
    for group in (forced, free):
        if group:
            for res in _run(group, law, salt):
                out[res.key] = res
    return out
