"""Search loops with a stub verifier (no calculators)."""

import numpy as np

from taxred.generate import archetypes
from taxred.search import (
    GreedyPoolProposer,
    GreedyProposer,
    RandomPoolProposer,
    RandomProposer,
    random_sequence,
    search_many,
    search_pool,
)
from taxred.moves import apply_moves
from taxred.verifier import Verdict


class StubVerifier:
    """Gain = 100 per gift move; counts calls."""

    def __init__(self):
        self.calls = 0

    def evaluate_many(self, proposals):
        self.calls += len(proposals)
        out = []
        for hh, moves in proposals:
            g = 100.0 * sum(m["op"] == "gift_asset" for m in moves)
            out.append(Verdict("candidate" if g > 50 else "no_gain", gain=g))
        return out


def test_random_sequences_are_valid():
    rng = np.random.default_rng(0)
    for hh in archetypes():
        for _ in range(20):
            seq = random_sequence(hh, rng, 3)
            apply_moves(hh, seq)  # raises if invalid


def test_search_many_respects_budget_and_dedups():
    hhs = archetypes()
    v = StubVerifier()
    hist = search_many(hhs, v, RandomProposer(), budget=30, batch=10, seed=1)
    for hid, recs in hist.items():
        assert len(recs) <= 30
        keys = [str(r.moves) for r in recs]
        assert len(keys) == len(set(keys))
    assert v.calls == sum(len(r) for r in hist.values())


def test_greedy_finds_gifts():
    hh = next(h for h in archetypes() if h.id == "high_earner_with_kids_assets")
    hist = search_many([hh], StubVerifier(), GreedyProposer(), budget=60, batch=10, seed=2)[hh.id]
    assert max(r.verdict.gain for r in hist) >= 100


def test_search_pool():
    pool = archetypes()
    for prop in (RandomPoolProposer(), GreedyPoolProposer()):
        hist = search_pool(pool, StubVerifier(), prop, budget=40, batch=10, seed=3)
        assert 0 < len(hist) <= 40
        assert {r.household_id for r in hist} <= {h.id for h in pool}
