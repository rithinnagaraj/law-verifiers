"""Households: the objects agents rearrange and the verifier evaluates.

A Household is the state of a family at the start of the horizon: people,
assets, tax units, state of residence, and its possible futures. The moves
layer turns (household, moves) into one household per tax year and future;
the calc layer compiles each of those into the returns that would be filed.
Nothing in this module knows about either calculator.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Optional

FILING_STATUSES = ("SINGLE", "JOINT", "SEPARATE", "HEAD_OF_HOUSEHOLD")

# Exogenous per-person items both calculators model: name -> (PolicyEngine
# input, Tax-Calculator record columns, kind). "income" items count toward a
# dependent's filing requirement and the kiddie tax's unearned income where
# unearned; no move changes them.
OTHER_ITEMS = {
    "social_security": ("social_security_retirement", ("e02400",), "income"),
    "pension": ("taxable_private_pension_income", ("e01500", "e01700"), "income"),
    "unemployment": ("unemployment_compensation", ("e02300",), "income"),
    "ira_distributions": ("taxable_ira_distributions", ("e01400",), "income"),
    "short_term_gains": ("short_term_capital_gains", ("p22250",), "income"),
    "nonqualified_dividends": ("non_qualified_dividend_income", ("e00600",), "income"),
    "real_estate_taxes": ("real_estate_taxes", ("e18500",), "deduction"),
}
UNEARNED_OTHER = ("ira_distributions", "short_term_gains", "nonqualified_dividends")


@dataclass
class Asset:
    """A financial asset. The income it throws off belongs to its owner."""

    id: str
    value: float
    basis: float
    interest_yield: float = 0.0  # taxable interest per $ of value per year
    dividend_yield: float = 0.0  # qualified dividends per $ of value per year
    sale_year: Optional[int] = None  # planned sale: remaining gain realized that year

    @property
    def unrealized_gain(self) -> float:
        return self.value - self.basis


@dataclass
class Person:
    id: str
    age: int
    is_student: bool = False
    wages: float = 0.0
    self_employment: float = 0.0
    hours: float = 0.0  # annual hours of work
    assets: list[Asset] = field(default_factory=list)
    ltcg: float = 0.0  # long-term gains realized this year
    charitable_cash: float = 0.0
    charitable_noncash: float = 0.0  # fair market value of property donated this year
    mortgage_interest: float = 0.0
    childcare: float = 0.0
    k401: float = 0.0  # elective deferral this year (out of wages)
    ira_contrib: float = 0.0  # deductible traditional IRA contribution this year
    hdhp: bool = False  # covered by a high-deductible health plan
    hsa: float = 0.0  # HSA contribution this year (deductible)
    ira_balance: float = 0.0  # traditional IRA balance
    roth_balance: float = 0.0
    given_away: float = 0.0  # cumulative value donated (left the household)
    other: dict = field(default_factory=dict)  # OTHER_ITEMS

    @property
    def interest(self) -> float:
        return sum(a.value * a.interest_yield for a in self.assets)

    @property
    def dividends(self) -> float:
        return sum(a.value * a.dividend_yield for a in self.assets)

    @property
    def earned_income(self) -> float:
        return self.wages + self.self_employment

    @property
    def unearned_income(self) -> float:
        other = sum(float(self.other.get(k, 0.0)) for k in UNEARNED_OTHER)
        return self.interest + self.dividends + self.ltcg + other

    @property
    def gross_income(self) -> float:
        other = sum(float(v) for k, v in self.other.items() if OTHER_ITEMS[k][2] == "income")
        return self.earned_income + self.interest + self.dividends + self.ltcg + other

    @property
    def wealth(self) -> float:
        return sum(a.value for a in self.assets) + self.ira_balance + self.roth_balance - self.given_away

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
    filing_status: Optional[str] = None  # None: derived
    itemize: Optional[bool] = None  # None: each calculator picks the better

    @property
    def members(self) -> list[str]:
        return [self.head] + ([self.spouse] if self.spouse else []) + list(self.dependents)


@dataclass
class Future:
    """A possible future: from `from_year` on, asset values and retirement
    balances are multiplied by asset_growth, wages and self-employment by
    wage_factor."""

    name: str
    prob: float
    from_year: int
    asset_growth: float = 1.0
    wage_factor: float = 1.0


STANDARD_FUTURES = (
    Future("up", 1 / 3, 2025, asset_growth=1.25),
    Future("down", 1 / 3, 2025, asset_growth=0.75),
    Future("income_drop", 1 / 3, 2025, wage_factor=0.5),
)


@dataclass
class Household:
    id: str
    year: int  # first tax year of the horizon
    state: str
    people: dict[str, Person]
    tax_units: list[TaxUnit]
    married_pairs: list[tuple[str, str]] = field(default_factory=list)
    futures: list[Future] = field(default_factory=list)  # empty: one future

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
            if tu.spouse and tu.spouse != self.spouse_of(tu.head):
                raise ValueError(f"{tu.spouse} is not married to {tu.head}")
        missing = set(self.people) - set(seen)
        if missing:
            raise ValueError(f"people in no tax unit: {sorted(missing)}")
        if self.futures and abs(sum(f.prob for f in self.futures) - 1.0) > 1e-9:
            raise ValueError("future probabilities must sum to 1")

    def with_futures(self, futures=STANDARD_FUTURES) -> "Household":
        out = self.copy()
        out.futures = [Future(f.name, f.prob, f.from_year - 2024 + self.year, f.asset_growth, f.wage_factor) for f in futures]
        return out

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Household":
        people = {pid: Person(**{**p, "assets": [Asset(**a) for a in p.get("assets", [])]}) for pid, p in d["people"].items()}
        return Household(
            id=d["id"],
            year=d["year"],
            state=d["state"],
            people=people,
            tax_units=[TaxUnit(**tu) for tu in d["tax_units"]],
            married_pairs=[tuple(p) for p in d.get("married_pairs", [])],
            futures=[Future(**f) for f in d.get("futures", [])],
        )

    def key(self) -> str:
        """Canonical content key (id excluded): equal keys, equal taxes."""
        d = self.to_dict()
        d.pop("id")
        d.pop("futures")
        return json.dumps(d, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Returns: what a household files in one tax year.
# ---------------------------------------------------------------------------


@dataclass
class Member:
    person: Person
    role: str  # HEAD | SPOUSE | DEPENDENT
    income_on_return: bool = True


@dataclass
class Return:
    key: str  # unique within one evaluation batch
    year: int
    state: str
    filing_status: str
    members: list[Member]
    itemize: Optional[bool] = None
    claimed_by: Optional[str] = None  # key of the claiming return (dependent filer)

    @property
    def head(self) -> Person:
        return next(m.person for m in self.members if m.role == "HEAD")

    @property
    def spouse(self) -> Optional[Person]:
        return next((m.person for m in self.members if m.role == "SPOUSE"), None)

    @property
    def filers(self) -> list[Person]:
        return [m.person for m in self.members if m.role in ("HEAD", "SPOUSE")]

    @property
    def dependents(self) -> list[Person]:
        return [m.person for m in self.members if m.role == "DEPENDENT"]


def filing_status_of(hh: Household, tu: TaxUnit) -> str:
    if tu.filing_status:
        return tu.filing_status
    if tu.spouse:
        return "JOINT"
    if hh.spouse_of(tu.head) is not None:
        return "SEPARATE"
    if tu.dependents:
        return "HEAD_OF_HOUSEHOLD"
    return "SINGLE"


def _has_income(p: Person) -> bool:
    return p.gross_income > 0


def compile_returns(hh: Household, prefix: str, year: int) -> list[Return]:
    """The returns `hh` (already the household of tax year `year`) files.

    A dependent with income files a separate return as a dependent of the
    claiming unit and appears on the claiming return with no income: left
    inside the parent's PolicyEngine unit, a dependent's income is taxed
    nowhere (v1 finding). Return keys are `prefix`-scoped, never derived from
    the household id (v1 finding F12)."""
    hh.validate()
    out: list[Return] = []
    for k, tu in enumerate(hh.tax_units):
        key = f"{prefix}.{k}"
        members = [Member(hh.people[tu.head], "HEAD")]
        if tu.spouse:
            members.append(Member(hh.people[tu.spouse], "SPOUSE"))
        members += [Member(hh.people[d], "DEPENDENT", income_on_return=False) for d in tu.dependents]
        out.append(Return(key, year, hh.state, filing_status_of(hh, tu), members, itemize=tu.itemize))
        for j, d in enumerate(tu.dependents):
            p = hh.people[d]
            if _has_income(p):
                out.append(Return(f"{key}.d{j}", year, hh.state, "SINGLE", [Member(p, "HEAD")], claimed_by=key))
    return out


# ---------------------------------------------------------------------------
# Economic reality (what the household has before tax).
# ---------------------------------------------------------------------------


@dataclass
class Reality:
    labor_income: float = 0.0
    investment_yield: float = 0.0
    wealth: float = 0.0  # at the end of the horizon
    hours: float = 0.0

    def add_year(self, hh: Household, last: bool) -> None:
        for p in hh.people.values():
            self.labor_income += p.earned_income
            self.investment_yield += p.interest + p.dividends
            self.hours += p.hours
            if last:
                self.wealth += p.wealth

    def as_dict(self) -> dict:
        return asdict(self)
