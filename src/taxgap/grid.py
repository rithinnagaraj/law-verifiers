"""A discretized move grid for a household (gate check 2, beam baseline).

`grid_moves(hh)` lists single moves with discretized amounts, each dated in
every year of the horizon. `sequences(hh, k)` enumerates valid sequences of
k grid moves (order-insensitive: one ordering per multiset), with duplicate
pruning.

Moves opened by an earlier move (DECISIONS, 2026-11-28): a sequence may also
contain grid moves of the household as it stands after one earlier grid move
(its opener) that are not grid moves of the starting household, such as the
sale of an asset just received as a gift. They are dated in the opener's
year or later, follow it, and need it in the sequence. One level only: moves
opened by an opened move are not enumerated.
"""

from __future__ import annotations

import copy
import itertools
import json

from .model import Household
from .moves import MoveError, _apply, horizon, limits, years_of


def _key(m: dict) -> str:
    return json.dumps(m, sort_keys=True)


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


def opened_moves(hh: Household, dated: bool = True) -> list[tuple[int, dict]]:
    """[(index of the opener in grid_moves(hh), move)]: the grid moves of the
    household after that one grid move that are not grid moves of the
    starting household, dated in the opener's year or later."""
    gm = grid_moves(hh, dated)
    start = {_key(m) for m in _base_moves(hh)}
    years = horizon(hh) if dated else [hh.year]
    out = []
    for i, o in enumerate(gm):
        y = o.get("year", hh.year)
        state = copy.deepcopy(hh)
        try:
            _apply(state, y, o, 0)
        except (MoveError, KeyError, ValueError):
            continue
        for m in _base_moves(state):
            if _key(m) in start:
                continue
            for y2 in years:
                if y2 >= y:
                    mm = dict(m)
                    if y2 != hh.year:
                        mm["year"] = y2
                    out.append((i, mm))
    return out


def n_opened(hh: Household, seqs: list, dated: bool = True) -> int:
    """How many of the sequences contain a move that is not a grid move of the starting household."""
    gk = {_key(m) for m in grid_moves(hh, dated)}
    return sum(any(_key(m) not in gk for m in s) for s in seqs)


def sequences(hh: Household, k: int, dated: bool = True, limit: int | None = None):
    """Valid k-move sequences of grid moves; moves sorted by year then grid
    order (one ordering per combination, the natural one). Combinations of
    the starting household's grid moves come first, then sequences with a
    move opened by an earlier one (each multiset once)."""
    if k == 0:
        yield []
        return
    gm = grid_moves(hh, dated)
    order = {_key(m): i for i, m in enumerate(gm)}
    yr = lambda m: m.get("year", hh.year)
    n = 0
    for combo in itertools.combinations(range(len(gm)), k):
        seq = sorted((gm[i] for i in combo), key=lambda m: (yr(m), order[_key(m)]))
        if _valid(hh, seq):
            yield seq
            n += 1
            if limit and n >= limit:
                return
    if k < 2:
        return  # an opened move needs its opener in the sequence
    seen = set()
    for o, m in opened_moves(hh, dated):
        others = [i for i in range(len(gm)) if i != o]
        for combo in itertools.combinations(others, k - 2):
            seq = sorted((gm[i] for i in (*combo, o)), key=lambda x: (yr(x), order[_key(x)]))
            pos = sum(1 for x in seq if yr(x) <= yr(m))  # after every move of its year, so after the opener
            seq = seq[:pos] + [m] + seq[pos:]
            key = tuple(sorted(_key(x) for x in seq))
            if key in seen:
                continue
            seen.add(key)
            if _valid(hh, seq):
                yield seq
                n += 1
                if limit and n >= limit:
                    return
