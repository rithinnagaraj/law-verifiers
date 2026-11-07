"""Law versions and the provision registry.

A `Law` is a base tax year plus a set of changes ("reforms") expressed for
each calculator, plus the rules this project implements itself because
neither calculator models them (currently: the kiddie tax, Form 8615).

Historical closures are encoded as counterfactual reforms on a modern base
year (research plan §8: "encode pre-closure rules as custom reforms"),
because PolicyEngine-US and Tax-Calculator only cover recent years.

Provisions are named, independently switchable pieces of law used by the
attribution check: disabling a provision and re-evaluating shows how much of
a gain it explains.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Optional


@dataclass(frozen=True)
class KiddieTaxRule:
    """Form 8615: a child's net unearned income is taxed at the parent's rate.

    age_under: the rule applies to children younger than this at year end.
    student_age_under: for full-time students, the age limit is this instead.
    Thresholds follow the statute's structure: the first `2 x dependent
    standard-deduction floor` of unearned income is not net unearned income.
    The earned-income support test for 18-23 year olds is not modelled.
    Siblings' net unearned income is combined and the parental tax allocated
    pro rata, as on Form 8615 lines 9-13.
    """

    enabled: bool = True
    age_under: int = 19
    student_age_under: Optional[int] = 24
    label: str = "current"
    # Unearned income up to this multiple of the dependent standard-deduction
    # floor is not net unearned income (statute: 2x).
    allowance_multiple: float = 2.0


KIDDIE_RULES = {
    # No kiddie tax: unearned income of children taxed at the child's rates.
    "none": KiddieTaxRule(enabled=False, label="none (pre-1987)"),
    # Tax Reform Act of 1986: children under 14.
    "tra1986": KiddieTaxRule(age_under=14, student_age_under=None, label="TRA 1986 (<14)"),
    # Tax Increase Prevention and Reconciliation Act of 2005: under 18.
    "tipra2005": KiddieTaxRule(age_under=18, student_age_under=None, label="TIPRA 2005 (<18)"),
    # Small Business and Work Opportunity Tax Act of 2007: under 19, students under 24.
    "sbwota2007": KiddieTaxRule(age_under=19, student_age_under=24, label="SBWOTA 2007 (<19, students <24)"),
}
KIDDIE_RULES["current"] = KIDDIE_RULES["sbwota2007"]


@dataclass(frozen=True)
class Provision:
    """A piece of law that can be switched off for attribution."""

    name: str
    description: str
    # PolicyEngine reform: {parameter path: value}. Scales are given as
    # "path[i].amount" entries. Value applies from 2000 to 2100.
    pe: dict = field(default_factory=dict)
    # Tax-Calculator reform: {param: value-or-list}.
    tc: dict = field(default_factory=dict)
    # Year-dependent PolicyEngine reform: fn(year) -> {path: value}.
    pe_fn: Optional[Callable[[int], dict]] = None
    # Implemented in this package rather than the calculators.
    internal: Optional[str] = None
    # "intended": an intended concession; gains from it are not loopholes when
    #   it is used within its stated conditions.
    # "anti_abuse": a rule that exists to stop a strategy. A gain that removing
    #   this rule would take away comes from getting around it, and is never
    #   labelled an intended concession, even when intended provisions explain it.
    # "other": ordinary rate and base provisions.
    kind: str = "other"

    @property
    def intended(self) -> bool:
        return self.kind == "intended"

    @property
    def anti_abuse(self) -> bool:
        return self.kind == "anti_abuse"


def _hoh_as_single(year: int) -> dict:
    """Head-of-household status switched off: HOH filers get the single
    standard deduction and brackets for `year`."""
    from .taxes import _pe_params

    p = _pe_params().gov.irs
    d = f"{year}-01-01"
    out = {"gov.irs.deductions.standard.amount.HEAD_OF_HOUSEHOLD": float(p.deductions.standard.amount.SINGLE(d))}
    for i in range(1, 8):
        th = p.income.bracket.thresholds.children[str(i)]
        out[f"gov.irs.income.bracket.thresholds.{i}.HEAD_OF_HOUSEHOLD"] = float(th.SINGLE(d))
    return out


_RC = "gov.irs.gross_income.retirement_contributions"

PROVISIONS: dict[str, Provision] = {
    p.name: p
    for p in [
        Provision(
            "head_of_household",
            "Head-of-household filing status (wider brackets, larger standard deduction)",
            pe_fn=_hoh_as_single,
            kind="intended",
        ),
        Provision(
            "retirement_contributions",
            "Exclusion / deduction of traditional 401(k) and IRA contributions",
            pe={f"{_RC}.limit.401k": 0, f"{_RC}.limit.ira": 0, **{f"{_RC}.catch_up.limit.k401[{i}].amount": 0 for i in range(4)}, f"{_RC}.catch_up.limit.ira": 0},
            kind="intended",
        ),
        Provision(
            "savers_credit",
            "Saver's credit (retirement savings contributions credit)",
            pe={"gov.irs.credits.retirement_saving.contributions_cap": 0},
            kind="intended",
        ),
        Provision(
            "eitc",
            "Earned income tax credit",
            pe={f"gov.irs.credits.eitc.max[{i}].amount": 0 for i in range(4)},
            tc={"EITC_c": [0, 0, 0, 0]},
            kind="intended",
        ),
        Provision(
            "eitc_investment_income_limit",
            "EITC disqualified (investment) income limit ($11,600 in 2024)",
            pe={"gov.irs.credits.eitc.phase_out.max_investment_income": 1e9},
            tc={"EITC_InvestIncome_c": 1e9},
            kind="anti_abuse",
        ),
        Provision(
            "ctc",
            "Child tax credit (incl. refundable portion)",
            pe={f"gov.irs.credits.ctc.amount.base[{i}].amount": 0 for i in range(2)},
            tc={"CTC_c": 0, "ACTC_c": 0, "ODC_c": 0},
            kind="intended",
        ),
        Provision(
            "dependent_std_deduction_limit",
            "Limit on the standard deduction of a dependent filer (TRA 1986)",
            pe={"gov.irs.deductions.standard.dependent.amount": 1_000_000},
            tc={"STD_Dep": 1_000_000},
            kind="anti_abuse",
        ),
        Provision(
            "child_amt_exemption_limit",
            "Limit on the AMT exemption of a child (AMT kiddie rule, TRA 1986)",
            pe={"gov.irs.income.amt.exemption.child.in_effect": False},
            tc={"AMT_child_em": 1_000_000},
            kind="anti_abuse",
        ),
        Provision(
            "niit",
            "Net investment income tax (3.8%)",
            pe={"gov.irs.investment.net_investment_income_tax.rate": 0},
            tc={"NIIT_rt": 0},
        ),
        Provision(
            "dependent_std_deduction_floor",
            "Minimum standard deduction of a dependent filer ($1,300 in 2024)",
            pe={
                "gov.irs.deductions.standard.dependent.amount": 0,
                "gov.irs.deductions.standard.dependent.additional_earned_income": 0,
            },
            tc={"STD_Dep": 0, "STD_Dep_earned_add": 0},
            kind="intended",
        ),
        Provision(
            "kiddie_allowance",
            "Kiddie-tax allowance: first 2x floor of a child's unearned income not taxed at the parent's rate",
            internal="kiddie_allowance",
            kind="intended",
        ),
        Provision(
            "kiddie_tax",
            "Kiddie tax: child's unearned income taxed at parent's rate (Form 8615)",
            internal="kiddie_tax",
            kind="anti_abuse",
        ),
    ]
}


@dataclass(frozen=True)
class Law:
    year: int = 2024
    kiddie: KiddieTaxRule = KIDDIE_RULES["current"]
    pe_reform: tuple = ()  # tuple of (path, value) for hashability
    tc_reform: tuple = ()
    disabled: frozenset = frozenset()  # provision names switched off
    label: str = "current law"

    def with_kiddie(self, key: str) -> "Law":
        return replace(self, kiddie=KIDDIE_RULES[key], label=f"{self.label} | kiddie={key}")

    def without(self, provision: str) -> "Law":
        """This law with one provision switched off (for attribution)."""
        p = PROVISIONS[provision]
        law = replace(
            self,
            pe_reform=self.pe_reform + tuple({**p.pe, **(p.pe_fn(self.year) if p.pe_fn else {})}.items()),
            tc_reform=self.tc_reform + tuple((k, _freeze(v)) for k, v in p.tc.items()),
            disabled=self.disabled | {provision},
            label=f"{self.label} - {provision}",
        )
        if p.internal == "kiddie_tax":
            law = replace(law, kiddie=KIDDIE_RULES["none"])
        elif p.internal == "kiddie_allowance":
            law = replace(law, kiddie=replace(law.kiddie, allowance_multiple=0.0))
        return law

    def without_all(self, provisions) -> "Law":
        law = self
        for p in provisions:
            law = law.without(p)
        return law

    def pe_reform_dict(self) -> dict:
        return {k: v for k, v in self.pe_reform}

    def tc_reform_dict(self) -> dict:
        return {k: _thaw(v) for k, v in self.tc_reform}


def _freeze(v):
    if isinstance(v, list):
        return tuple(_freeze(x) for x in v)
    return v


def _thaw(v):
    if isinstance(v, tuple):
        return [_thaw(x) for x in v]
    return v
