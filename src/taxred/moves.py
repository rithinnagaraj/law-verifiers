"""The action vocabulary (research plan §5.2).

A move is a JSON-serialisable dict {"op": name, ...args}. `apply_moves`
returns a new household; the input is never mutated. Invalid moves raise
MoveError, which the verifier reports as an invalid proposal.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

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
        sale_year=a.sale_year,
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
    if gain < 0:
        # Wash sale (IRC s.1091): a loss on a sale followed by an immediate
        # repurchase is disallowed and added to the new basis. Neither
        # calculator knows about repurchases, so the rule lives here; without
        # it an agent is paid up to $3,000/yr of fake loss deductions.
        return
    p.long_term_gains += gain
    a.basis += gain


def _retirement_limits(year: int, age: int) -> dict:
    from .taxes import _pe_params

    r = _pe_params().gov.irs.gross_income.retirement_contributions
    d = f"{year}-01-01"
    catch_up = age >= r.catch_up.age_threshold(d)
    # The 401(k) catch-up is a scale by age (SECURE 2.0 adds a 60-63 tier).
    return {
        "401k": float(getattr(r.limit, "401k")(d)) + float(np.asarray(r.catch_up.limit.k401(d).calc(np.array([float(age)])))[0]),
        "ira": float(r.limit.ira(d)) + catch_up * float(r.catch_up.limit.ira(d)),
    }


def contribute_retirement(hh: Household, person: str, account: str, amount: float) -> None:
    """Make a pre-tax retirement contribution out of this year's pay.

    account "401k": an elective deferral from wages (an employer plan is
    assumed), up to the statutory limit incl. catch-up. account "ira": a
    traditional IRA contribution, allowed only when it is fully deductible
    under the rules both calculators share: nobody in the person's tax unit
    makes a 401(k) deferral (no active participant, IRC s.219(g)), and it is
    within the limit and the person's compensation. Gross pay and wealth are
    unchanged (cash moves into a retirement account)."""
    p = _person(hh, person)
    amount = float(amount)
    if amount <= 0:
        raise MoveError("amount must be positive")
    lim = _retirement_limits(hh.year, p.age)
    tu = hh.unit_of(person)
    if person not in (tu.head, tu.spouse):
        raise MoveError("only a filer (head or spouse) can contribute")
    unit_people = [hh.people[m] for m in (tu.head, tu.spouse) if m]
    if account == "401k":
        if p.traditional_401k + amount > lim["401k"] + 1e-6:
            raise MoveError(f"401(k) limit is {lim['401k']:.0f}")
        if p.traditional_401k + amount > p.wages:
            raise MoveError("401(k) deferral exceeds wages")
        if any(q.traditional_ira > 0 for q in unit_people):
            raise MoveError("an IRA contribution in this unit would become partly non-deductible")
        p.traditional_401k += amount
    elif account == "ira":
        if any(q.traditional_401k > 0 for q in unit_people):
            raise MoveError("someone in this unit is an active plan participant (IRA deduction limited)")
        if p.traditional_ira + amount > lim["ira"] + 1e-6:
            raise MoveError(f"IRA limit is {lim['ira']:.0f}")
        if p.traditional_ira + amount > p.earned_income:
            raise MoveError("IRA contribution exceeds compensation")
        p.traditional_ira += amount
    else:
        raise MoveError(f"unknown account {account!r}")


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
    "contribute_retirement": contribute_retirement,
}




# ---------------------------------------------------------------------------
# Stage 1 moves (bright-line statutory rules only)
# ---------------------------------------------------------------------------

HSA_CATCH_UP = 1_000.0  # s.223(b)(3)(B), not indexed


def contribute_hsa(hh: Household, person: str, amount: float, coverage: str = "self") -> None:
    """HSA contribution (deductible, s.223). Requires HDHP coverage; within the
    self-only or family limit, plus $1,000 at 55+. Cash moves into the HSA:
    wealth unchanged."""
    from .taxes import _pe_params

    p = _person(hh, person)
    amount = float(amount)
    if amount <= 0:
        raise MoveError("amount must be positive")
    if not p.hdhp:
        raise MoveError("not covered by a high-deductible health plan")
    if coverage not in ("self", "family"):
        raise MoveError("coverage is self or family")
    lim = _pe_params().gov.irs.gross_income.health_savings_account_contributions.limit
    d = f"{hh.year}-01-01"
    cap = float((lim.family if coverage == "family" else lim.self_only)(d)) + (HSA_CATCH_UP if p.age >= 55 else 0.0)
    if p.hsa + amount > cap + 1e-6:
        raise MoveError(f"HSA limit is {cap:.0f}")
    if p.hsa + amount > p.earned_income + sum(q.earned_income for q in hh.people.values() if hh.spouse_of(person) == q.id):
        raise MoveError("HSA contribution exceeds the household's pay (modelled as funded from pay)")
    p.hsa += amount


def donate_cash(hh: Household, person: str, amount: float) -> None:
    """A cash gift to a public charity this year (one-time when dated). The
    money leaves the household."""
    p = _person(hh, person)
    amount = float(amount)
    if amount <= 0:
        raise MoveError("amount must be positive")
    p.charitable_cash += amount
    p.given_away += amount


def reduce_donation(hh: Household, person: str, amount: float) -> None:
    """Give less in cash this year than the household normally does (one-time
    when dated); with donate_cash in another year this bunches giving."""
    p = _person(hh, person)
    amount = float(amount)
    if amount <= 0 or amount > p.charitable_cash + 1e-6:
        raise MoveError("can only reduce the cash this person gives this year")
    p.charitable_cash -= amount
    p.given_away -= amount


DONATE_ASSET_CAP = 0.2  # share of the household's gross income (vocabulary rule)


def donate_asset(hh: Household, person: str, asset: str, fraction: float = 1.0) -> None:
    """Give (part of) a long-held appreciated asset to a public charity: a
    deduction at fair market value and no capital gain (one-time when dated).
    Vocabulary rule: at most 20% of the household's gross income per year,
    below the AGI limits (30%/50%) that only PolicyEngine applies, so both
    calculators see the same deduction."""
    p = _person(hh, person)
    f = _fraction(fraction)
    a = p.asset(asset)
    value = a.value * f
    gross = sum(q.earned_income + q.unearned_income for q in hh.people.values())
    if value + sum(q.charitable_noncash for q in hh.people.values()) > DONATE_ASSET_CAP * max(gross, 0.0):
        raise MoveError("donated property above 20% of household income (vocabulary limit)")
    a.value *= 1 - f
    a.basis *= 1 - f
    if a.value <= 0:
        p.assets.remove(a)
    p.charitable_noncash += value
    p.given_away += value


def roth_convert(hh: Household, person: str, amount: float) -> None:
    """Convert part of a traditional IRA to a Roth IRA: the amount is a taxable
    IRA distribution this year (one-time when dated). Wealth unchanged (the
    balance moves accounts). No recharacterization (repealed for conversions
    after 2017; see the scenario extension)."""
    p = _person(hh, person)
    amount = float(amount)
    if amount <= 0 or amount > p.ira_balance + 1e-6:
        raise MoveError("amount must be positive and at most the traditional IRA balance")
    p.ira_balance -= amount
    p.roth_balance += amount
    p.other["ira_distributions"] = p.other.get("ira_distributions", 0.0) + amount


def recharacterize(hh: Household, person: str, amount: float, of_year: int) -> None:
    """Undo (part of) a Roth conversion made in `of_year` (allowed only by the
    following year, and only under law that permits it). Its effect is
    resolved in household_in_year; applied directly it only checks its inputs."""
    _person(hh, person)
    if float(amount) <= 0:
        raise MoveError("amount must be positive")


MOVES.update(
    {
        "recharacterize": recharacterize,
        "contribute_hsa": contribute_hsa,
        "donate_cash": donate_cash,
        "reduce_donation": reduce_donation,
        "donate_asset": donate_asset,
        "roth_convert": roth_convert,
    }
)


def apply_moves(hh: Household, moves: list[dict]) -> Household:
    out = hh.copy()
    for i, m in enumerate(moves):
        m = dict(m)
        m.pop("year", None)  # dating is handled by household_in_year
        m.pop("if_scenario", None)  # scenarios are resolved by household_in_year
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


# ---------------------------------------------------------------------------
# Multi-year horizon
# ---------------------------------------------------------------------------

ONE_TIME_OPS = ("realize_gain", "donate_cash", "reduce_donation", "donate_asset", "roth_convert", "contribute_hsa")
# Per-year flows that one-time moves change; their stock effects (basis,
# balances, given_away) persist.
FLOW_FIELDS = ("long_term_gains", "charitable_cash", "charitable_noncash", "hsa")


def _year_of(m: dict, start: int) -> int:
    try:
        return int(m.get("year", start))
    except (TypeError, ValueError) as e:
        raise MoveError("bad year") from e


def _resolve(hh: Household, moves: list[dict], scenario: dict | None, allow_recharacterization: bool = False) -> list[dict]:
    """The moves that apply in `scenario`: contingent moves ("if_scenario")
    are kept only in their scenarios and only once the future is known;
    recharacterizations cancel (part of) a conversion of the year they name
    where the law allows it, and have no effect where it does not (TCJA 2017
    repealed recharacterization of conversions: the conversion stands)."""
    start = hh.year
    out = []
    for i, m in enumerate(moves):
        y = _year_of(m, start)
        if y < start:
            raise MoveError(f"move {i}: year {y} before the horizon starts ({start})")
        cond = m.get("if_scenario")
        if cond is not None:
            if not hh.scenarios:
                raise MoveError(f"move {i}: contingent move, but the household has one future")
            names = [cond] if isinstance(cond, str) else list(cond)
            reveal = min(s["from_year"] for s in hh.scenarios)
            if y < reveal:
                raise MoveError(f"move {i}: depends on a future not known until {reveal}")
            if scenario is None or scenario["name"] not in names:
                continue
        out.append({k: v for k, v in m.items() if k != "if_scenario"})
    for m in [m for m in out if m.get("op") == "recharacterize" and allow_recharacterization]:
        of = int(m.get("of_year", start))
        d = _year_of(m, start)
        if not of <= d <= of + 1:
            raise MoveError("a conversion can be recharacterized only by the following year")
        left = float(m.get("amount", 0.0))
        if left <= 0:
            raise MoveError("amount must be positive")
        convs = [c for c in out if c.get("op") == "roth_convert" and c.get("person") == m.get("person") and _year_of(c, start) == of]
        if sum(float(c["amount"]) for c in convs) + 1e-6 < left:
            raise MoveError("recharacterizes more than was converted that year")
        for c in convs:
            take = min(left, float(c["amount"]))
            c["amount"] = float(c["amount"]) - take
            left -= take
        out = [c for c in out if not (c.get("op") == "roth_convert" and float(c["amount"]) <= 0)]
    return [m for m in out if m.get("op") != "recharacterize"]


def household_in_year(hh: Household, moves: list[dict], year: int, scenario: dict | None = None, allow_recharacterization: bool = False) -> Household:
    """The household as it stands in tax year `year` of a horizon starting at
    hh.year, simulated forward year by year.

    Facts repeat each year (a static household) unless a scenario changes the
    world: from its from_year on, asset values and IRA balances are scaled by
    asset_growth and wages by wage_factor. Moves dated (key "year") in a year
    apply from that year on; one-time events (ONE_TIME_OPS) count their flows
    only in their own year while their stock effects persist. Assets with a
    `sale_year` realize their remaining gain in that year (reinvested)."""
    start = hh.year
    moves = _resolve(hh, moves, scenario, allow_recharacterization)
    out = hh.copy()
    for y in range(start, year + 1):
        if scenario is not None and y == scenario["from_year"]:
            g, wf = float(scenario.get("asset_growth", 1.0)), float(scenario.get("wage_factor", 1.0))
            for p in out.people.values():
                p.wages *= wf
                p.self_employment *= wf
                for a in p.assets:
                    a.value *= g
                p.ira_balance *= g
                p.roth_balance *= g
        chunk: list[dict] = []
        for m in [m for m in moves if _year_of(m, start) == y]:
            m = {k: v for k, v in m.items() if k != "year"}
            if m.get("op") in ONE_TIME_OPS and y < year:
                if chunk:
                    out, chunk = apply_moves(out, chunk), []
                before = {pid: ({f: getattr(p, f) for f in FLOW_FIELDS}, dict(p.other)) for pid, p in out.people.items()}
                out = apply_moves(out, [m])
                for pid, (flows, other) in before.items():
                    for f, v in flows.items():
                        setattr(out.people[pid], f, v)
                    out.people[pid].other = other
            else:
                chunk.append(m)
        if chunk or y == start:
            out = apply_moves(out, chunk)
        for p in out.people.values():
            for a in p.assets:
                if a.sale_year == y and a.unrealized_gain > 0:
                    if y == year:
                        p.long_term_gains += a.unrealized_gain
                    a.basis = a.value
    out.year = year
    return out
