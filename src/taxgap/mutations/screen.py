"""Pre-gate screen of generator v4 (G0 revision 2; see generate.py, DECISIONS.md).

Two necessary conditions of the A5 gate, checked cheaply before a candidate
is gated. They never relax the gate: a candidate that passes the screen is
still gated in full.

  hidden  no one-move grid sequence on the 9 gate households is a match under
          L, at either magnitude (PolicyEngine filter, then the full
          verifier on the PolicyEngine matches, exactly as check 2 does)
  alive   at both magnitudes, one of `n_two` sampled reality-preserving
          two-move grid sequences on the witness households has gain > $50,
          attributable gain >= $50 and >= 0.3 of its gain (PolicyEngine)
"""

from __future__ import annotations

import numpy as np

from ..archetypes import gate_archetypes, witness_archetypes
from ..grid import sequences
from ..law import CURRENT_LAW
from ..verifier import Config, Verifier
from .family import FLOOR, WITNESS_SHARE, Family, _matches, _pe_gains, _real

_ONE: dict = {}
_TWO: dict = {}


def _one_move() -> list:
    if not _ONE:
        _ONE["p"] = [(hh, s) for hh in gate_archetypes() for s in sequences(hh, 1) if _real(hh, s)]
    return _ONE["p"]


def _two_move(n_two: int, seed: int = 0) -> list:
    if n_two not in _TWO:
        rng = np.random.default_rng(seed)
        out = []
        pool = witness_archetypes()
        per = max(1, n_two // len(pool))
        for i, hh in enumerate(pool):
            seqs = list(sequences(hh, 2))
            idx = rng.permutation(len(seqs))
            got = 0
            for j in idx:
                if _real(hh, seqs[j]):
                    out.append((hh, seqs[j]))
                    got += 1
                    if got >= per:
                        break
        _TWO[n_two] = out
    return _TWO[n_two]


def screen(fam: Family, n_two: int = 1500) -> dict:
    """Screen one candidate. A mutated law that a calculator rejects (for
    example a bracket threshold scaled past the next one, which Tax-Calculator
    refuses as out of order) is recorded as `invalid_law` and fails."""
    try:
        return _screen(fam, n_two)
    except Exception as e:  # noqa: BLE001 - only the calculators' parameter validation is caught
        if type(e).__name__ != "ValidationError":
            raise
        return {"family": fam.id, "hidden": False, "alive": False, "invalid_law": str(e)[:400]}


def _screen(fam: Family, n_two: int) -> dict:
    out = {"family": fam.id, "hidden": True, "alive": False, "one_move_matches": {}, "alive_at": None}
    one = _one_move()
    for m in fam.magnitudes:
        L = fam.laws(m)["L"]
        hits = _matches(one, L, Verifier(L, Config()))
        if hits:
            out["hidden"] = False
            out["one_move_matches"][f"{m:g}"] = [{"hh": p[0].id, "moves": p[1], "attr": round(at)} for p, _, at in hits[:3]]
            out["n_one_move_matches"] = len(hits)
            return out
    two = _two_move(n_two)
    g0 = _pe_gains(two, CURRENT_LAW)
    out["alive_at"] = {}
    for m in fam.magnitudes:  # the gate needs both magnitudes, so alive needs both
        gl = _pe_gains(two, fam.laws(m)["L"])
        best = [(b - a, i) for i, (a, b) in enumerate(zip(g0, gl)) if b == b and b > FLOOR and b - a >= FLOOR and b - a >= WITNESS_SHARE * b]
        if not best:
            out["alive_at"][f"{m:g}"] = None
            return out
        at, i = max(best)
        out["alive_at"][f"{m:g}"] = {"hh": two[i][0].id, "moves": two[i][1], "attr": round(at), "n": len(best)}
    out["alive"] = True
    return out


def passes(row: dict) -> bool:
    return bool(row["hidden"] and row["alive"] and not row.get("invalid_law"))
