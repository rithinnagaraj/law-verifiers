"""The action vocabulary and the multi-year horizon.

A move is a dict {"op": name, ...args}, optionally with "year" (a tax year
of the horizon; default its first year) and "if_future" (a future name or
list of names: the move happens only in those futures, and only from the
year the future is known). Moves enforce bright-line statutory rules that
neither calculator checks (wash sales, contribution limits, HDHP coverage,
married filing rules). Invalid moves raise MoveError.

Persistent moves change the household from their year on. One-time moves
(ONE_TIME) count their flows (realized gains, donations, conversions, HSA
contributions) only in their own year; their stock effects (basis, balances,
assets given away) persist.

`years_of(hh, moves, future)` returns the household of every tax year of the
horizon in that future.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from typing import Callable, Optional

import numpy as np

from .config import HORIZON_YEARS
from .model import FILING_STATUSES, Asset, Future, Household, TaxUnit


class MoveError(ValueError):
    pass


def _person(hh: Household, pid):
    if pid not in hh.people:
        raise MoveError(f"unknown person {pid!r}")
    return hh.people[pid]


def _fraction(x) -> float:
    x = float(x)
    if not 0 < x <= 1:
        raise MoveError(f"fraction must be in (0, 1], got {x}")
    return x


def _amount(x) -> float:
    x = float(x)
    if not x > 0 or not np.isfinite(x):
        raise MoveError("amount must be positive")
    return x


@lru_cache(maxsize=64)
def limits(year: int, age: int) -> dict:
    """Current-law contribution limits (PolicyEngine parameters)."""
    from .params import pe_node, pe_value

    r = "gov.irs.gross_income.retirement_contributions"
    d = f"{year}-01-01"
    catch_up = age >= pe_value(f"{r}.catch_up.age_threshold", year)
    k401_catch = float(np.asarray(pe_node(f"{r}.catch_up.limit.k401")(d).calc(np.array([float(age)])))[0])
    h = "gov.irs.gross_income.health_savings_account_contributions.limit"
    return {
        "401k": pe_value(f"{r}.limit.401k", year) + k401_catch,
        "ira": pe_value(f"{r}.limit.ira", year) + catch_up * pe_value(f"{r}.catch_up.limit.ira", year),
        "hsa_self": pe_value(f"{h}.self_only", year) + (1000.0 if age >= 55 else 0.0),
        "hsa_family": pe_value(f"{h}.family", year) + (1000.0 if age >= 55 else 0.0),
    }


# ---------------------------------------------------------------------------
# Moves
# ---------------------------------------------------------------------------


def set_filing_status(hh: Household, year: int, tax_unit: str, status: str) -> None:
    """JOINT merges a married couple into one unit; SEPARATE splits it (the
    spouse heads a new unit `<id>_s`). SINGLE and HEAD_OF_HOUSEHOLD may be
    asserted only by an unmarried head; each calculator then applies its own
    eligibility rules. A married person living with the spouse cannot file
    single or head of household (s.2(b), s.7703(b))."""
    if status not in FILING_STATUSES:
        raise MoveError(f"unknown filing status {status!r}")
    tu = hh.tax_unit(tax_unit)
    if status == "SEPARATE":
        if not tu.spouse:
            raise MoveError("SEPARATE needs a married unit")
        hh.tax_units.append(TaxUnit(f"{tu.id}_s", tu.spouse, filing_status="SEPARATE"))
        tu.spouse = None
        tu.filing_status = "SEPARATE"
    elif status == "JOINT":
        spouse = hh.spouse_of(tu.head)
        if spouse is None:
            raise MoveError("JOINT needs a married head")
        other = hh.unit_of(spouse)
        if other.id == tu.id:
            raise MoveError("already filing jointly")
        if other.head != spouse:
            raise MoveError("the spouse is a dependent on another return")
        tu.spouse = spouse
        tu.dependents += other.dependents
        tu.filing_status = None
        hh.tax_units.remove(other)
    else:
        if tu.spouse or hh.spouse_of(tu.head) is not None:
            raise MoveError("a married person living with the spouse files JOINT or SEPARATE")
        if status == "HEAD_OF_HOUSEHOLD" and not tu.dependents:
            raise MoveError("head of household needs a qualifying person in the unit")
        tu.filing_status = status


def assign_dependent(hh: Household, year: int, dependent: str, tax_unit: str) -> None:
    """Another unit of the household claims the dependent."""
    _person(hh, dependent)
    src = hh.unit_of(dependent)
    if dependent not in src.dependents:
        raise MoveError(f"{dependent} is not a dependent")
    dst = hh.tax_unit(tax_unit)
    if dst.id == src.id:
        raise MoveError("already claimed by that unit")
    src.dependents.remove(dependent)
    dst.dependents.append(dependent)
    if not src.dependents and src.filing_status == "HEAD_OF_HOUSEHOLD":
        src.filing_status = None


def gift_asset(hh: Household, year: int, giver: str, recipient: str, asset: str, fraction: float = 1.0) -> None:
    """Give (part of) an asset to another household member; basis carries over."""
    g, r = _person(hh, giver), _person(hh, recipient)
    if giver == recipient:
        raise MoveError("giver is the recipient")
    f = _fraction(fraction)
    a = g.asset(asset)
    moved = Asset(f"{a.id}@{recipient}", a.value * f, a.basis * f, a.interest_yield, a.dividend_yield, a.sale_year, giver, year)
    a.value *= 1 - f
    a.basis *= 1 - f
    if a.value <= 1e-9:
        g.assets.remove(a)
    have = next((x for x in r.assets if x.id == moved.id), None)
    if have:
        have.value += moved.value
        have.basis += moved.basis
        have.gift_from, have.gift_year = giver, year
    else:
        r.assets.append(moved)


def shift_income(hh: Household, year: int, payer: str, payee: str, amount: float) -> None:
    """The payer's business pays the payee wages for work in it: the payer's
    self-employment income falls by `amount`, the payee's wages rise by it;
    hours move with the pay at the payer's hourly rate."""
    p, q = _person(hh, payer), _person(hh, payee)
    if payer == payee:
        raise MoveError("payer is the payee")
    amount = _amount(amount)
    if amount > p.self_employment + 1e-6:
        raise MoveError("amount above the payer's self-employment income")
    h = p.hours * amount / p.earned_income if p.earned_income > 0 else 0.0
    p.self_employment -= amount
    q.wages += amount
    p.hours -= h
    q.hours += h


