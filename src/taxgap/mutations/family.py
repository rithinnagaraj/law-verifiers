"""A candidate interaction family and its gate (experiment plan A5).

A family moves two parameters from different provisions together (in the
direction that lowers tax), at two magnitudes. For each magnitude m:

  L1, L2   each mutation alone;  L = both;  Lrev = both reversed
  witness  targeted search on witness archetypes for a sequence whose gain
           under L comes from the interaction: mutation-attributable share
           >= 0.3 and each single mutation's share < R; minimized (moves
           dropped while that holds); witnesses with k >= 2 moves are
           preferred; a k = 1 family is kept but marked shallow

Gate (both magnitudes must pass):
  1 witness valid: labelled candidate under L; attributable share >= 0.3
  2 non-decomposable: no (k-1)-move grid sequence on the 10 archetypes
    (9 stratified + the witness household) is a match under L
  3 single-mutation ablation: each mutation alone gives share < R on the witness
  4 continuous spot check: 500 random (k-1)-move draws, same test as 2
  5 negative control: the witness is not a match under Lrev

A match: labelled candidate, attributable gain >= $50 and >= R of its gain.
Attributable gain = gain under L minus gain under current law (PolicyEngine).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..archetypes import gate_archetypes, witness_archetypes
from ..grid import sequences
from ..law import CURRENT_LAW, Law
from ..moves import MoveError
from ..search.pool import mutate
from ..search.sample import random_sequence
from ..verifier import Config, Verifier, gains, prepare
from .catalog import Param

R = 0.1
WITNESS_SHARE = 0.3
FLOOR = 50.0


@dataclass
class Family:
    id: str
    mechanism: str
    p1: Param
    p2: Param
    magnitudes: tuple = (2.0, 4.0)

    def _f(self, p: Param, m: float, reverse: bool = False) -> tuple:
        up = (p.generous > 0) != reverse
        return p.change("scale", m if up else 1.0 / m)

    def laws(self, m: float) -> dict:
        a, b = self._f(self.p1, m), self._f(self.p2, m)
        ra, rb = self._f(self.p1, m, True), self._f(self.p2, m, True)
        return {
            "L": CURRENT_LAW.plus(*a, *b, label=f"{self.id}@{m:g}"),
            "L1": CURRENT_LAW.plus(*a, label=f"{self.p1.key}@{m:g}"),
            "L2": CURRENT_LAW.plus(*b, label=f"{self.p2.key}@{m:g}"),
            "Lrev": CURRENT_LAW.plus(*ra, *rb, label=f"{self.id}@{m:g} reversed"),
        }

    def describe(self) -> dict:
        return {"id": self.id, "mechanism": self.mechanism, "p1": self.p1.key, "p2": self.p2.key, "provisions": [self.p1.provision, self.p2.provision], "magnitudes": list(self.magnitudes)}


def _pe_gains(props: list, law: Law) -> list[float]:
    preps, idx = [], []
    for i, (hh, mv) in enumerate(props):
        try:
            preps.append(prepare(hh, mv))
            idx.append(i)
        except (MoveError, KeyError, ValueError):
            pass
    out = [float("nan")] * len(props)
    for i, g in zip(idx, gains(preps, law, with_tc=False)):
        out[i] = g["gain"]
    return out


def _scores(props: list, laws: dict) -> list[dict]:
    g0 = _pe_gains(props, CURRENT_LAW)
    gl = _pe_gains(props, laws["L"])
    g1 = _pe_gains(props, laws["L1"])
    g2 = _pe_gains(props, laws["L2"])
    out = []
    for a, b, c, d in zip(g0, gl, g1, g2):
        attr, s1, s2 = b - a, c - a, d - a
        inter = b > FLOOR and attr >= FLOOR and attr >= WITNESS_SHARE * b and s1 < R * b and s2 < R * b
        out.append({"g0": a, "gL": b, "attr": attr, "s1": s1, "s2": s2, "interacting": bool(inter), "score": (attr - 2 * max(s1, s2, 0.0)) if b > FLOOR else 0.0})
    return out


def witness_search(laws: dict, rng: np.random.Generator, budget: int = 1250, batch: int = 50, pool: Optional[list] = None) -> dict:
    pool = pool or witness_archetypes()
    elite: list = []  # (score, k, moves)
    found: list = []  # interacting (k, moves, score dict)
    n = 0
    while n < budget:
        props = []
        for _ in range(batch):
            if not elite or rng.random() < 0.4:
                k = int(rng.integers(len(pool)))
                seq = random_sequence(pool[k], rng, max_len=3)
            else:
                _, k, base = elite[int(rng.integers(len(elite)))]
                seq = mutate(pool[k], base, rng, max_len=4)
            if seq:
                props.append((k, seq))
        if not props:
            break
        sc = _scores([(pool[k], s) for k, s in props], laws)
        n += len(props)
        for (k, s), x in zip(props, sc):
            if x["score"] > 0:
                elite.append((x["score"], k, s))
            if x["interacting"]:
                found.append((k, s, x))
        elite.sort(key=lambda e: -e[0])
        elite = elite[:8]
    # minimize interacting sequences: drop moves while still interacting
    mins = []
    for k, s, x in sorted(found, key=lambda f: -f[2]["attr"])[:10]:
        seq = list(s)
        changed = True
        while changed and len(seq) > 1:
            changed = False
            for i in range(len(seq)):
                shorter = seq[:i] + seq[i + 1 :]
                y = _scores([(pool[k], shorter)], laws)[0]
                if y["interacting"]:
                    seq, x, changed = shorter, y, True
                    break
        mins.append((len(seq) < 2, len(seq), -x["attr"], k, seq, x))
    best = min(mins, key=lambda t: t[:3]) if mins else None
    if best is None:
        return {"found": False, "proposals": n, "n_interacting": len(found)}
    _, k_len, _, k, seq, x = best
    return {"found": True, "proposals": n, "n_interacting": len(found), "household": k, "household_id": pool[k].id, "moves": seq, "k": k_len, "scores": x}


def _matches(props: list, law: Law, verifier: Verifier) -> list:
    """Proposals that are matches under `law` (cheap PolicyEngine filter,
    then the full verifier for those that pass it)."""
    g0 = _pe_gains(props, CURRENT_LAW)
    gl = _pe_gains(props, law)
    cand = [i for i, (a, b) in enumerate(zip(g0, gl)) if b > FLOOR and b - a >= FLOOR and b - a >= R * b]
    if not cand:
        return []
    vs = verifier.evaluate([props[i] for i in cand])
    return [(props[i], v.to_dict(), gl[i] - g0[i]) for i, v in zip(cand, vs) if v.label == "candidate"]


def gate(fam: Family, m: float, rng: np.random.Generator, witness_budget: int = 1250, grid_cap: int = 30_000, spot: int = 500) -> dict:
    laws = fam.laws(m)
    out = {"family": fam.id, "magnitude": m, "checks": {}, "passed": False}
    pool = witness_archetypes()
    w = witness_search(laws, rng, witness_budget, pool=pool)
    out["witness"] = w
    if not w["found"]:
        out["reason"] = "no interacting witness"
        return out
    hh, mv, k = pool[w["household"]], w["moves"], w["k"]
    out["shallow"] = k < 2  # one-move witness: check 2 is vacuous; reported, not rejected
    vL = Verifier(laws["L"], Config())
    # 1. witness valid
    v = vL.one(hh, mv)
    share = w["scores"]["attr"] / v.gain if v.gain > 0 else 0.0
    out["checks"]["1_witness"] = {"label": v.label, "gain": v.gain, "gain_tc": v.gain_tc, "attr_share": share, "ok": v.label == "candidate" and share >= WITNESS_SHARE}
    # 3. single-mutation ablation
    s = w["scores"]
    out["checks"]["3_ablation"] = {"share1": s["s1"] / s["gL"], "share2": s["s2"] / s["gL"], "ok": s["s1"] < R * s["gL"] and s["s2"] < R * s["gL"]}
    # 2. non-decomposability on 10 archetypes
    arch = gate_archetypes() + [hh]
    n_seq, sampled, hits = 0, False, []
    for a in arch:
        seqs = list(sequences(a, k - 1, limit=grid_cap + 1))
        if len(seqs) > grid_cap:
            sampled = True
            idx = rng.choice(len(seqs), grid_cap, replace=False)
            seqs = [seqs[i] for i in idx]
        n_seq += len(seqs)
        for c in range(0, len(seqs), 400):
            for p, vd, at in _matches([(a, s_) for s_ in seqs[c : c + 400]], laws["L"], vL):
                hits.append((a.id, p[1], vd, at))
    out["checks"]["2_grid"] = {"sequences": n_seq, "sampled": sampled, "matches": len(hits), "examples": [{"hh": h, "moves": s_, "attr": at} for h, s_, _, at in hits[:3]], "ok": not hits}
    # 4. continuous spot check
    draws = []
    for _ in range(spot):
        a = arch[int(rng.integers(len(arch)))]
        sq = random_sequence(a, rng, max_len=k - 1)
        if sq and len(sq) == k - 1:
            draws.append((a, sq))
    sh = _matches(draws, laws["L"], vL)
    out["checks"]["4_spot"] = {"draws": len(draws), "matches": len(sh), "examples": [{"hh": p[0].id, "moves": p[1], "attr": at} for p, _, at in sh[:3]], "ok": not sh}
    # 5. negative control
    rv = _matches([(hh, mv)], laws["Lrev"], Verifier(laws["Lrev"], Config()))
    out["checks"]["5_reverse"] = {"matches": len(rv), "ok": not rv}
    out["passed"] = all(c["ok"] for c in out["checks"].values())
    if not out["passed"]:
        out["reason"] = "failed " + ",".join(k_ for k_, c in out["checks"].items() if not c["ok"])
    return out
