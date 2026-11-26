"""Diagnostic (not an experiment): do interacting multi-move witnesses exist
for spike-3 (rejected) families on a dense household grid? Pool defined
before running: 8 types x 13 wage levels x 4 investment levels."""
import json, sys, time
from multiprocessing import Pool

import numpy as np

from taxgap.archetypes import _hh, _p
from taxgap.model import TaxUnit
from taxgap.mutations.family import FLOOR, R, WITNESS_SHARE, _pe_gains, _real, _scores
from taxgap.law import CURRENT_LAW
from taxgap.grid import sequences
from taxgap.mutations.generate import all_families

WAGES = (10_000, 20_000, 30_000, 40_000, 50_000, 60_000, 75_000, 90_000, 110_000, 140_000, 180_000, 250_000, 400_000)
INV = {"i0": (10_000, 20_000), "i1": (150_000, 150_000), "i2": (300_000, 300_000), "i3": (800_000, 800_000)}  # (bond, fund)
TYPES = ("s0", "s1", "s2", "s3", "m0", "m1", "m2", "m3")
KID_AGES = (4, 9, 14)


def household(t, w, inv):
    bond, fund = INV[inv]
    kids = [_p(f"k{i}", KID_AGES[i]) for i in range(int(t[1]))]
    ex = dict(ira=0.5 * w, give=0.01 * w, mortgage=0.03 * w)
    hid = f"d_{t}_{w // 1000}k_{inv}"
    if t[0] == "s":
        a = _p("a", 40, wages=w, bond=bond, fund=fund, **ex)
        return _hh(hid, [a, *kids], [TaxUnit("t", "a", dependents=[k.id for k in kids])])
    a = _p("a", 42, wages=0.7 * w, bond=bond, fund=fund, **ex)
    b = _p("b", 41, wages=0.3 * w)
    return _hh(hid, [a, b, *kids], [TaxUnit("t", "a", "b", [k.id for k in kids])], [("a", "b")])


def pool(types=TYPES):
    return [household(t, w, i) for t in types for w in WAGES for i in INV]


def work(arg):
    fid, m, hh = arg
    laws = all_families(0)[fid].laws(m)
    seqs = [s for j in (1, 2) for s in sequences(hh, j) if _real(hh, s)]
    props = [(hh, s) for s in seqs]
    found, n_share = [], 0
    for c in range(0, len(props), 600):
        ch = props[c : c + 600]
        g0 = _pe_gains(ch, CURRENT_LAW)
        gl = _pe_gains(ch, laws["L"])
        keep = [i for i, (a, b) in enumerate(zip(g0, gl)) if b == b and b > FLOOR and b - a >= FLOOR and b - a >= WITNESS_SHARE * b]
        n_share += len(keep)
        if keep:
            for i, x in zip(keep, _scores([ch[i] for i in keep], laws)):
                if x["interacting"]:
                    found.append((len(ch[i][1]), ch[i][1], {k: round(v) for k, v in x.items() if k in ("gL", "attr", "s1", "s2")}))
    return hh.id, len(seqs), n_share, found


if __name__ == "__main__":
    fids = sys.argv[1].split(",")
    types = tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else TYPES
    hhs = pool(types)
    t = time.time()
    for fid in fids:
        args = [(fid, 2.0, h) for h in hhs]
        with Pool(24) as p:
            res = p.map(work, args, chunksize=1)
        tot = sum(r[1] for r in res)
        ninter = sum(len(r[3]) for r in res)
        k1 = sum(1 for r in res for f in r[3] if f[0] == 1)
        print(f"== {fid} m=2: households {len(hhs)}, sequences {tot}, share-ok {sum(r[2] for r in res)}, interacting {ninter} (one-move {k1}, two-move {ninter - k1}), {round(time.time() - t)}s", flush=True)
        for hid, n, ns, f in res:
            if f:
                k2 = [x for x in f if x[0] == 2]
                print(f"   {hid}: {len(f)} interacting, {len(f) - len(k2)} one-move; e.g. {json.dumps(f[0][1])[:200]} {f[0][2]}", flush=True)
