"""A discretized move grid for a household (gate check 2, beam baseline).

`grid_moves(hh)` lists single moves with discretized amounts, each dated in
every year of the horizon. `sequences(hh, k)` enumerates valid sequences of
k grid moves (order-insensitive: one ordering per multiset), with duplicate
pruning.
"""

from __future__ import annotations

import itertools
import json

from .model import Household
from .moves import MoveError, horizon, limits, years_of


def _base_moves(hh: Household) -> list[dict]:
    out = []
    people = list(hh.people)
    for tu in hh.tax_units:
        if tu.spouse:
            out.append({"op": "set_filing_status", "tax_unit": tu.id, "status": "SEPARATE"})
        elif tu.dependents and hh.spouse_of(tu.head) is None:
            out.append({"op": "set_filing_status", "tax_unit": tu.id, "status": "SINGLE"})
    units = [tu.id for tu in hh.tax_units]
    # the unit a SEPARATE split would create
    split = [f"{tu.id}_s" for tu in hh.tax_units if tu.spouse]
    for tu in hh.tax_units:
        for d in tu.dependents:
            for dst in units + split:
                if dst != tu.id:
                    out.append({"op": "assign_dependent", "dependent": d, "tax_unit": dst})
    for p in hh.people.values():
        for a in p.assets:
            for q in people:
                if q != p.id:
                    for f in (0.5, 1.0):
                        out.append({"op": "gift_asset", "giver": p.id, "recipient": q, "asset": a.id, "fraction": f})
            if a.unrealized_gain > 0:
                out.append({"op": "realize_gain", "person": p.id, "asset": a.id, "fraction": 1.0})
                out.append({"op": "donate_asset", "person": p.id, "asset": a.id, "fraction": 0.1})
        if p.self_employment > 0:
            for q in people:
                if q != p.id:
                    for s in (0.25, 0.5, 1.0):
                        out.append({"op": "shift_income", "payer": p.id, "payee": q, "amount": round(s * p.self_employment, 2)})
        filer = any(p.id in (tu.head, tu.spouse) for tu in hh.tax_units)
        if filer and p.wages > 0:
            cap = min(limits(hh.year, p.age)["401k"], p.wages) - p.k401
            for s in (0.5, 1.0):
                if cap > 0:
                    out.append({"op": "contribute_retirement", "person": p.id, "account": "401k", "amount": round(s * cap, 2)})
        if filer and p.earned_income > 0:
            cap = min(limits(hh.year, p.age)["ira"], p.earned_income) - p.ira_contrib
            if cap > 0:
                out.append({"op": "contribute_retirement", "person": p.id, "account": "ira", "amount": round(cap, 2)})
        if p.hdhp:
            out.append({"op": "contribute_hsa", "person": p.id, "amount": limits(hh.year, p.age)["hsa_self"], "coverage": "self"})
        if p.charitable_cash > 0:
            out.append({"op": "reduce_donation", "person": p.id, "amount": round(p.charitable_cash, 2)})
            out.append({"op": "donate_cash", "person": p.id, "amount": round(p.charitable_cash, 2)})
        if p.ira_balance > 0:
            for s in (0.25, 1.0):
                out.append({"op": "roth_convert", "person": p.id, "amount": round(s * min(p.ira_balance, 100_000), 2)})
    return out


def grid_moves(hh: Household, dated: bool = True) -> list[dict]:
    years = horizon(hh) if dated else [hh.year]
    out = []
    for m in _base_moves(hh):
        for y in years:
            mm = dict(m)
            if y != hh.year:
                mm["year"] = y
            out.append(mm)
    return out


def _valid(hh: Household, seq: list) -> bool:
    try:
        for f in hh.futures or [None]:
            years_of(hh, seq, f)
        return True
    except (MoveError, KeyError, ValueError):
        return False


def sequences(hh: Household, k: int, dated: bool = True, limit: int | None = None):
    """Valid k-move sequences of grid moves; moves sorted by year then grid
    order (one ordering per combination, the natural one)."""
    if k == 0:
        yield []
        return
    gm = grid_moves(hh, dated)
    order = {json.dumps(m, sort_keys=True): i for i, m in enumerate(gm)}
    n = 0
    for combo in itertools.combinations(range(len(gm)), k):
        seq = sorted((gm[i] for i in combo), key=lambda m: (m.get("year", hh.year), order[json.dumps(m, sort_keys=True)]))
        if _valid(hh, seq):
            yield seq
            n += 1
            if limit and n >= limit:
                return
