"""Diagnostic (not an experiment) on spike-3 (rejected) families: on the dense
household grid of diag_pool.py, how many interacting sequences, how many
one-move, and how many households whose interacting sequences are all >= 2
moves (depth 2 on that household)? Current-law gains cached once."""
import json, os, pickle, sys, time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diag_pool import pool  # noqa: E402

from taxgap.grid import sequences  # noqa: E402
from taxgap.law import CURRENT_LAW  # noqa: E402
from taxgap.mutations.family import FLOOR, R, WITNESS_SHARE, _pe_gains, _real, _scores  # noqa: E402
from taxgap.mutations.generate import all_families  # noqa: E402

CACHE = os.path.expanduser("~/diag_g0")
HH = {h.id: h for h in pool()}


def seqs_g0(hid):
    f = f"{CACHE}/{hid}.pkl"
    if os.path.exists(f):
        return pickle.load(open(f, "rb"))
    hh = HH[hid]
    seqs = [s for j in (1, 2) for s in sequences(hh, j) if _real(hh, s)]
    g0 = []
    for c in range(0, len(seqs), 600):
        g0 += _pe_gains([(hh, s) for s in seqs[c : c + 600]], CURRENT_LAW)
    pickle.dump((seqs, g0), open(f + ".tmp", "wb"))
    os.replace(f + ".tmp", f)
    return seqs, g0


def work(arg):
    fid, m, hid = arg
    hh = HH[hid]
    seqs, g0 = seqs_g0(hid)
    if fid is None:
        return hid, len(seqs)
    laws = all_families(0)[fid].laws(m)
    found = []
    for c in range(0, len(seqs), 600):
        sq, a0 = seqs[c : c + 600], g0[c : c + 600]
        gl = _pe_gains([(hh, s) for s in sq], laws["L"])
        keep = [i for i, (a, b) in enumerate(zip(a0, gl)) if b == b and b > FLOOR and b - a >= FLOOR and b - a >= WITNESS_SHARE * b]
        if keep:
            for i, x in zip(keep, _scores([(hh, sq[i]) for i in keep], laws)):
                if x["interacting"]:
                    found.append((len(sq[i]), sq[i], {k: round(v) for k, v in x.items() if k in ("gL", "attr", "s1", "s2")}))
    return hid, found


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    fids = sys.argv[1].split(",")
    m = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    t = time.time()
    with Pool(28) as p:
        p.map(work, [(None, m, h) for h in HH], chunksize=1)
        print(f"g0 cache ready {round(time.time() - t)}s", flush=True)
        for fid in fids:
            res = p.map(work, [(fid, m, h) for h in HH], chunksize=1)
            inter = [(hid, f) for hid, f in res if f]
            n1 = sum(1 for _, f in inter for x in f if x[0] == 1)
            deep = [(hid, f) for hid, f in inter if all(x[0] >= 2 for x in f)]
            print(f"== {fid} m={m:g}: households with interacting {len(inter)}, sequences {sum(len(f) for _, f in inter)}, one-move {n1}, "
                  f"households depth-2 {len(deep)} {round(time.time() - t)}s", flush=True)
            for hid, f in deep[:6]:
                best = max(f, key=lambda x: x[2]['attr'])
                print(f"   depth-2 {hid}: {len(f)}; best {json.dumps(best[1])[:220]} {best[2]}", flush=True)
            ones = [(hid, x) for hid, f in inter for x in f if x[0] == 1]
            for hid, x in ones[:3]:
                print(f"   one-move {hid}: {json.dumps(x[1])[:200]} {x[2]}", flush=True)
