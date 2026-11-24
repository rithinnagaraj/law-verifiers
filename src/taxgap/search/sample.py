"""Random valid move sequences (continuous amounts, dated, contingent).

`random_moves(hh, rng)` draws one move applicable to the household as it
stands after earlier moves; `random_sequence(hh, rng)` draws 1-3 moves and
keeps drawing until the sequence is valid over the horizon in every future.
"""

from __future__ import annotations

import copy
from typing import Optional

import numpy as np

from ..model import Household
from ..moves import MoveError, _apply, horizon, limits, years_of

OPS = (
    "set_filing_status",
    "assign_dependent",
    "gift_asset",
    "shift_income",
    "contribute_retirement",
    "realize_gain",
    "contribute_hsa",
    "donate_cash",
    "reduce_donation",
    "donate_asset",
    "roth_convert",
    "set_hours",
)
# set_hours is a real change of reality: drawn rarely.
WEIGHTS = np.array([1.0] * 11 + [0.25])


def _filers(hh: Household) -> list[str]:
    return [m for tu in hh.tax_units for m in (tu.head, tu.spouse) if m]


def candidates(hh: Household, rng: np.random.Generator, year: int) -> list[dict]:
    """One concrete move per applicable op (amounts drawn at random)."""
    out = []
    people = list(hh.people)
    u = lambda lo=0.05, hi=1.0: float(rng.uniform(lo, hi))
    pick = lambda xs: xs[int(rng.integers(len(xs)))]
    # filing status
    fs = []
    for tu in hh.tax_units:
        if tu.spouse:
            fs.append({"op": "set_filing_status", "tax_unit": tu.id, "status": "SEPARATE"})
        elif hh.spouse_of(tu.head) and hh.unit_of(hh.spouse_of(tu.head)).head == hh.spouse_of(tu.head):
            fs.append({"op": "set_filing_status", "tax_unit": tu.id, "status": "JOINT"})
        elif tu.dependents:
            fs.append({"op": "set_filing_status", "tax_unit": tu.id, "status": pick(["HEAD_OF_HOUSEHOLD", "SINGLE"])})
    if fs:
        out.append(pick(fs))
    deps = [(d, tu.id) for tu in hh.tax_units for d in tu.dependents]
    if deps and len(hh.tax_units) > 1:
        d, src = pick(deps)
        dst = pick([tu.id for tu in hh.tax_units if tu.id != src])
        out.append({"op": "assign_dependent", "dependent": d, "tax_unit": dst})
    owners = [(p.id, a.id) for p in hh.people.values() for a in p.assets if a.value > 0]
    if owners and len(people) > 1:
        g, a = pick(owners)
        out.append({"op": "gift_asset", "giver": g, "recipient": pick([q for q in people if q != g]), "asset": a, "fraction": round(u(), 3)})
    se = [p.id for p in hh.people.values() if p.self_employment > 1_000]
    if se and len(people) > 1:
        s = pick(se)
        out.append({"op": "shift_income", "payer": s, "payee": pick([q for q in people if q != s]), "amount": round(u(0.02, 1.0) * hh.people[s].self_employment, 0)})
    workers = [pid for pid in _filers(hh) if hh.people[pid].earned_income > 1_000]
    if workers:
        w = pick(workers)
        p = hh.people[w]
        lim = limits(year, p.age)
        acct = pick(["401k", "ira"]) if p.wages > 0 else "ira"
        cap = (min(lim["401k"], p.wages) - p.k401) if acct == "401k" else (min(lim["ira"], p.earned_income) - p.ira_contrib)
        if cap > 100:
            out.append({"op": "contribute_retirement", "person": w, "account": acct, "amount": round(u() * cap, 0)})
    gains = [(p.id, a.id) for p in hh.people.values() for a in p.assets if a.unrealized_gain > 0]
    if gains:
        p, a = pick(gains)
        out.append({"op": "realize_gain", "person": p, "asset": a, "fraction": round(u(), 3)})
    hd = [p.id for p in hh.people.values() if p.hdhp and p.earned_income > 0]
    if hd:
        h = pick(hd)
        cov = pick(["self", "family"])
        cap = limits(year, hh.people[h].age)["hsa_family" if cov == "family" else "hsa_self"] - hh.people[h].hsa
        if cap > 100:
            out.append({"op": "contribute_hsa", "person": h, "amount": round(u() * cap, 0), "coverage": cov})
    earners = [p for p in hh.people.values() if p.gross_income > 5_000]
    if earners:
        p = pick(earners)
        out.append({"op": "donate_cash", "person": p.id, "amount": round(u(0.005, 0.1) * p.gross_income, 0)})
    givers = [p for p in hh.people.values() if p.charitable_cash > 100]
    if givers:
        p = pick(givers)
        out.append({"op": "reduce_donation", "person": p.id, "amount": round(u() * p.charitable_cash, 0)})
    if gains:
        p, a = pick(gains)
        out.append({"op": "donate_asset", "person": p, "asset": a, "fraction": round(u(0.01, 0.3), 3)})
    iras = [p for p in hh.people.values() if p.ira_balance > 1_000]
    if iras:
        p = pick(iras)
        out.append({"op": "roth_convert", "person": p.id, "amount": round(u(0.01, 1.0) * min(p.ira_balance, 100_000), 0)})
    wage = [p for p in hh.people.values() if p.wages > 0 and p.hours > 0]
    if wage:
        p = pick(wage)
        out.append({"op": "set_hours", "person": p.id, "hours": round(p.hours * u(0.5, 1.0), 0)})
    return out


def random_move(hh: Household, rng: np.random.Generator, year: int) -> Optional[dict]:
    cs = candidates(hh, rng, year)
    if not cs:
        return None
    w = np.array([WEIGHTS[OPS.index(c["op"])] for c in cs])
    return cs[int(rng.choice(len(cs), p=w / w.sum()))]


def random_sequence(hh: Household, rng: np.random.Generator, max_len: int = 3, tries: int = 50, dated: bool = True, contingent: bool = True) -> list:
    """A valid sequence of 1..max_len moves (moves applied in year order)."""
    years = horizon(hh)
    reveal = min((f.from_year for f in hh.futures), default=None)
    for _ in range(tries):
        n = int(rng.integers(1, max_len + 1))
        ys = sorted(int(rng.choice(years)) if dated else years[0] for _ in range(n))
        state = copy.deepcopy(hh)
        seq = []
        try:
            for i, y in enumerate(ys):
                m = random_move(state, rng, y)
                if m is None:
                    break
                _apply(state, y, m, i)
                if y != years[0]:
                    m["year"] = y
                if contingent and hh.futures and reveal is not None and y >= reveal and rng.random() < 0.25:
                    m["if_future"] = hh.futures[int(rng.integers(len(hh.futures)))].name
                seq.append(m)
        except (MoveError, KeyError, ValueError):
            continue
        if not seq:
            continue
        try:
            for f in hh.futures or [None]:
                years_of(hh, seq, f)
        except (MoveError, KeyError, ValueError):
            continue
        return seq
    return []
