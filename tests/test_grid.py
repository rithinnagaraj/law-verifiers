"""Move grid: moves opened by an earlier move (DECISIONS, 2026-11-28)."""

import json

from taxgap.grid import _base_moves, grid_moves, n_opened, opened_moves, sequences
from taxgap.model import Asset, Household, Person, TaxUnit
from taxgap.mutations.family import grid_scan
from taxgap.mutations.handmade import hand_families

K = lambda m: json.dumps(m, sort_keys=True)


def hh():
    p = Person("p", 45, wages=150_000, hours=2080)
    p.assets.append(Asset("fund", 60_000, 20_000, dividend_yield=0.02))
    return Household("hk", 2024, "TX", {"p": p, "c": Person("c", 12)}, [TaxUnit("t", "p", dependents=["c"])])


GIFT = {"op": "gift_asset", "giver": "p", "recipient": "c", "asset": "fund", "fraction": 1.0}
SELL = {"op": "realize_gain", "person": "c", "asset": "fund@c", "fraction": 1.0}


def test_one_move_grid_is_unchanged():
    h = hh()
    one = list(sequences(h, 1))
    gk = {K(m) for m in grid_moves(h)}
    assert all(len(s) == 1 and K(s[0]) in gk for s in one)
    assert n_opened(h, one) == 0


def test_gift_then_sell_is_in_the_grid():
    h = hh()
    two = [[K(m) for m in s] for s in sequences(h, 2)]
    assert [K(GIFT), K(SELL)] in two  # same year
    assert [K(GIFT), K(dict(SELL, year=2025))] in two  # next year
    assert [K(dict(GIFT, year=2025)), K(SELL)] not in two  # never before the gift
    # the starting household's grid has no move on the child's asset
    assert all(m.get("asset") != "fund@c" for m in _base_moves(h))


def test_opened_moves_need_their_opener():
    h = hh()
    gm = grid_moves(h)
    gk = {K(m) for m in gm}
    openers = {}
    for i, m in opened_moves(h):
        openers.setdefault(K(m), set()).add(K(gm[i]))
        assert m.get("year", h.year) >= gm[i].get("year", h.year)
    for k in (2, 3):
        seqs = list(sequences(h, k))
        keys = [tuple(sorted(K(m) for m in s)) for s in seqs]
        assert len(keys) == len(set(keys))  # each multiset once
        for s in seqs:
            new = [j for j, m in enumerate(s) if K(m) not in gk]
            assert len(new) <= 1
            for j in new:
                before = {K(m) for m in s[:j]}
                assert openers[K(s[j])] & before  # its opener comes first


def test_witness_grid_scan_finds_the_planted_exploit():
    laws = hand_families()["h:kid_gain"].laws(1.0)
    found = grid_scan(laws, [hh()])
    assert any(len(s) == 2 and {m["op"] for m in s} == {"gift_asset", "realize_gain"} and any(m.get("asset") == "fund@c" for m in s) for _, s, _ in found)