def set_hours(hh: Household, year: int, person: str, hours: float) -> None:
    """Change hours worked; wages scale at the current hourly wage."""
    p = _person(hh, person)
    hours = float(hours)
    if not 0 <= hours <= 4000:
        raise MoveError("hours must be in [0, 4000]")
    if p.hours <= 0 or p.wages <= 0:
        raise MoveError("no current wage work to scale")
    p.wages *= hours / p.hours
    p.hours = hours


# No "itemize" move: Tax-Calculator cannot force the itemization choice (it
# always takes the larger deduction), so a forced choice is outside the
# calculators' overlap (found in A2 testing). Both calculators pick the
# better option, which is what a rational household would do.


def contribute_retirement(hh: Household, year: int, person: str, account: str, amount: float) -> None:
    """A pre-tax retirement contribution out of this year's pay, repeated
    each later year. "401k": an elective deferral (an employer plan is
    assumed). "ira": a traditional IRA contribution, allowed only when it is
    fully deductible under the rule both calculators share (no 401(k)
    deferral in the unit, s.219(g)). Within limits and compensation."""
    p = _person(hh, person)
    amount = _amount(amount)
    tu = hh.unit_of(person)
    if person not in (tu.head, tu.spouse):
        raise MoveError("only a filer can contribute")
    filers = [hh.people[m] for m in (tu.head, tu.spouse) if m]
    lim = limits(year, p.age)
    if account == "401k":
        if p.k401 + amount > min(lim["401k"], p.wages) + 1e-6:
            raise MoveError("401(k) deferral above the limit or wages")
        if any(q.ira_contrib > 0 for q in filers):
            raise MoveError("an IRA contribution in this unit would become partly non-deductible")
        p.k401 += amount
    elif account == "ira":
        if any(q.k401 > 0 for q in filers):
            raise MoveError("someone in the unit is an active plan participant")
        if p.ira_contrib + amount > min(lim["ira"], p.earned_income) + 1e-6:
            raise MoveError("IRA contribution above the limit or compensation")
        p.ira_contrib += amount
    else:
        raise MoveError(f"unknown account {account!r}")


def _tag_gift_gain(p, a, year: int, gain: float) -> None:
    """Record a gain realized on recently gifted property, by years since
    the gift (the planted donor-attribution rule reads it; real law ignores
    it). Planned sales are tagged as sales by a move are (DECISIONS 2026-11-28)."""
    if a.gift_from is not None and a.gift_year is not None and year - a.gift_year in (0, 1):
        if year == a.gift_year:
            p.gift_ltcg_y0 += gain
        else:
            p.gift_ltcg_y1 += gain
        p.gift_donor = a.gift_from


