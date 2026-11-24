"""Beam enumeration baseline: breadth-first over the discretized grid.

Depth 1 for every household (households in a seeded random order), then
depth 2, then depth 3. Sequences are combinations of grid moves (one
ordering each); duplicates are pruned. Deterministic given the seed.
"""

from __future__ import annotations

import json

import numpy as np

from ..grid import sequences


class BeamProposer:
    def __init__(self, pool, rng: np.random.Generator, max_depth: int = 3, per_household_cap: int | None = None):
        self.pool = pool
        self.order = list(rng.permutation(len(pool)))
        self.max_depth = max_depth
        self.cap = per_household_cap
        self._gen = self._walk()
        self.seen: set = set()

    def _walk(self):
        for d in range(1, self.max_depth + 1):
            for k in self.order:
                for seq in sequences(self.pool[k], d, limit=self.cap):
                    key = (k, json.dumps(seq, sort_keys=True))
                    if key in self.seen:
                        continue
                    self.seen.add(key)
                    yield int(k), seq

    def propose(self, n: int) -> list:
        out = []
        for _ in range(n):
            try:
                out.append(next(self._gen))
            except StopIteration:
                break
        return out

    def observe(self, recs: list) -> None:
        pass
