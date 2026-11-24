"""Batched, memoized evaluation of household-years under a law.

`evaluate(households, law)` takes households that are each already the
household of one tax year, and returns each one's federal income tax under
both calculators (Form 8615 included). Results are memoized per process by
(law, household content): the same household-year under the same law is
never computed twice (baselines, shared first years of the futures,
repeated proposals). `with_tc=False` computes PolicyEngine only (the
verifier's attribution). `fresh=True` bypasses the memo and evaluates the
given items in a batch of their own; the verifier uses it to re-check
flagged proposals against batch-composition bugs.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from typing import Sequence

from ..law import Law
from ..model import Household, compile_returns
from . import kiddie, pe, tc

MEMO_MAX = 400_000
BATCH_RETURNS = 1_500  # returns per calculator call


@dataclass(frozen=True)
class YearTax:
    pe: float  # federal income tax, PolicyEngine (kiddie tax included)
    tc: float  # federal income tax, Tax-Calculator (kiddie tax included); nan if not computed
    pe_only: float  # PolicyEngine-only federal credits (saver's credit), part of pe
    kiddie_pe: float  # Form 8615 tax computed by this package, part of pe
    kiddie_tc: float


_memo: "OrderedDict[tuple, YearTax]" = OrderedDict()
stats = {"hits": 0, "misses": 0, "pe_calls": 0, "tc_calls": 0, "returns": 0}


def clear_memo() -> None:
    _memo.clear()


def _chunks(per_hh: list) -> list:
    chunks, cur, n = [], [], 0
    for rs in per_hh:
        if cur and n + len(rs) > BATCH_RETURNS:
            chunks.append(cur)
            cur, n = [], 0
        cur += rs
        n += len(rs)
    if cur:
        chunks.append(cur)
    return chunks


def _compute(items: Sequence[Household], law: Law, with_tc: bool) -> list[YearTax]:
    year = items[0].year
    per_hh = [compile_returns(h, f"h{i}", year) for i, h in enumerate(items)]
    pe_res, tc_res, adj_pe, adj_tc = {}, {}, {}, {}
    for chunk in _chunks(per_hh):
        stats["pe_calls"] += 1
        stats["returns"] += len(chunk)
        pr = pe.evaluate(chunk, law)
        salt = {k: r.salt for k, r in pr.items()}
        adj_pe.update(kiddie.adjustments(chunk, pr, law, lambda rs, s: pe.evaluate(rs, law, s), salt))
        pe_res.update(pr)
        if with_tc:
            stats["tc_calls"] += 1
            tr = tc.evaluate(chunk, law, salt)
            adj_tc.update(kiddie.adjustments(chunk, tr, law, lambda rs, s: tc.evaluate(rs, law, s), salt))
            tc_res.update(tr)
    out = []
    for rs in per_hh:
        kp = sum(adj_pe.get(r.key, 0.0) for r in rs)
        kt = sum(adj_tc.get(r.key, 0.0) for r in rs)
        out.append(
            YearTax(
                pe=sum(pe_res[r.key].fed_tax for r in rs) + kp,
                tc=sum(tc_res[r.key].fed_tax for r in rs) + kt if with_tc else math.nan,
                pe_only=sum(pe_res[r.key].pe_only_credits for r in rs),
                kiddie_pe=kp,
                kiddie_tc=kt if with_tc else math.nan,
            )
        )
    return out


def _by_year(items: Sequence[Household], idx: list) -> dict:
    out: dict[int, list] = {}
    for i in idx:
        out.setdefault(items[i].year, []).append(i)
    return out


def evaluate(items: Sequence[Household], law: Law, fresh: bool = False, with_tc: bool = True) -> list[YearTax]:
    if not items:
        return []
    res: list = [None] * len(items)
    if fresh:
        for _, idx in _by_year(items, range(len(items))).items():
            for i, r in zip(idx, _compute([items[i] for i in idx], law, with_tc)):
                res[i] = r
        return res
    lk = law.key()
    todo: dict[str, list[int]] = {}
    for i, h in enumerate(items):
        hk = h.key()
        hit = _memo.get((lk, hk, True)) or (None if with_tc else _memo.get((lk, hk, False)))
        if hit is not None:
            stats["hits"] += 1
            res[i] = hit
        else:
            todo.setdefault(hk, []).append(i)
    if todo:
        stats["misses"] += len(todo)
        first = [idx[0] for idx in todo.values()]
        for _, idx in _by_year(items, first).items():
            for i, r in zip(idx, _compute([items[i] for i in idx], law, with_tc)):
                hk = items[i].key()
                _memo[(lk, hk, with_tc)] = r
                for j in todo[hk]:
                    res[j] = r
        while len(_memo) > MEMO_MAX:
            _memo.popitem(last=False)
    return res
