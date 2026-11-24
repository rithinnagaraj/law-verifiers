"""Search over a pool of households with a verifier-call budget.

A proposer proposes (household index, moves) pairs in batches; each
proposal costs one verifier call. Proposers see only verifier output (gain
and label). `search(pool, law, proposer, budget)` returns one record per
proposal.

Reward: by default the gain of a proposal labelled `candidate`, else 0.
`blind_crosscheck=True` also rewards `code_disagreement` (used for canary
search: the exploits a search finds are measured before the cross-check
judges them).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..moves import MoveError, _apply, horizon, years_of
from ..verifier import Config, Verifier
from .sample import random_move, random_sequence


@dataclass
class Record:
    call: int
    hh: int
    moves: list
    verdict: dict

    def to_row(self) -> dict:
        return {"call": self.call, "hh": self.hh, "moves": self.moves, "verdict": self.verdict}


def reward(v: dict, blind_crosscheck: bool = False) -> float:
    ok = ("candidate", "code_disagreement") if blind_crosscheck else ("candidate",)
    return float(v["gain"]) if v["label"] in ok else 0.0


class RandomProposer:
    """A fresh random household and sequence for every proposal."""

    def __init__(self, pool, rng: np.random.Generator, max_len: int = 3):
        self.pool, self.rng, self.max_len = pool, rng, max_len

    def propose(self, n: int) -> list:
        out = []
        for _ in range(n):
            k = int(self.rng.integers(len(self.pool)))
            seq = random_sequence(self.pool[k], self.rng, self.max_len)
            if seq:
                out.append((k, seq))
        return out

    def observe(self, recs: list) -> None:
        pass


def _valid(hh, seq) -> bool:
    try:
        for f in hh.futures or [None]:
            years_of(hh, seq, f)
        return True
    except (MoveError, KeyError, ValueError):
        return False


def mutate(hh, seq: list, rng: np.random.Generator, max_len: int = 4, tries: int = 20) -> Optional[list]:
    """Add, drop or replace one move (valid result or None)."""
    years = horizon(hh)
    for _ in range(tries):
        op = rng.choice(["add", "drop", "replace"]) if len(seq) > 1 else rng.choice(["add", "replace"])
        new = [dict(m) for m in seq]
        if op == "drop":
            del new[int(rng.integers(len(new)))]
        else:
            if op == "add" and len(new) >= max_len:
                continue
            pos = int(rng.integers(len(new) + (op == "add")))
            prefix = new[:pos]
            state = copy.deepcopy(hh)
            try:
                for i, m in enumerate(sorted(prefix, key=lambda m: m.get("year", years[0]))):
                    _apply(state, int(m.get("year", years[0])), m, i)
            except MoveError:
                continue
            y = int(rng.choice(years))
            m = random_move(state, rng, y)
            if m is None:
                continue
            if y != years[0]:
                m["year"] = y
            if op == "add":
                new.insert(pos, m)
            else:
                new[pos] = m
        if new and _valid(hh, new):
            return new
    return None


class GreedyProposer:
    """Top-5 elite by reward; 40% exploration (fresh random), else mutate a
    random elite member (add / drop / replace one move)."""

    def __init__(self, pool, rng: np.random.Generator, elite: int = 5, explore: float = 0.4, blind_crosscheck: bool = False, max_len: int = 4):
        self.pool, self.rng = pool, rng
        self.k, self.explore, self.blind, self.max_len = elite, explore, blind_crosscheck, max_len
        self.elite: list = []  # (reward, hh, moves)

    def propose(self, n: int) -> list:
        out = []
        for _ in range(n):
            if not self.elite or self.rng.random() < self.explore:
                k = int(self.rng.integers(len(self.pool)))
                seq = random_sequence(self.pool[k], self.rng)
            else:
                _, k, base = self.elite[int(self.rng.integers(len(self.elite)))]
                seq = mutate(self.pool[k], base, self.rng, self.max_len)
            if seq:
                out.append((k, seq))
        return out

    def observe(self, recs: list) -> None:
        for r in recs:
            g = reward(r.verdict, self.blind)
            if g > 0:
                self.elite.append((g, r.hh, r.moves))
        self.elite.sort(key=lambda x: -x[0])
        seen, keep = set(), []
        for e in self.elite:
            key = (e[1], repr(e[2]))
            if key not in seen:
                seen.add(key)
                keep.append(e)
        self.elite = keep[: self.k]


def search(pool: list, law, proposer, budget: int, cfg: Optional[Config] = None, batch: int = 20) -> list[Record]:
    v = Verifier(law, cfg or Config())
    recs: list[Record] = []
    while len(recs) < budget:
        props = proposer.propose(min(batch, budget - len(recs)))
        if not props:
            break
        vs = v.evaluate([(pool[k], seq) for k, seq in props])
        new = [Record(len(recs) + i, k, seq, vd.to_dict()) for i, ((k, seq), vd) in enumerate(zip(props, vs))]
        recs += new
        proposer.observe(new)
    return recs
