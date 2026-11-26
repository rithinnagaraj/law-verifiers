"""Exploratory probe (not an experiment; changes nothing in the gate).

Would the two EITC investment-limit families yield usable targets if depth
were judged per household instead of over every household searched? For
each family, magnitude (x2, x4) and household of the dense pool where, at
x2, only two-move sequences interact (results/a5/diag/dense_pool_run*.txt):
  witness   the household's interacting two-move sequence with the largest
            attributable gain at that magnitude (deterministic)
  check 1   verifier label and attributable share on the witness
  check 3   each mutation alone < R of the gain (from the scores)
  check 5   no match under the reversed law
  own k-1   one-move matches on the witness household itself (full grid)
  gate k-1  one-move matches on the 9 gate archetypes (check 2 as written)
Families, households and order fixed before it ran (DECISIONS, 2026-11-27).
Output: ~/diag_census/probe_instance.jsonl
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diag_pool2 as d2  # noqa: E402

from taxgap.archetypes import gate_archetypes  # noqa: E402
from taxgap.grid import sequences  # noqa: E402
from taxgap.mutations.family import WITNESS_SHARE, R, _matches  # noqa: E402
from taxgap.mutations.generate import all_families  # noqa: E402
from taxgap.verifier import Config, Verifier  # noqa: E402

DEPTH2 = {
    "v5:eitc_gate:eitc_inv+eitc_max3": ["d_s3_30k_i3", "d_s3_50k_i2", "d_s3_60k_i2", "d_s3_75k_i2", "d_s3_90k_i0", "d_s3_110k_i0", "d_s3_180k_i2",
                                        "d_m3_40k_i3", "d_m3_60k_i2", "d_m3_75k_i2", "d_m3_90k_i0", "d_m3_90k_i3", "d_m3_110k_i0"],
    "v5:eitc_gate:eitc_inv+eitc_max1": None,  # the 6 printed in the run-2 log (it prints at most 6)
}
GATE = {}
OUT = os.path.expanduser("~/diag_census/probe_instance.jsonl")


def one_move_matches(hhs, law, v):
    hits = []
    for a in hhs:
        seqs = list(sequences(a, 1))
        for c in range(0, len(seqs), 400):
            hits += [(p[0].id, p[1], at) for p, _, at in _matches([(a, s) for s in seqs[c : c + 400]], law, v)]
    return hits


def probe(fid, m, hid):
    hh = d2.HH[hid]
    laws = all_families(0)[fid].laws(m)
    _, found = d2.work((fid, m, hid))
    two = [x for x in found if x[0] == 2]
    row = {"family": fid, "magnitude": m, "household": hid, "interacting_two_move": len(two), "interacting_one_move": len(found) - len(two)}
    if not two:
        return row
    _, mv, sc = max(two, key=lambda x: x[2]["attr"])
    vL = Verifier(laws["L"], Config())
    v = vL.one(hh, mv)
    share = sc["attr"] / v.gain if v.gain > 0 else 0.0
    own = one_move_matches([hh], laws["L"], vL)
    key = (fid, m)
    if key not in GATE:
        GATE[key] = one_move_matches(gate_archetypes(), laws["L"], vL)
    gate = GATE[key]
    rv = _matches([(hh, mv)], laws["Lrev"], Verifier(laws["Lrev"], Config()))
    row.update({
        "witness": mv, "scores": sc,
        "1_witness": {"label": v.label, "gain": v.gain, "gain_tc": v.gain_tc, "attr_share": share, "ok": v.label == "candidate" and share >= WITNESS_SHARE},
        "3_ablation": {"ok": sc["s1"] < R * sc["gL"] and sc["s2"] < R * sc["gL"]},
        "5_reverse": {"matches": len(rv), "ok": not rv},
        "own_k1": {"matches": len(own), "examples": own[:3], "ok": not own},
        "gate_k1": {"matches": len(gate), "examples": gate[:3], "ok": not gate},
    })
    return row


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    log = open(os.path.join(here, "..", "..", "results", "a5", "diag", "dense_pool_run2.txt")).read().split("\n")
    DEPTH2["v5:eitc_gate:eitc_inv+eitc_max1"] = [l.split()[1].rstrip(":") for l in log if l.strip().startswith("depth-2 ")]
    done = set()
    if os.path.exists(OUT):
        done = {(r["family"], r["magnitude"], r["household"]) for r in map(json.loads, open(OUT))}
    for fid, hids in DEPTH2.items():
        for m in (2.0, 4.0):
            for hid in hids:
                if (fid, m, hid) in done:
                    continue
                row = probe(fid, m, hid)
                with open(OUT, "a") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                print(fid, m, hid, {k: row[k].get("ok") for k in row if isinstance(row[k], dict) and "ok" in row[k]}, flush=True)
