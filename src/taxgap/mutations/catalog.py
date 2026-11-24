"""Parameters encoded in both calculators, paired by statutory meaning.

Each Param names one statutory quantity in PolicyEngine (path) and
Tax-Calculator (name, index); `extra` lists further Tax-Calculator
parameters that encode the same statutory quantity and must move with it
(F11: the AMT's capital-gains thresholds). `verify()` checks that both
calculators hold the same current-law value in 2024-2026; only verified
pairs are used to build mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..law import Change
from ..params import MARS_ORDER, pe_value, tc_value

STATUSES = ("SINGLE", "JOINT", "SEPARATE", "HEAD_OF_HOUSEHOLD")


@dataclass(frozen=True)
class Param:
    key: str  # short id
    provision: str  # statutory provision it belongs to (for "two provisions")
    pe: str
    tc: str
    tc_index: Optional[int] = None
    extra: tuple = ()  # ((tc name, index), ...) moved together with tc
    generous: int = +1  # +1: raising it lowers tax; -1: lowering it lowers tax
    status: Optional[str] = None

    def change(self, kind: str, value) -> tuple:
        out = [Change(self.pe, self.tc, self.tc_index, kind, value)]
        for name, idx in self.extra:
            out.append(Change(None, name, idx, kind, value))
        return tuple(out)


def _mars(key, provision, pe_base, tc, generous=+1, extra=(), statuses=STATUSES):
    out = []
    for s in statuses:
        i = MARS_ORDER.index(s)
        out.append(Param(f"{key}.{s}", provision, f"{pe_base}.{s}", tc, i, tuple((n, i) for n in extra), generous, s))
    return out


def candidates() -> list[Param]:
    ps: list[Param] = []
    ps += _mars("std", "standard_deduction", "gov.irs.deductions.standard.amount", "STD")
    for b in range(1, 7):
        ps += _mars(f"brk{b}", "rate_brackets", f"gov.irs.income.bracket.thresholds.{b}", f"II_brk{b}")
    ps += _mars("cg0", "capital_gains_rates", "gov.irs.capital_gains.thresholds.1", "CG_brk1", extra=("AMT_CG_brk1",))
    ps += _mars("cg15", "capital_gains_rates", "gov.irs.capital_gains.thresholds.2", "CG_brk2", extra=("AMT_CG_brk2",))
    ps += _mars("ctc_ps", "ctc", "gov.irs.credits.ctc.phase_out.threshold", "CTC_ps")
    ps += _mars("niit", "niit", "gov.irs.investment.net_investment_income_tax.threshold", "NIIT_thd")
    ps += _mars("amt_em", "amt", "gov.irs.income.amt.exemption.amount", "AMT_em")
    ps += _mars("amt_ps", "amt", "gov.irs.income.amt.exemption.phase_out.start", "AMT_em_ps")
    ps += _mars("salt", "salt_cap", "gov.irs.deductions.itemized.salt_and_real_estate.cap", "ID_AllTaxes_c")
    ps += [
        Param("ctc_amt", "ctc", "gov.irs.credits.ctc.amount.base[0].amount", "CTC_c"),
        Param("actc_rt", "actc", "gov.irs.credits.ctc.refundable.phase_in.rate", "ACTC_rt"),
        Param("actc_thd", "actc", "gov.irs.credits.ctc.refundable.phase_in.threshold", "ACTC_Income_thd", generous=-1),
        Param("eitc_inv", "eitc_investment_limit", "gov.irs.credits.eitc.phase_out.max_investment_income", "EITC_InvestIncome_c"),
        Param("niit_rt", "niit", "gov.irs.investment.net_investment_income_tax.rate", "NIIT_rt", generous=-1),
        Param("dep_std", "dependent_std", "gov.irs.deductions.standard.dependent.amount", "STD_Dep"),
        Param("dep_std_add", "dependent_std", "gov.irs.deductions.standard.dependent.additional_earned_income", "STD_Dep_earned_add"),
        Param("odc", "odc", "gov.irs.credits.ctc.amount.adult_dependent", "ODC_c"),
    ]
    for k in range(4):
        ps.append(Param(f"eitc_max{k}", "eitc", f"gov.irs.credits.eitc.max[{k}].amount", "EITC_c", k))
    return ps


def verify(years=(2024, 2025, 2026), tol=0.5) -> tuple[list[Param], list[tuple]]:
    """(verified params, [(param key, reason)]) by comparing current-law values."""
    ok, bad = [], []
    for p in candidates():
        try:
            for y in years:
                a = pe_value(p.pe, y)
                t = tc_value(p.tc, y)
                b = t[p.tc_index] if p.tc_index is not None else t
                if isinstance(a, bool) or abs(float(a) - float(b)) > tol * max(1.0, 1e-6 * abs(float(a))):
                    raise ValueError(f"{y}: PE {a} vs TC {b}")
                for name, idx in p.extra:
                    e = tc_value(name, y)
                    e = e[idx] if idx is not None else e
                    if abs(float(e) - float(b)) > tol:
                        raise ValueError(f"{y}: TC {name} {e} vs {b}")
            ok.append(p)
        except Exception as ex:  # missing path or name, or values differ
            bad.append((p.key, str(ex)[:120]))
    return ok, bad
