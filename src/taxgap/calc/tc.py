"""Tax-Calculator (PSL) adapter.

All returns in one call share a tax year and a law. EITC and ACTC take-up
is set to full claiming (Tax-Calculator's current law draws take-up at
random). Wages are net of 401(k) deferrals. State and local income tax
(SALT) comes from PolicyEngine for the same return, so the itemized SALT
deduction sees the same fact in both calculators.
"""

from __future__ import annotations

from typing import Sequence

from ..law import Law
from ..model import OTHER_ITEMS, Return
from ..params import MARS_ORDER
from . import ReturnResult

TAKEUP = ("eitc_claim_prob_scale", "actc_claim_prob_scale")
_INT_COLS = {"RECID", "FLPDYR", "MARS", "XTOT", "DSI", "age_head", "age_spouse", "f2441", "n24", "nu18", "nu13", "nu06", "EIC", "elderly_dependents"}


def _record(rec_id: int, r: Return, salt: float, hsa_on: bool) -> dict:
    head, spouse = r.head, r.spouse
    filers = r.filers
    deps = r.dependents
    s = lambda attr: float(sum(getattr(p, attr) for p in filers))
    qd = s("dividends")
    eitc_kids = [d for d in deps if d.age < 19 or (d.is_student and d.age < 24)]
    rec = dict(
        RECID=rec_id,
        FLPDYR=r.year,
        MARS=MARS_ORDER.index(r.filing_status) + 1,
        XTOT=len(filers) + len(deps),
        DSI=int(r.claimed_by is not None),
        age_head=head.age,
        age_spouse=spouse.age if spouse else 0,
        e00200p=float(head.wages - head.k401),
        e00200s=float(spouse.wages - spouse.k401) if spouse else 0.0,
        e00200=s("wages") - s("k401"),
        pencon_p=float(head.k401),
        pencon_s=float(spouse.k401) if spouse else 0.0,
        e03150=s("ira_contrib"),
        e00900p=float(head.self_employment),
        e00900s=float(spouse.self_employment) if spouse else 0.0,
        e00900=s("self_employment"),
        e00300=s("interest"),
        e00600=qd,
        e00650=qd,
        p23250=s("ltcg"),
        e19800=s("charitable_cash"),
        e20100=s("charitable_noncash"),
        e19200=s("mortgage_interest"),
        e32800=s("childcare"),
        f2441=min(2, sum(1 for d in deps if d.age < 13)),
        n24=sum(1 for d in deps if d.age < 17),
        nu18=sum(1 for d in deps if d.age < 18),
        nu13=sum(1 for d in deps if d.age < 13),
        nu06=sum(1 for d in deps if d.age < 6),
        EIC=min(3, len(eitc_kids)),
        elderly_dependents=sum(1 for d in deps if d.age >= 65),
        e18400=float(salt),
        e03290=s("hsa") if hsa_on else 0.0,
    )
    if r.filing_status == "SEPARATE":
        # Spouses in this model live together: no child and dependent care
        # credit on a separate return (s.21(e)(2)). PolicyEngine applies the
        # rule; Tax-Calculator has no switch for it, so it gets no expenses.
        rec["e32800"] = 0.0
        rec["f2441"] = 0
    for p in filers:
        for k, v in p.other.items():
            for col in OTHER_ITEMS[k][1]:
                rec[col] = rec.get(col, 0.0) + float(v)
    return rec


def evaluate(returns: Sequence[Return], law: Law, salt: dict) -> dict[str, ReturnResult]:
    """{return key: result}; salt: {return key: state and local income tax}."""
    if not returns:
        return {}
    import pandas as pd
    import taxcalc as tc

    year = returns[0].year
    if any(r.year != year for r in returns):
        raise ValueError("one tax year per Tax-Calculator batch")
    hsa_on = "hsa_deduction" not in law.internal_off
    df = pd.DataFrame([_record(i + 1, r, salt.get(r.key, 0.0), hsa_on) for i, r in enumerate(returns)]).fillna(0.0)
    for c in df.columns:
        df[c] = df[c].astype(int if c in _INT_COLS else float)
    pol = tc.Policy()
    pol.implement_reform({k: {year: 9e99} for k in TAKEUP})
    # Spouses in this model live together: a separate filer is not eligible
    # for the EITC (s.32(d)(2) as amended by ARPA 2021 requires living apart).
    # Tax-Calculator otherwise allows it from 2021; PolicyEngine does not.
    pol.implement_reform({"EITC_sep_filers_elig": {year: False}})
    reform = law.tc_reform(year)
    if reform:
        pol.implement_reform(reform)
    recs = tc.Records(data=df, start_year=year, gfactors=None, weights=None)
    calc = tc.Calculator(policy=pol, records=recs, verbose=False)
    if calc.current_year != year:
        calc.advance_to_year(year)
    calc.calc_all()
    out = calc.dataframe(["RECID", "iitax", "taxbc", "c09600", "c04800"])
    by_id = {int(row.RECID): row for row in out.itertuples(index=False)}
    res = {}
    for i, r in enumerate(returns):
        row = by_id[i + 1]
        res[r.key] = ReturnResult(r.key, float(row.iitax), float(row.taxbc), float(row.c09600), float(row.c04800))
    if len(res) != len(returns):
        raise RuntimeError("Tax-Calculator returned a different number of records")
    return res