def realize_gain(hh: Household, year: int, person: str, asset: str, fraction: float = 1.0) -> None:
    """Sell and immediately repurchase (part of) an asset: its unrealized
    gain becomes a long-term gain this year and the basis steps up. A loss
    sold and repurchased is a wash sale (s.1091): disallowed, nothing happens."""
    p = _person(hh, person)
    a = p.asset(asset)
    gain = (a.value - a.basis) * _fraction(fraction)
    if gain <= 0:
        return
    p.ltcg += gain
    a.basis += gain
    _tag_gift_gain(p, a, year, gain)


def contribute_hsa(hh: Household, year: int, person: str, amount: float, coverage: str = "self") -> None:
    """HSA contribution this year (s.223): needs HDHP coverage; within the
    self-only or family limit (+$1,000 at 55+) and the couple's pay."""
    p = _person(hh, person)
    amount = _amount(amount)
    if not p.hdhp:
        raise MoveError("no high-deductible health plan")
    if coverage not in ("self", "family"):
        raise MoveError("coverage is self or family")
    cap = limits(year, p.age)["hsa_family" if coverage == "family" else "hsa_self"]
    if p.hsa + amount > cap + 1e-6:
        raise MoveError("HSA contribution above the limit")
    spouse = hh.spouse_of(person)
    pay = p.earned_income + (hh.people[spouse].earned_income if spouse else 0.0)
    if p.hsa + amount > pay + 1e-6:
        raise MoveError("HSA contribution above the couple's pay")
    p.hsa += amount


def donate_cash(hh: Household, year: int, person: str, amount: float) -> None:
    """A cash gift to a public charity this year; the money leaves the household."""
    p = _person(hh, person)
    amount = _amount(amount)
    p.charitable_cash += amount
    p.given_away += amount


def reduce_donation(hh: Household, year: int, person: str, amount: float) -> None:
    """Give less cash to charity this year than usual (with donate_cash in
    another year, this bunches giving)."""
    p = _person(hh, person)
    amount = _amount(amount)
    if amount > p.charitable_cash + 1e-6:
        raise MoveError("can only reduce this year's cash giving")
    p.charitable_cash -= amount
    p.given_away -= amount


DONATE_ASSET_CAP = 0.2  # share of household gross income


def donate_asset(hh: Household, year: int, person: str, asset: str, fraction: float = 1.0) -> None:
    """Give (part of) an appreciated asset to a public charity: a deduction
    at fair market value and no capital gain. Vocabulary rule: at most 20% of
    household gross income per year (below the AGI limits only PolicyEngine
    applies, so both calculators see the same deduction)."""
    p = _person(hh, person)
    a = p.asset(asset)
    value = a.value * _fraction(fraction)
    gross = sum(q.gross_income for q in hh.people.values())
    if value + sum(q.charitable_noncash for q in hh.people.values()) > DONATE_ASSET_CAP * max(gross, 0.0):
        raise MoveError("donated property above 20% of household income")
    a.basis *= a.value and (a.value - value) / a.value
    a.value -= value
    if a.value <= 1e-9:
        p.assets.remove(a)
    p.charitable_noncash += value
    p.given_away += value


def roth_convert(hh: Household, year: int, person: str, amount: float) -> None:
    """Convert part of a traditional IRA to a Roth IRA: a taxable IRA
    distribution this year; the balance moves accounts."""
    p = _person(hh, person)
    amount = _amount(amount)
    if amount > p.ira_balance + 1e-6:
        raise MoveError("above the traditional IRA balance")
    p.ira_balance -= amount
    p.roth_balance += amount
    p.other["ira_distributions"] = p.other.get("ira_distributions", 0.0) + amount


MOVES: dict[str, Callable] = {
    "set_filing_status": set_filing_status,
    "assign_dependent": assign_dependent,
    "gift_asset": gift_asset,
    "shift_income": shift_income,
    "set_hours": set_hours,
    "contribute_retirement": contribute_retirement,
    "realize_gain": realize_gain,
    "contribute_hsa": contribute_hsa,
    "donate_cash": donate_cash,
    "reduce_donation": reduce_donation,
    "donate_asset": donate_asset,
    "roth_convert": roth_convert,
}
ONE_TIME = frozenset({"realize_gain", "contribute_hsa", "donate_cash", "reduce_donation", "donate_asset", "roth_convert"})
FLOWS = ("ltcg", "charitable_cash", "charitable_noncash", "hsa", "gift_ltcg_y0", "gift_ltcg_y1")
OTHER_FLOWS = ("ira_distributions",)


