"""The action vocabulary (research plan §5.2).

A move is a JSON-serialisable dict {"op": name, ...args}. `apply_moves`
returns a new household; the input is never mutated. Invalid moves raise
MoveError, which the verifier reports as an invalid proposal.
"""

from __future__ import annotations

from typing import Callable

from .household import FILING_STATUSES, Asset, Household, TaxUnit


class MoveError(ValueError):
    pass


def _person(hh: Household, pid: str):
    if pid not in hh.people:
        raise MoveError(f"unknown person {pid!r}")
    return hh.people[pid]


def _fraction(x) -> float:
    x = float(x)
    if not 0 < x <= 1:
        raise MoveError(f"fraction must be in (0, 1], got {x}")
    return x


def set_filing_status(hh: Household, tax_unit: str, status: str) -> None:
    """JOINT merges a married couple into one unit; SEPARATE splits them.
    For other units, only SINGLE / HEAD_OF_HOUSEHOLD may be asserted (and are
    then subject to each calculator's eligibility rules)."""
    if status not in FILING_STATUSES:
        raise MoveError(f"unknown filing status {status!r}")
    tu = hh.tax_unit(tax_unit)
    if status == "SEPARATE":
        if not tu.spouse:
            raise MoveError("SEPARATE needs a married unit (head and spouse)")
        new = TaxUnit(f"{tu.id}_s", tu.spouse, filing_status="SEPARATE")
        tu.spouse = None
        tu.filing_status = "SEPARATE"
        hh.tax_units.append(new)
    elif status == "JOINT":
        spouse = hh.spouse_of(tu.head)
        if spouse is None:
            raise MoveError("JOINT needs a married head")
        other = hh.unit_of(spouse)
        if other.id == tu.id:
            tu.filing_status = None
            return
        if other.head != spouse:
            raise MoveError("spouse is a dependent elsewhere")
        tu.spouse = spouse
        tu.dependents += other.dependents
        tu.filing_status = None
        hh.tax_units.remove(other)
    else:
        if tu.spouse:
            raise MoveError(f"a married unit cannot file {status}")
        tu.filing_status = status


def gift_asset(hh: Household, giver: str, recipient: str, asset: str, fraction: float = 1.0) -> None:
    """Transfer (part of) an asset within the household, basis carried over."""
    g, r = _person(hh, giver), _person(hh, recipient)
    if giver == recipient:
        raise MoveError("giver == recipient")
    f = _fraction(fraction)
    a = g.asset(asset)
    moved = Asset(
        id=f"{a.id}@{recipient}",
        value=a.value * f,
        basis=a.basis * f,
        interest_yield=a.interest_yield,
        qualified_dividend_yield=a.qualified_dividend_yield,
    )
    a.value *= 1 - f
    a.basis *= 1 - f
    if a.value <= 0:
        g.assets.remove(a)
    existing = next((x for x in r.assets if x.id == moved.id), None)
    if existing:
        existing.value += moved.value
        existing.basis += moved.basis
    else:
        r.assets.append(moved)


def shift_income(hh: Household, payer: str, payee: str, amount: float) -> None:
    """The payer's business pays the payee wages for work in it: the payer's
    self-employment income falls by `amount`, the payee's wages rise by it.
    Hours move with the pay at the payer's implied hourly rate."""
    p, q = _person(hh, payer), _person(hh, payee)
    amount = float(amount)
    if amount <= 0 or amount > p.self_employment:
        raise MoveError("amount must be positive and at most the payer's self-employment income")
    rate_hours = p.hours * (amount / p.earned_income) if p.earned_income else 0.0
    p.self_employment -= amount
    q.wages += amount
    p.hours -= rate_hours
    q.hours += rate_hours


def realize_gain(hh: Household, person: str, asset: str, fraction: float = 1.0) -> None:
    """Sell and immediately repurchase (part of) an asset: the unrealized gain
    on it becomes a realized long-term gain and its basis steps up."""
    p = _person(hh, person)
    f = _fraction(fraction)
    a = p.asset(asset)
    gain = (a.value - a.basis) * f
    p.long_term_gains += gain
    a.basis += gain


def assign_dependent(hh: Household, dependent: str, tax_unit: str) -> None:
    _person(hh, dependent)
    src = hh.unit_of(dependent)
    if dependent not in src.dependents:
        raise MoveError(f"{dependent} is not currently a dependent")
    dst = hh.tax_unit(tax_unit)
    if dst.id == src.id:
        raise MoveError("already in that unit")
    src.dependents.remove(dependent)
    dst.dependents.append(dependent)
    if not src.dependents and src.filing_status == "HEAD_OF_HOUSEHOLD":
        src.filing_status = None


def set_hours(hh: Household, person: str, hours: float) -> None:
    """Change hours worked; wages scale at the person's current hourly wage."""
    p = _person(hh, person)
    hours = float(hours)
    if hours < 0 or hours > 4000:
        raise MoveError("hours must be in [0, 4000]")
    if p.hours <= 0:
        raise MoveError("person has no current hours to scale from")
    rate = p.wages / p.hours
    p.wages = rate * hours
    p.hours = hours


def itemize_or_standard(hh: Household, tax_unit: str, itemize: bool) -> None:
    hh.tax_unit(tax_unit).itemize = bool(itemize)


MOVES: dict[str, Callable] = {
    "set_filing_status": set_filing_status,
    "gift_asset": gift_asset,
    "shift_income": shift_income,
    "realize_gain": realize_gain,
    "assign_dependent": assign_dependent,
    "set_hours": set_hours,
    "itemize_or_standard": itemize_or_standard,
}


def apply_moves(hh: Household, moves: list[dict]) -> Household:
    out = hh.copy()
    for i, m in enumerate(moves):
        m = dict(m)
        op = m.pop("op", None)
        if op not in MOVES:
            raise MoveError(f"move {i}: unknown op {op!r}")
        try:
            MOVES[op](out, **m)
        except MoveError:
            raise
        except (KeyError, TypeError) as e:
            raise MoveError(f"move {i} ({op}): {e}") from e
    try:
        out.validate()
    except ValueError as e:
        raise MoveError(str(e)) from e
    return out
