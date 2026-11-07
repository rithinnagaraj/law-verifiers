"""Household model: the object agents rearrange and the verifier evaluates.

A Household is a calculator-independent description of a family's people,
assets and tax-unit arrangement for one tax year. Calculators never see it
directly: `compile_filing_units` turns it into the returns that would be
filed, and each calculator adapter translates those returns.

Single-year for now (`year`). The 3-year horizon in the experiment plan is a
planned extension; see README "Known limitations".
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Optional

FILING_STATUSES = ("SINGLE", "JOINT", "SEPARATE", "HEAD_OF_HOUSEHOLD")


# Exogenous per-person items: name -> (PolicyEngine input, Tax-Calculator
# record variable(s), kind). kind "income" counts toward a dependent's filing
# requirement; "deduction" items are expenses.
OTHER_ITEMS = {
    "social_security": ("social_security_retirement", ("e02400",), "income"),
    "pension": ("taxable_private_pension_income", ("e01500", "e01700"), "income"),
    "unemployment": ("unemployment_compensation", ("e02300",), "income"),
    "rental": ("rental_income", ("e02000",), "income"),
    "ira_distributions": ("taxable_ira_distributions", ("e01400",), "income"),
    "short_term_gains": ("short_term_capital_gains", ("p22250",), "income"),
    "nonqualified_dividends": ("non_qualified_dividend_income", ("e00600",), "income"),
    "real_estate_taxes": ("real_estate_taxes", ("e18500",), "deduction"),
    "student_loan_interest": ("student_loan_interest", ("e03210",), "deduction"),
}


@dataclass
class Asset:
    """A financial asset. Income it throws off is attributed to its owner."""

    id: str
    value: float
    basis: float
    interest_yield: float = 0.0  # taxable interest per $ of value per year
    qualified_dividend_yield: float = 0.0  # qualified dividends per $ of value
    # Planned liquidity event (multi-year horizon): in this tax year the
    # remaining unrealized gain is realized and the position reinvested.
    sale_year: Optional[int] = None

    @property
    def unrealized_gain(self) -> float:
        return self.value - self.basis


@dataclass
class Person:
    id: str
    age: int
    wages: float = 0.0
    self_employment: float = 0.0
    hours: float = 0.0  # annual hours of work (wages + self-employment)
    is_student: bool = False
    assets: list[Asset] = field(default_factory=list)
    # Long-term gains realized this year (exogenous + realize_gain moves).
    long_term_gains: float = 0.0
    # Deductible / credit-relevant expenses, paid by this person.
    charitable_cash: float = 0.0
    mortgage_interest: float = 0.0
    childcare_expenses: float = 0.0
    # Pre-tax retirement contributions this year, funded from pay. They move
    # cash into a retirement account: wealth and gross pay are unchanged.
    traditional_401k: float = 0.0
    traditional_ira: float = 0.0
    # Exogenous items both calculators model, keyed by OTHER_ITEMS (survey
    # households). They repeat each year and no move changes them.
    other: dict = field(default_factory=dict)

    # ---- derived income -------------------------------------------------
    @property
    def taxable_interest(self) -> float:
        return sum(a.value * a.interest_yield for a in self.assets)

    @property
    def qualified_dividends(self) -> float:
        return sum(a.value * a.qualified_dividend_yield for a in self.assets)

    @property
    def unearned_income(self) -> float:
        other = sum(v for k, v in self.other.items() if OTHER_ITEMS[k][2] == "income")
        return self.taxable_interest + self.qualified_dividends + self.long_term_gains + other

    @property
    def earned_income(self) -> float:
        return self.wages + self.self_employment

    @property
    def wealth(self) -> float:
        return sum(a.value for a in self.assets)

    def asset(self, asset_id: str) -> Asset:
        for a in self.assets:
            if a.id == asset_id:
                return a
        raise KeyError(f"{self.id} has no asset {asset_id!r}")


@dataclass
class TaxUnit:
    id: str
    head: str
    spouse: Optional[str] = None
    dependents: list[str] = field(default_factory=list)
    # None = derived (JOINT if spouse, HOH if dependents, else SINGLE).
    filing_status: Optional[str] = None
    # None = calculator chooses the better of standard / itemized.
    itemize: Optional[bool] = None

    @property
    def members(self) -> list[str]:
        return [self.head] + ([self.spouse] if self.spouse else []) + list(self.dependents)


@dataclass
class Household:
    id: str
    year: int
    state: str
    people: dict[str, Person]
    tax_units: list[TaxUnit]
    # Pairs of people who are legally married (needed for SEPARATE status).
    married_pairs: list[tuple[str, str]] = field(default_factory=list)

    # ---- helpers ----------------------------------------------------------
    def copy(self) -> "Household":
        return copy.deepcopy(self)

    def unit_of(self, person_id: str) -> TaxUnit:
        for tu in self.tax_units:
            if person_id in tu.members:
                return tu
        raise KeyError(f"{person_id} is in no tax unit")

    def tax_unit(self, unit_id: str) -> TaxUnit:
        for tu in self.tax_units:
            if tu.id == unit_id:
                return tu
        raise KeyError(f"no tax unit {unit_id!r}")

    def spouse_of(self, person_id: str) -> Optional[str]:
        for a, b in self.married_pairs:
            if a == person_id:
                return b
            if b == person_id:
                return a
        return None

    def validate(self) -> None:
        seen: dict[str, str] = {}
        for tu in self.tax_units:
            for m in tu.members:
                if m not in self.people:
                    raise ValueError(f"tax unit {tu.id} lists unknown person {m}")
                if m in seen:
                    raise ValueError(f"{m} is in tax units {seen[m]} and {tu.id}")
                seen[m] = tu.id
            if tu.filing_status is not None and tu.filing_status not in FILING_STATUSES:
                raise ValueError(f"bad filing status {tu.filing_status}")
            if tu.spouse and (tu.spouse != self.spouse_of(tu.head)):
                raise ValueError(f"{tu.spouse} is not married to {tu.head}")
        missing = set(self.people) - set(seen)
        if missing:
            raise ValueError(f"people in no tax unit: {sorted(missing)}")

    # ---- serialisation ------------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Household":
        people = {
            pid: Person(**{**p, "assets": [Asset(**a) for a in p.get("assets", [])]})
            for pid, p in d["people"].items()
        }
        return Household(
            id=d["id"],
            year=d["year"],
            state=d["state"],
            people=people,
            tax_units=[TaxUnit(**tu) for tu in d["tax_units"]],
            married_pairs=[tuple(p) for p in d.get("married_pairs", [])],
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# Filing units: the returns a household actually files.
# ---------------------------------------------------------------------------


@dataclass
class ReturnMember:
    person: Person
    role: str  # HEAD | SPOUSE | DEPENDENT
    # Whether this member's income is reported on this return. Dependents who
    # file their own return appear on the parent's return with income off.
    income_on_return: bool = True


@dataclass
class FilingUnit:
    id: str
    household_id: str
    year: int
    state: str
    filing_status: str
    members: list[ReturnMember]
    itemize: Optional[bool] = None
    # Set on a dependent's own return: the unit that claims them.
    claimed_by: Optional[str] = None

    @property
    def is_dependent_filer(self) -> bool:
        return self.claimed_by is not None

    @property
    def head(self) -> Person:
        return next(m.person for m in self.members if m.role == "HEAD")

    @property
    def spouse(self) -> Optional[Person]:
        return next((m.person for m in self.members if m.role == "SPOUSE"), None)

    @property
    def dependents(self) -> list[Person]:
        return [m.person for m in self.members if m.role == "DEPENDENT"]

    def filers(self) -> list[Person]:
        return [m.person for m in self.members if m.role in ("HEAD", "SPOUSE")]


def derive_filing_status(hh: Household, tu: TaxUnit) -> str:
    if tu.filing_status:
        return tu.filing_status
    if tu.spouse:
        return "JOINT"
    if hh.spouse_of(tu.head) is not None:
        return "SEPARATE"  # married but filing without the spouse
    if tu.dependents:
        return "HEAD_OF_HOUSEHOLD"
    return "SINGLE"


def _has_income(p: Person) -> bool:
    return (p.earned_income + p.unearned_income) > 0


def compile_filing_units(hh: Household) -> list[FilingUnit]:
    """Translate a household into the returns it files.

    Rule: a dependent with any income files their own return (as a dependent
    of the unit that claims them); on the claiming unit's return they appear
    with zero income. This makes the dependent-filer case explicit in every
    calculator instead of relying on how each calculator treats a dependent's
    income inside the parent's unit (PolicyEngine silently drops it; see
    results/phase0/FINDINGS.md).
    """
    hh.validate()
    units: list[FilingUnit] = []
    for tu in hh.tax_units:
        members = [ReturnMember(hh.people[tu.head], "HEAD")]
        if tu.spouse:
            members.append(ReturnMember(hh.people[tu.spouse], "SPOUSE"))
        for d in tu.dependents:
            p = hh.people[d]
            members.append(ReturnMember(p, "DEPENDENT", income_on_return=False))
        units.append(
            FilingUnit(
                id=f"{hh.id}:{tu.id}",
                household_id=hh.id,
                year=hh.year,
                state=hh.state,
                filing_status=derive_filing_status(hh, tu),
                members=members,
                itemize=tu.itemize,
            )
        )
        for d in tu.dependents:
            p = hh.people[d]
            if _has_income(p):
                units.append(
                    FilingUnit(
                        id=f"{hh.id}:{tu.id}:dep:{d}",
                        household_id=hh.id,
                        year=hh.year,
                        state=hh.state,
                        filing_status="SINGLE",
                        members=[ReturnMember(p, "HEAD")],
                        claimed_by=f"{hh.id}:{tu.id}",
                    )
                )
    return units


# ---------------------------------------------------------------------------
# Economic reality: what the household has before any tax.
# ---------------------------------------------------------------------------


@dataclass
class EconomicSnapshot:
    labor_income: float
    investment_yield: float  # interest + dividends thrown off by assets
    wealth: float  # market value of assets
    hours: float

    def as_dict(self) -> dict:
        return asdict(self)


def economic_snapshot(hh: Household) -> EconomicSnapshot:
    ps = hh.people.values()
    return EconomicSnapshot(
        labor_income=sum(p.earned_income for p in ps),
        investment_yield=sum(p.taxable_interest + p.qualified_dividends for p in ps),
        wealth=sum(p.wealth for p in ps),
        hours=sum(p.hours for p in ps),
    )
