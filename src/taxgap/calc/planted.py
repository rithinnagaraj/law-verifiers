"""Planted provisions of the hand-authored catalog (DECISIONS, 2026-11-27),
implemented in this package on top of each calculator, as Form 8615 is.

Real law (`Law.planted` at its default) has none of them, and every function
here is then the identity / zero.

Donor attribution (`gift_window`): a long-term gain realized on property
received by gift from a household member, in the gift year (0) or the next
year (1) when that year is in the window, is taxed to the donor. It moves
to the donor's return before either calculator runs, so both calculators
tax it natively.

Small-investor credit (`investor_rate`): rate x min(the return's realized
long-term gains, cap), for returns whose AGI (each calculator's own) is
below the saver's-credit AGI limit for the filing status and year;
nonrefundable (limited to the return's income tax after every other
credit, the kiddie tax included); a return claimed as a dependent gets
`investor_dep_share` of it. Gains from it are shared code: the cross-check
cannot vouch for them.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from ..law import Law
from ..model import Household, Return
from . import ReturnResult

_SAVERS = "gov.irs.credits.retirement_saving.rate"


def attribute_gifts(hh: Household, law: Law) -> Household:
    """The household with recent-gift gains moved to their donors (a copy),
    or `hh` itself when nothing moves."""
    win = law.planted.gift_window
    if not win:
        return hh
    moves = []
    for pid, p in hh.people.items():
        amt = (p.gift_ltcg_y0 if 0 in win else 0.0) + (p.gift_ltcg_y1 if 1 in win else 0.0)
        amt = min(amt, p.ltcg)
        if amt > 0 and p.gift_donor in hh.people and p.gift_donor != pid:
            moves.append((pid, p.gift_donor, amt))
    if not moves:
        return hh
    out = hh.copy()
    for pid, donor, amt in moves:
        out.people[pid].ltcg -= amt
        out.people[donor].ltcg += amt
    return out


@lru_cache(maxsize=64)
def agi_limit(status: str, year: int) -> float:
    """The saver's-credit AGI limit (the joint 10%-tier end x the status adjustment)."""
    from ..params import pe_system

    p = pe_system().parameters.gov.irs.credits.retirement_saving.rate
    d = f"{year}-01-01"
    top = float(p.joint(d).thresholds[-1])
    key = "JOINT" if status == "SURVIVING_SPOUSE" else status
    return top * float(p.threshold_adjustment.children[key](d))


def credits(returns: Sequence[Return], results: dict[str, ReturnResult], law: Law, other_adj: dict) -> dict[str, float]:
    """{return key: -credit} (a tax change) for the small-investor credit.
    `other_adj`: package adjustments already applied (the kiddie tax)."""
    pl = law.planted
    if pl.investor_rate <= 0 or not returns:
        return {}
    out = {}
    for r in returns:
        share = pl.investor_dep_share if r.claimed_by is not None else 1.0
        if share <= 0:
            continue
        gains = sum(m.person.ltcg for m in r.members if m.income_on_return)
        if gains <= 0:
            continue
        res = results[r.key]
        if res.agi >= agi_limit(r.filing_status, r.year):
            continue
        tax = res.fed_tax + other_adj.get(r.key, 0.0)
        c = min(pl.investor_rate * min(gains, pl.investor_cap) * share, max(tax, 0.0))
        if c > 0:
            out[r.key] = -c
    return out