def _flows(hh: Household) -> dict:
    return {pid: [getattr(p, f) for f in FLOWS] + [p.other.get(k, 0.0) for k in OTHER_FLOWS] for pid, p in hh.people.items()}


def _apply(hh: Household, year: int, m: dict, i: int) -> None:
    args = {k: v for k, v in m.items() if k not in ("op", "year", "if_future")}
    op = m.get("op")
    if op not in MOVES:
        raise MoveError(f"move {i}: unknown op {op!r}")
    try:
        MOVES[op](hh, year, **args)
    except MoveError as e:
        raise MoveError(f"move {i} ({op}): {e}") from e
    except (KeyError, TypeError, ValueError) as e:
        raise MoveError(f"move {i} ({op}): {e}") from e


def horizon(hh: Household) -> list[int]:
    return [hh.year + t for t in range(HORIZON_YEARS)]


def check(hh: Household, moves: list, years: Optional[list] = None) -> None:
    """Static checks: dates inside the horizon, futures known when used."""
    years = years or horizon(hh)
    names = {f.name for f in hh.futures}
    reveal = min((f.from_year for f in hh.futures), default=None)
    for i, m in enumerate(moves):
        if not isinstance(m, dict):
            raise MoveError(f"move {i}: not an object")
        try:
            y = int(m.get("year", years[0]))
        except (TypeError, ValueError) as e:
            raise MoveError(f"move {i}: bad year") from e
        if y not in years:
            raise MoveError(f"move {i}: year {y} outside the horizon {years[0]}-{years[-1]}")
        cond = m.get("if_future")
        if cond is not None:
            want = [cond] if isinstance(cond, str) else list(cond)
            if not hh.futures or not set(want) <= names:
                raise MoveError(f"move {i}: unknown future {cond!r}")
            if y < reveal:
                raise MoveError(f"move {i}: depends on a future not known until {reveal}")


def years_of(hh: Household, moves: list, future: Optional[Future], years: Optional[list] = None) -> list[Household]:
    """The household of each tax year of the horizon in `future`."""
    years = years or horizon(hh)
    check(hh, moves, years)
    state = hh.copy()
    state.futures = []
    out = []
    for y in years:
        if future is not None and y == future.from_year:
            for p in state.people.values():
                p.wages *= future.wage_factor
                p.self_employment *= future.wage_factor
                for a in p.assets:
                    a.value *= future.asset_growth
                p.ira_balance *= future.asset_growth
                p.roth_balance *= future.asset_growth
        todo = []
        for i, m in enumerate(moves):
            if int(m.get("year", years[0])) != y:
                continue
            cond = m.get("if_future")
            if cond is not None:
                want = [cond] if isinstance(cond, str) else list(cond)
                if future is None or future.name not in want:
                    continue
            todo.append((i, m))
        delta: dict = {}
        for i, m in todo:
            if m.get("op") in ONE_TIME:
                before = _flows(state)
                _apply(state, y, m, i)
                after = _flows(state)
                for pid in after:
                    d = [a - b for a, b in zip(after[pid], before.get(pid, [0.0] * len(after[pid])))]
                    delta[pid] = [x + z for x, z in zip(delta.get(pid, [0.0] * len(d)), d)]
            else:
                _apply(state, y, m, i)
        try:
            state.validate()
        except ValueError as e:
            raise MoveError(str(e)) from e
        year_hh = copy.deepcopy(state)
        year_hh.year = y
        for pid, p in year_hh.people.items():
            for a in p.assets:
                if a.sale_year == y and a.unrealized_gain > 0:
                    p.ltcg += a.unrealized_gain
                    _tag_gift_gain(p, a, y, a.unrealized_gain)
            sp = state.people[pid]
            for a in sp.assets:
                if a.sale_year == y:
                    a.basis = max(a.basis, a.value)
        for pid, d in delta.items():
            sp = state.people[pid]
            for f, x in zip(FLOWS, d):
                setattr(sp, f, getattr(sp, f) - x)
            for k, x in zip(OTHER_FLOWS, d[len(FLOWS):]):
                if k in sp.other or x:
                    sp.other[k] = sp.other.get(k, 0.0) - x
                    if abs(sp.other[k]) < 1e-9:
                        del sp.other[k]
        out.append(year_hh)
    return out
