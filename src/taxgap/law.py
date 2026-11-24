"""Laws and provisions.

A Law is current law plus a tuple of Changes. A Change names the same
statutory parameter in both calculators (PolicyEngine path, Tax-Calculator
name and MARS/kid index) and how it changes:

  set    a constant value in every year
  scale  current-law value x factor, year by year
  add    current-law value + delta, year by year
  copy   the current-law value of another PolicyEngine path (and another
         Tax-Calculator index), year by year

Either side may be absent (a canary changes PolicyEngine only). The kiddie
tax (Form 8615) is implemented in this package (calc/kiddie.py), so its rule
is part of the Law too.

Provisions are named sets of changes that switch a piece of law off; the
verifier uses them for the intended-concession test (whitelist) and to see
whether a gain gets around an anti-abuse rule.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Optional

from .params import MARS_ORDER, PATCH_YEARS, pe_value, tc_value


@dataclass(frozen=True)
class Change:
    pe: Optional[str] = None  # PolicyEngine parameter path
    tc: Optional[str] = None  # Tax-Calculator parameter name
    tc_index: Optional[int] = None  # MARS (0 = SINGLE ...) or kid index; None = scalar
    kind: str = "set"  # set | scale | add | copy
    value: object = None  # constant / factor / delta
    pe_src: Optional[str] = None  # copy: source path
    tc_src_index: Optional[int] = None  # copy: source index

    def pe_values(self) -> dict:
        """{year: value} for PolicyEngine over PATCH_YEARS."""
        out = {}
        for y in PATCH_YEARS:
            out[y] = self._apply(lambda: pe_value(self.pe, y), lambda: pe_value(self.pe_src, y))
        return out

    def tc_value(self, year: int):
        cur = tc_value(self.tc, year)
        if self.tc_index is None:
            return self._apply(lambda: cur, lambda: cur)
        new = list(cur)
        src = cur[self.tc_src_index] if self.kind == "copy" else None
        new[self.tc_index] = self._apply(lambda: cur[self.tc_index], lambda: src)
        return new

    def _apply(self, current, source):
        if self.kind == "set":
            return self.value
        if self.kind == "scale":
            return current() * float(self.value)
        if self.kind == "add":
            return current() + float(self.value)
        if self.kind == "copy":
            return source()
        raise ValueError(f"unknown change kind {self.kind}")


def by_status(pe_path: str, tc_name: Optional[str], status: str, kind: str, value) -> Change:
    """A change to one filing status of a MARS-indexed parameter."""
    return Change(f"{pe_path}.{status}", tc_name, MARS_ORDER.index(status) if tc_name else None, kind, value)


@dataclass(frozen=True)
class KiddieRule:
    """Form 8615. The rule applies to children under `age_under` (full-time
    students under `student_age_under`); unearned income up to
    `allowance_multiple` x the dependent standard-deduction floor is not net
    unearned income. The earned-income support test for 18-23 year olds is
    not modelled."""

    enabled: bool = True
    age_under: int = 19
    student_age_under: Optional[int] = 24
    allowance_multiple: float = 2.0


@dataclass(frozen=True)
class Law:
    label: str = "current law"
    changes: tuple = ()
    kiddie: KiddieRule = KiddieRule()
    # Internal switches implemented by the adapters: "hsa_deduction" off.
    internal_off: frozenset = frozenset()

    def plus(self, *changes: Change, label: Optional[str] = None) -> "Law":
        return replace(self, changes=self.changes + tuple(changes), label=label or f"{self.label} + {len(changes)} change(s)")

    def key(self) -> str:
        return _law_key(self)

    def pe_changes(self) -> tuple:
        return _pe_changes(self)

    def tc_reform(self, year: int) -> dict:
        """Tax-Calculator reform for one year: {name: {year: value}}. Later
        changes to the same parameter compose on the earlier ones."""
        out: dict = {}
        for c in self.changes:
            if c.tc is None:
                continue
            if c.tc in out and c.tc_index is not None:
                v = list(out[c.tc][year])
                v[c.tc_index] = c.tc_value(year)[c.tc_index]
                out[c.tc] = {year: v}
            else:
                out[c.tc] = {year: c.tc_value(year)}
        return out

    def pe_param(self, path: str, year: int) -> float:
        """A PolicyEngine parameter's value under this law."""
        v = pe_value(path, year)
        for p, values in self.pe_changes():
            if p == path:
                v = values[year]
        return v

    def without(self, *provisions: str) -> "Law":
        law = self
        for name in provisions:
            p = PROVISIONS[name]
            law = replace(law, changes=law.changes + p.changes, label=f"{law.label} - {name}")
            if p.internal == "kiddie_tax":
                law = replace(law, kiddie=replace(law.kiddie, enabled=False))
            elif p.internal == "kiddie_allowance":
                law = replace(law, kiddie=replace(law.kiddie, allowance_multiple=0.0))
            elif p.internal:
                law = replace(law, internal_off=law.internal_off | {p.internal})
        return law


CURRENT_LAW = Law()


@lru_cache(maxsize=4096)
def _law_key(law: Law) -> str:
    return json.dumps(
        {"c": [c.__dict__ for c in law.changes], "k": law.kiddie.__dict__, "i": sorted(law.internal_off)},
        sort_keys=True,
        default=str,
    )


