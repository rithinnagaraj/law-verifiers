"""Search over move sequences: proposers and a budgeted search loop.

Conditions in experiment plan E2.3 share this loop and differ only in the
proposer:

  RandomProposer      random valid move sequences (the random baseline)
  GreedyProposer      hill-climbing: extend / mutate the best sequences so
                      far (the heuristic baseline)
  (LLM proposers plug in through the same `propose(state)` interface.)

The budget unit is verifier calls (experiment plan §1.4). Every proposal is
one call; attribution of candidates is part of that call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Protocol

import numpy as np

from .household import Household
from .moves import MoveError, apply_moves
from .verifier import Verdict, Verifier

FLAGGED = ("candidate", "code_disagreement")


# ---------------------------------------------------------------------------
# Random valid moves
# ---------------------------------------------------------------------------


def _choice(rng, seq):
    return seq[int(rng.integers(len(seq)))]


def _frac(rng, continuous: bool, choices=(0.25, 0.5, 1.0), lo: float = 0.05, hi: float = 1.0) -> float:
    """A fraction: one of a few round values, or (stage 1) any value."""
    return round(float(rng.uniform(lo, hi)), 3) if continuous else float(_choice(rng, list(choices)))


def random_move(hh: Household, rng: np.random.Generator, continuous: bool = False) -> Optional[dict]:
    """One random move that is plausible for `hh` (it may still be invalid).
    continuous: draw fractions and amounts from a continuum (stage 1)."""
    people = list(hh.people)
    ops = []
    with_assets = [p for p in people if hh.people[p].assets]
    if with_assets and len(people) > 1:
        ops.append("gift_asset")
    if any(hh.people[p].self_employment > 0 for p in people) and len(people) > 1:
        ops.append("shift_income")
    if any(a.unrealized_gain > 0 for p in people for a in hh.people[p].assets):
        ops.append("realize_gain")
    if any(tu.dependents for tu in hh.tax_units) and (len(hh.tax_units) > 1 or len(people) > 1):
        ops.append("assign_dependent")
    if hh.married_pairs:
        ops.append("set_filing_status")
    if any(hh.people[p].hours > 0 for p in people):
        ops.append("set_hours")
    ops.append("itemize_or_standard")
    if any(hh.people[p].wages > 0 for p in people):
        ops.append("contribute_retirement")
    op = _choice(rng, ops)

    if op == "gift_asset":
        g = _choice(rng, with_assets)
        r = _choice(rng, [p for p in people if p != g])
        a = _choice(rng, hh.people[g].assets).id
        return {"op": op, "giver": g, "recipient": r, "asset": a, "fraction": _frac(rng, continuous)}
    if op == "shift_income":
        payer = _choice(rng, [p for p in people if hh.people[p].self_employment > 0])
        payee = _choice(rng, [p for p in people if p != payer])
        amt = round(hh.people[payer].self_employment * _frac(rng, continuous, (0.1, 0.25, 0.5), 0.02, 0.6), -1)
        return {"op": op, "payer": payer, "payee": payee, "amount": max(amt, 10.0)}
    if op == "realize_gain":
        cands = [(p, a.id) for p in people for a in hh.people[p].assets if a.unrealized_gain > 0]
        p, a = _choice(rng, cands)
        return {"op": op, "person": p, "asset": a, "fraction": _frac(rng, continuous)}
    if op == "assign_dependent":
        src = _choice(rng, [tu for tu in hh.tax_units if tu.dependents])
        d = _choice(rng, src.dependents)
        others = [tu.id for tu in hh.tax_units if tu.id != src.id]
        if not others:
            return None
        return {"op": op, "dependent": d, "tax_unit": _choice(rng, others)}
    if op == "set_filing_status":
        tu = _choice(rng, hh.tax_units)
        return {"op": op, "tax_unit": tu.id, "status": _choice(rng, ["SEPARATE", "JOINT", "SINGLE", "HEAD_OF_HOUSEHOLD"])}
    if op == "set_hours":
        p = _choice(rng, [p for p in people if hh.people[p].hours > 0])
        return {"op": op, "person": p, "hours": round(hh.people[p].hours * _frac(rng, continuous, (0.5, 0.8, 1.2), 0.5, 1.2))}
    if op == "itemize_or_standard":
        return {"op": op, "tax_unit": _choice(rng, hh.tax_units).id, "itemize": bool(rng.random() < 0.5)}
    if op == "contribute_retirement":
        p = _choice(rng, [p for p in people if hh.people[p].wages > 0])
        acct = _choice(rng, ["401k", "ira"])
        cap = 23_000 if acct == "401k" else 7_000
        return {"op": op, "person": p, "account": acct, "amount": round(float(min(hh.people[p].wages, cap) * _frac(rng, continuous)), 0)}
    return None


def random_sequence(hh: Household, rng: np.random.Generator, max_len: int = 3, tries: int = 20, continuous: bool = False, horizon: int = 1) -> list[dict]:
    """A valid random sequence of 1..max_len moves (built move by move).
    With horizon > 1, each move is dated in a random year of the horizon
    with probability 1/2 (otherwise it applies from the first year)."""
    n = int(rng.integers(1, max_len + 1))
    seq: list[dict] = []
    cur = hh
    for _ in range(tries):
        if len(seq) >= n:
            break
        m = random_move(cur, rng, continuous)
        if m is None:
            continue
        try:
            nxt = apply_moves(cur, [m])
        except MoveError:
            continue
        if horizon > 1 and rng.random() < 0.5:
            m = dict(m, year=hh.year + int(rng.integers(horizon)))
        seq.append(m)
        cur = nxt
    return seq


# ---------------------------------------------------------------------------
# Search loop
# ---------------------------------------------------------------------------


@dataclass
class Record:
    household_id: str
    call: int
    moves: list
    verdict: Verdict

    def to_row(self) -> dict:
        v = self.verdict
        return dict(
            household_id=self.household_id,
            call=self.call,
            moves=json.dumps(self.moves),
            n_moves=len(self.moves),
            label=v.label,
            gain=v.gain,
            gain_federal_pe=v.gain_federal_pe,
            gain_federal_tc=v.gain_federal_tc,
            gain_other_tax=v.gain_other_tax,
            gain_benefits=v.gain_benefits,
            gain_pe_only_credits=v.gain_pe_only_credits,
            coverage=v.coverage,
            crosscheck=v.crosscheck_pass,
            reality=v.reality_unchanged,
            signature=",".join(v.signature),
            circumvents=",".join(v.circumvents),
            residual_without_intended=v.residual_without_intended,
            attribution=json.dumps({k: round(x, 3) for k, x in v.attribution.items()}),
            error=v.error,
            recheck_gain=v.recheck_gain,
        )


class Proposer(Protocol):
    def propose(self, hh: Household, history: list[Record], k: int, rng: np.random.Generator) -> list[list[dict]]: ...


class RandomProposer:
    def __init__(self, max_len: int = 3, continuous: bool = False, horizon: int = 1):
        self.max_len, self.continuous, self.horizon = max_len, continuous, horizon

    def propose(self, hh, history, k, rng):
        return [random_sequence(hh, rng, self.max_len, continuous=self.continuous, horizon=self.horizon) for _ in range(k)]


class GreedyProposer:
    """Keep the top sequences by gain among flagged-or-not proposals with
    unchanged reality; propose mutations of them (append a move, drop a move,
    re-draw one move). Falls back to random sequences until there is an
    archive."""

    def __init__(self, max_len: int = 4, top: int = 5, explore: float = 0.3, continuous: bool = False, horizon: int = 1):
        self.max_len, self.top, self.explore = max_len, top, explore
        self.continuous, self.horizon = continuous, horizon

    def _seq(self, hh, rng):
        return random_sequence(hh, rng, self.max_len, continuous=self.continuous, horizon=self.horizon)

    def _move(self, hh, rng):
        m = random_move(hh, rng, self.continuous)
        if m is not None and self.horizon > 1 and rng.random() < 0.5:
            m = dict(m, year=hh.year + int(rng.integers(self.horizon)))
        return m

    def propose(self, hh, history, k, rng):
        good = [r for r in history if r.verdict.label not in ("invalid", "sacrifice", "benefit_cliff") and r.verdict.gain > 0]
        good.sort(key=lambda r: -r.verdict.gain)
        elite = [r.moves for r in good[: self.top]]
        out = []
        for _ in range(k):
            if not elite or rng.random() < self.explore:
                out.append(self._seq(hh, rng))
                continue
            base = list(_choice(rng, elite))
            kind = rng.random()
            try:
                cur = apply_moves(hh, base)
            except MoveError:
                out.append(self._seq(hh, rng))
                continue
            if kind < 0.5 and len(base) < self.max_len:
                m = self._move(cur, rng)
                out.append(base + ([m] if m else []))
            elif kind < 0.7 and len(base) > 1:
                i = int(rng.integers(len(base)))
                out.append(base[:i] + base[i + 1 :])
            else:
                i = int(rng.integers(len(base)))
                try:
                    pre = apply_moves(hh, base[:i])
                except MoveError:
                    pre = hh
                m = self._move(pre, rng)
                out.append(base[:i] + ([m] if m else []) + base[i + 1 :])
        return out


def search_many(
    households: list[Household],
    verifier: Verifier,
    proposer: Proposer,
    budget: int,
    batch: int = 25,
    seed: int = 0,
) -> dict[str, list[Record]]:
    """Spend `budget` verifier calls on each household. Rounds run across all
    households at once so the calculators see large batches. Empty and
    duplicate proposals cost nothing."""
    rngs = {h.id: np.random.default_rng([seed, i]) for i, h in enumerate(households)}
    hist: dict[str, list[Record]] = {h.id: [] for h in households}
    seen: dict[str, set] = {h.id: set() for h in households}
    calls = {h.id: 0 for h in households}
    stall = {h.id: 0 for h in households}
    while True:
        jobs = []  # (hh, moves)
        for hh in households:
            if calls[hh.id] >= budget or stall[hh.id] >= 5:
                continue
            k = min(batch, budget - calls[hh.id])
            fresh = []
            for p in proposer.propose(hh, hist[hh.id], k, rngs[hh.id]):
                key = json.dumps(p, sort_keys=True)
                if p and key not in seen[hh.id]:
                    seen[hh.id].add(key)
                    fresh.append(p)
            if not fresh:
                stall[hh.id] += 1
                continue
            stall[hh.id] = 0
            jobs += [(hh, p) for p in fresh]
        if not jobs:
            break
        verdicts = verifier.evaluate_many(jobs)
        for (hh, p), v in zip(jobs, verdicts):
            calls[hh.id] += 1
            hist[hh.id].append(Record(hh.id, calls[hh.id], p, v))
    return hist


def search(hh: Household, verifier: Verifier, proposer: Proposer, budget: int, batch: int = 25, seed: int = 0) -> list[Record]:
    return search_many([hh], verifier, proposer, budget, batch, seed)[hh.id]


# ---------------------------------------------------------------------------
# Pool targets: the search chooses the household as well as the moves.
# ---------------------------------------------------------------------------


class PoolProposer(Protocol):
    def propose_pool(self, pool: list[Household], history: list[Record], k: int, rng: np.random.Generator) -> list[tuple[int, list[dict]]]: ...


class RandomPoolProposer:
    """Uniform household, random valid move sequence."""

    def __init__(self, max_len: int = 3, continuous: bool = False, horizon: int = 1):
        self.max_len, self.continuous, self.horizon = max_len, continuous, horizon

    def propose_pool(self, pool, history, k, rng):
        out = []
        for _ in range(k):
            i = int(rng.integers(len(pool)))
            out.append((i, random_sequence(pool[i], rng, self.max_len, continuous=self.continuous, horizon=self.horizon)))
        return out


class GreedyPoolProposer:
    """Hill-climbing over (household, sequence): mutate the best proposals so
    far on their own household; explore new households with probability
    `explore`."""

    def __init__(self, max_len: int = 4, top: int = 5, explore: float = 0.4, continuous: bool = False, horizon: int = 1):
        self.inner = GreedyProposer(max_len=max_len, top=top, explore=0.0, continuous=continuous, horizon=horizon)
        self.max_len, self.top, self.explore = max_len, top, explore

    def propose_pool(self, pool, history, k, rng):
        good = [r for r in history if r.verdict.label not in ("invalid", "sacrifice", "benefit_cliff") and r.verdict.gain > 0]
        good.sort(key=lambda r: -r.verdict.gain)
        idx = {h.id: i for i, h in enumerate(pool)}
        elite = [(idx[r.household_id], r) for r in good[: self.top] if r.household_id in idx]
        out = []
        for _ in range(k):
            if not elite or rng.random() < self.explore:
                i = int(rng.integers(len(pool)))
                out.append((i, self.inner._seq(pool[i], rng)))
                continue
            i, _r = elite[int(rng.integers(len(elite)))]
            hist_i = [r for r in history if r.household_id == pool[i].id]
            props = self.inner.propose(pool[i], hist_i, 1, rng)
            out.append((i, props[0] if props else self.inner._seq(pool[i], rng)))
        return out


def search_pool(pool: list[Household], verifier: Verifier, proposer, budget: int, batch: int = 25, seed: int = 0) -> list[Record]:
    """Spend `budget` verifier calls on (household, moves) proposals over a
    pool of households. Duplicates and empty sequences cost nothing."""
    rng = np.random.default_rng(seed)
    history: list[Record] = []
    seen: set = set()
    calls, stall = 0, 0
    while calls < budget and stall < 5:
        k = min(batch, budget - calls)
        fresh = []
        for i, p in proposer.propose_pool(pool, history, k, rng):
            key = (i, json.dumps(p, sort_keys=True))
            if p and key not in seen:
                seen.add(key)
                fresh.append((i, p))
        if not fresh:
            stall += 1
            continue
        stall = 0
        verdicts = verifier.evaluate_many([(pool[i], p) for i, p in fresh])
        for (i, p), v in zip(fresh, verdicts):
            calls += 1
            history.append(Record(pool[i].id, calls, p, v))
    return history
