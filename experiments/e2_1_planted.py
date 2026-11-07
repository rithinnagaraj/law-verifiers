"""E2.1 planted-variant generator: validate each variant and measure reach.

For each variant: the witness under the mutated law (full attribution) and
under the closure (unmutated law). A variant is valid when the witness is
flagged (candidate, or code_disagreement for single-calc families) under the
mutated law and reverting the mutation removes >= MIN_REDUCTION of its gain.
Reach: the share of the family's panel households where the same moves are
flagged and the closure removes >= MIN_REDUCTION.

Writes results/phase2/planted/{variants.json, verdicts.csv, summary.md}.

    python experiments/e2_1_planted.py --workers 6
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from common import out_dir, run_metadata, write_json

from taxred.planted import variants
from taxred.verifier import Verifier, VerifierConfig

MIN_REDUCTION = 0.5
FLAGGED = ("candidate", "code_disagreement")


def run(args):
    vid, year = args
    v = next(x for x in variants(year) if x.id == vid)
    hhs = [v.witness_household] + v.panel
    props = [(h, v.witness) for h in hhs]
    mut = Verifier(v.law, VerifierConfig()).evaluate_many(props)
    clo = Verifier(v.closure, VerifierConfig(run_attribution=False)).evaluate_many(props)
    rows = []
    for i, (h, a, b) in enumerate(zip(hhs, mut, clo)):
        red = (a.gain - b.gain) / a.gain if a.gain > 1e-9 else float("nan")
        rows.append(
            dict(
                variant=v.id,
                family=v.family,
                split=v.split,
                is_witness=i == 0,
                household_id=h.id,
                label=a.label,
                label_closure=b.label,
                gain=a.gain,
                gain_closure=b.gain,
                reduction=red,
                gain_federal_pe=a.gain_federal_pe,
                gain_federal_tc=a.gain_federal_tc,
                coverage=a.coverage,
                signature=",".join(a.signature),
                error=a.error,
                exploited=bool(a.label in FLAGGED and red >= MIN_REDUCTION),
            )
        )
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    vs = variants(a.year)
    od = out_dir("phase2/planted")
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(run, [(v.id, a.year) for v in vs]):
            rows += r
    df = pd.DataFrame(rows)
    df.to_csv(od / "verdicts.csv", index=False)
    w = df[df.is_witness].set_index("variant")
    reach = df[~df.is_witness].groupby("variant").exploited.mean()
    manifest = []
    for v in vs:
        r = w.loc[v.id]
        manifest.append(
            dict(
                id=v.id, family=v.family, operator=v.operator, magnitude=v.magnitude, split=v.split, coverage=v.coverage,
                held_out_family=v.held_out_family, valid=bool(r.exploited), witness_gain=float(r.gain),
                witness_reduction=float(r.reduction), witness_label=r.label, reach=float(reach.get(v.id, 0.0)),
                description=v.description, disguised=v.disguised, witness=v.witness,
            )
        )
    (od / "variants.json").write_text(json.dumps(manifest, indent=2, default=float))
    tab = pd.DataFrame(manifest)[["id", "family", "split", "coverage", "valid", "witness_label", "witness_gain", "witness_reduction", "reach"]]
    md = (
        f"# E2.1 planted variants ({len(vs)}; valid {int(tab.valid.sum())})\n\n"
        f"Valid: witness flagged under the mutated law and the closure removes >= {MIN_REDUCTION:.0%} of its gain. "
        "Reach: share of the family panel exploited the same way.\n\n" + tab.to_markdown(index=False, floatfmt=".2f") +
        "\n\n## Witness signatures\n\n" + w[["family", "label", "signature", "gain_federal_pe", "gain_federal_tc", "error"]].to_markdown(floatfmt=".0f") + "\n"
    )
    write_json(od / "summary.json", {"meta": run_metadata(), "n": len(vs), "valid": int(tab.valid.sum())})
    (od / "summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