@lru_cache(maxsize=4096)
def _pe_changes(law: Law) -> tuple:
    """((path, {year: value}), ...) with later changes composed on earlier."""
    merged: dict = {}
    for c in law.changes:
        if c.pe is None:
            continue
        vals = c.pe_values()
        if c.pe in merged and c.kind in ("scale", "add"):
            prev = merged[c.pe]
            base = {y: pe_value(c.pe, y) for y in vals}
            vals = {y: prev[y] + (vals[y] - base[y]) if c.kind == "add" else prev[y] * float(c.value) for y in vals}
        merged[c.pe] = vals
    return tuple(merged.items())


# ---------------------------------------------------------------------------
# Provisions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Provision:
    name: str
    description: str
    kind: str  # intended | anti_abuse | other
    changes: tuple = ()
    internal: Optional[str] = None
    extended: bool = False  # not in the research plan's whitelist (A4 decides)


_STD = "gov.irs.deductions.standard"
_RC = "gov.irs.gross_income.retirement_contributions"
_BRK = "gov.irs.income.bracket.thresholds"


def _hoh_as_single() -> tuple:
    ch = [Change(f"{_STD}.amount.HEAD_OF_HOUSEHOLD", "STD", 3, "copy", pe_src=f"{_STD}.amount.SINGLE", tc_src_index=0)]
    for i in range(1, 8):
        ch.append(Change(f"{_BRK}.{i}.HEAD_OF_HOUSEHOLD", f"II_brk{i}", 3, "copy", pe_src=f"{_BRK}.{i}.SINGLE", tc_src_index=0))
    return tuple(ch)


PROVISIONS: dict[str, Provision] = {
    p.name: p
    for p in [
        Provision("head_of_household", "Head-of-household status (wider brackets, larger standard deduction)", "intended", _hoh_as_single()),
        Provision(
            "retirement_contributions",
            "Exclusion/deduction of traditional 401(k) and IRA contributions",
            "intended",
            (
                Change(f"{_RC}.limit.401k", kind="set", value=0.0),
                Change(f"{_RC}.limit.ira", kind="set", value=0.0),
                Change(f"{_RC}.catch_up.limit.ira", kind="set", value=0.0),
                *(Change(f"{_RC}.catch_up.limit.k401[{i}].amount", kind="set", value=0.0) for i in range(4)),
            ),
        ),
        Provision("savers_credit", "Saver's credit", "intended", (Change("gov.irs.credits.retirement_saving.contributions_cap", kind="set", value=0.0),)),
        Provision(
            "eitc",
            "Earned income tax credit",
            "intended",
            tuple(Change(f"gov.irs.credits.eitc.max[{i}].amount", "EITC_c", i, "set", 0.0) for i in range(4)),
        ),
        Provision(
            "ctc",
            "Child tax credit, refundable portion and credit for other dependents",
            "intended",
            (
                *(Change(f"gov.irs.credits.ctc.amount.base[{i}].amount", kind="set", value=0.0) for i in range(2)),
                Change(tc="CTC_c", kind="set", value=0.0),
                Change(tc="ACTC_c", kind="set", value=0.0),
                Change(tc="ODC_c", kind="set", value=0.0),
            ),
        ),
        Provision(
            "dependent_std_floor",
            "Minimum standard deduction of a dependent filer",
            "intended",
            (
                Change(f"{_STD}.dependent.amount", "STD_Dep", None, "set", 0.0),
                Change(f"{_STD}.dependent.additional_earned_income", "STD_Dep_earned_add", None, "set", 0.0),
            ),
        ),
        Provision("kiddie_allowance", "First 2x floor of a child's unearned income is outside the kiddie tax", "intended", internal="kiddie_allowance"),
        Provision("hsa_deduction", "HSA contribution deduction", "intended", internal="hsa_deduction", extended=True),
        Provision(
            "charitable_deduction",
            "Charitable contribution deduction",
            "intended",
            (Change("gov.irs.deductions.itemized.charity.ceiling.all", kind="set", value=0.0),),
            extended=True,
        ),
        Provision("kiddie_tax", "Kiddie tax (Form 8615)", "anti_abuse", internal="kiddie_tax"),
        Provision(
            "dependent_std_limit",
            "Limit on a dependent filer's standard deduction",
            "anti_abuse",
            (Change(f"{_STD}.dependent.amount", "STD_Dep", None, "set", 1_000_000.0),),
        ),
        Provision(
            "child_amt_limit",
            "Limit on a child's AMT exemption",
            "anti_abuse",
            (
                Change("gov.irs.income.amt.exemption.child.in_effect", kind="set", value=False),
                Change(tc="AMT_child_em", kind="set", value=1_000_000.0),
            ),
        ),
        Provision(
            "eitc_investment_limit",
            "EITC investment-income limit",
            "anti_abuse",
            (Change("gov.irs.credits.eitc.phase_out.max_investment_income", "EITC_InvestIncome_c", None, "set", 1e9),),
        ),
    ]
}

WHITELIST = tuple(n for n, p in PROVISIONS.items() if p.kind == "intended" and not p.extended)
WHITELIST_EXTENDED = tuple(n for n, p in PROVISIONS.items() if p.kind == "intended")
ANTI_ABUSE = tuple(n for n, p in PROVISIONS.items() if p.kind == "anti_abuse")
