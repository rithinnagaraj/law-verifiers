"""E0.7 matching-rule validation on planted variants (known ground truth).

For each variant V (law = V.law, closure = V.closure), proposals on V's panel:

  positives  V's witness moves, perturbed: on other households, with an
             extra unrelated move appended (a 401(k) deferral or an itemize
             toggle), or split into two half-gifts where the witness is a gift
  negatives  the witnesses of every other family, under V's law

A proposal matches V when it is flagged under V.law and the closure removes
>= R of its gain (closure-test half of experiment plan §1.1). For planted
variants the signature half reduces to the same check (the planted provision
is the mutation), so the closure test is what is validated here. Output:
precision / recall over a grid of R, and the R that maximises F1 with both
precision and recall >= 0.9 if one exists.

    python experiments/e0_7_matching.py --workers 6
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
from common import out_dir, run_metadata, safe_workers, write_json

from taxred.moves import MoveError, apply_moves
from taxred.planted import FAMILIES, variants
from taxred.verifier import Verifier, VerifierConfig

FLAGGED = ("candidate", "code_disagreement")
GRID = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def _extra_moves(hh):
    """Unrelated moves to append to a witness."""
    out = []
    for pid, p in hh.people.items():
        if p.wages > 10_000:
            try:
                tu = hh.unit_of(pid)
            except KeyError:
                continue
            if pid in (tu.head, tu.spouse):
                out.append({"op": "contribute_retirement", "person": pid, "account": "401k", "amount": 5_000.0})
                break
    out.append({"op": "itemize_or_standard", "tax_unit": hh.tax_units[0].id, "itemize": False})
    return out


def _split_gift(moves):
    if len(moves) == 1 and moves[0]["op"] == "gift_asset":
        m = dict(moves[0])
        a = dict(m, fraction=0.5)
        # second half-gift: the remaining half of the original asset
        b = dict(m, fraction=1.0)
        return [a, b]
    return None


def proposals_for(v, all_variants):
    props = []  # (kind, source family, household, moves)
    hhs = [v.witness_household] + v.panel
    for h in hhs:
        props.append(("positive", v.family, h, v.witness))
        for e in _extra_moves(h):
            props.append(("positive", v.family, h, v.witness + [e]))
        s = _split_gift(v.witness)
        if s:
            props.append(("positive", v.family, h, s))
    seen = set()
    for o in all_variants:
        if o.family == v.family or o.family in seen:
            continue
        seen.add(o.family)
        for h in [o.witness_household] + o.panel[:4]:
            props.append(("negative", o.family, h, o.witness))
    # keep only proposals that are valid
    ok = []
    for p in props:
        try:
            apply_moves(p[2], p[3])
            ok.append(p)
        except MoveError:
            pass
    return ok


def run(args):
    vid, year = args
    vs = variants(year)
    v = next(x for x in vs if x.id == vid)
    props = proposals_for(v, vs)
    pre = Verifier(v.law, VerifierConfig(run_attribution=False, horizon=v.horizon)).evaluate_many([(h, m) for _, _, h, m in props])
    post = Verifier(v.closure, VerifierConfig(run_attribution=False, horizon=v.horizon)).evaluate_many([(h, m) for _, _, h, m in props])
    rows = []
    for (kind, src, h, m), a, b in zip(props, pre, post):
        red = (a.gain - b.gain) / a.gain if a.gain > 1e-9 else 0.0
        rows.append(dict(variant=v.id, family=v.family, kind=kind, source=src, household_id=h.id, n_moves=len(m),
                         label=a.label, gain=a.gain, gain_closure=b.gain, reduction=red, flagged=a.label in FLAGGED))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--from-csv", action="store_true")
    a = ap.parse_args()
    od = out_dir("phase0/e0_7")
    if a.from_csv:
        df = pd.read_csv(od / "pairs.csv")
    else:
        valid = None
        man = Path(out_dir("phase2/planted")) / "variants.json"
        if man.exists():
            valid = {m["id"] for m in json.loads(man.read_text()) if m["valid"]}
        vs = [v for v in variants(a.year) if valid is None or v.id in valid]
        rows = []
        with ProcessPoolExecutor(safe_workers(a.workers)) as ex:
            for r in ex.map(run, [(v.id, a.year) for v in vs]):
                rows += r
        df = pd.DataFrame(rows)
        df.to_csv(od / "pairs.csv", index=False)

    # Ground truth by construction: a proposal is an instance of the planted
    # loophole when the mutation creates > $50 of its gain and the gain is
    # positive, whatever witness it came from. (Run 1 counted cross-family
    # witnesses as negatives, but e.g. filing separately under the CTC-MFS
    # mutation exploits it too: all 25 "false positives" were such cases.)
    df["truth"] = ((df.gain - df.gain_closure) > 50) & (df.gain > 50)
    grid = []
    for r in GRID:
        pred = df.flagged & (df.reduction >= r)
        tp = int((pred & df.truth).sum())
        fp = int((pred & ~df.truth).sum())
        fn = int((~pred & df.truth).sum())
        p = tp / (tp + fp) if tp + fp else float("nan")
        rc = tp / (tp + fn) if tp + fn else float("nan")
        f1 = 2 * p * rc / (p + rc) if p + rc else float("nan")
        grid.append(dict(R=r, precision=p, recall=rc, f1=f1, tp=tp, fp=fp, fn=fn))
    g = pd.DataFrame(grid)
    ok = g[(g.precision >= 0.9) & (g.recall >= 0.9)]
    # Among the R with the best F1, take the largest (the most conservative
    # threshold in the stable region).
    pool = ok if len(ok) else g
    best = pool[pool.f1 >= pool.f1.max() - 1e-9].sort_values("R").iloc[-1].to_dict()
    by_family = df[df.truth].groupby("family").reduction.describe()[["count", "min", "25%", "50%"]]
    neg = df[df.kind == "negative"].groupby("family").apply(lambda d: float((d.flagged & (d.reduction >= best["R"])).mean()))
    summary = dict(meta=run_metadata(), grid=grid, best=best, both_over_0_9=bool(len(ok)))
    write_json(od / "summary.json", summary)
    md = (
        "# E0.7 matching rule (closure test) on planted variants\n\n"
        f"Proposals: {len(df)} ({int(df.truth.sum())} true instances, {int((df.kind == 'negative').sum())} cross-family negatives).\n\n"
        + g.to_markdown(index=False, floatfmt=".3f")
        + f"\n\n**Chosen R = {best['R']}** (precision {best['precision']:.3f}, recall {best['recall']:.3f}; both >= 0.9: {bool(len(ok))}).\n\n"
        "## Reduction among true instances, by family\n\n" + by_family.to_markdown(floatfmt=".2f")
        + "\n\n## Cross-family negatives matched at the chosen R\n\n" + neg.to_frame("match_rate").to_markdown(floatfmt=".3f") + "\n"
    )
    (od / "summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
