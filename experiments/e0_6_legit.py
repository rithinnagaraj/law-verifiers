"""E0.6 legitimate-planning set and E1.2 ablation of the checks.

Runs every scenario in taxred.planning through the verifier with full
attribution of every gain (attribute_all), saves the verdicts, then:

  E0.6  false-positive rate on positives (legitimate planning flagged as
        candidate / code_disagreement), per family and per dev/test split;
        accuracy on labelled negatives (sacrifice, benefit cliff, wash sale).
  E1.2  relabels the same verdicts with one check switched off at a time
        (reality check, cross-check, whitelist, gain threshold) and reports
        the change in false positives and in misses on the closure set
        (results/phase1/closures, if present).

    python experiments/e0_6_legit.py --workers 8
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from common import chunks, out_dir, run_metadata, write_json

from taxred.law import Law
from taxred.planning import scenarios
from taxred.verifier import Verdict, Verifier, VerifierConfig, decide_label

FLAGGED = ("candidate", "code_disagreement")
CFG = VerifierConfig(attribute_all=True)
ABLATIONS = {
    "full": {},
    "no_reality_check": {"use_reality_check": False},
    "no_crosscheck": {"use_crosscheck": False},
    "no_whitelist": {"use_whitelist": False},
    "no_anti_abuse_override": {"anti_abuse_overrides_intended": False},
    "no_gain_threshold": {"gain_threshold": 0.0},
}


def run(args):
    ids, year = args
    sc = {s.id: s for s in scenarios(year)}
    batch = [sc[i] for i in ids]
    vs = Verifier(Law(year), CFG).evaluate_many([(s.household, s.moves) for s in batch])
    return [dict(id=s.id, family=s.family, split=s.split, positive=s.positive, expected=",".join(sorted(s.expected)), **v.to_dict()) for s, v in zip(batch, vs)]


def relabel(row: dict, cfg: VerifierConfig) -> str:
    v = Verdict(**{k: row[k] for k in Verdict.__dataclass_fields__ if k in row})
    return decide_label(v, cfg, attributed=v.residual_without_intended is not None or bool(v.attribution))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--from-json", action="store_true")
    a = ap.parse_args()
    od = out_dir("phase1/legit")
    if a.from_json:
        rows = json.loads((od / "verdicts.json").read_text())
    else:
        ids = [s.id for s in scenarios(a.year)]
        size = max(1, -(-len(ids) // a.workers))
        rows = []
        with ProcessPoolExecutor(a.workers) as ex:
            for r in ex.map(run, [(c, a.year) for c in chunks(ids, size)]):
                rows += r
        (od / "verdicts.json").write_text(json.dumps(rows, default=float))

    df = pd.DataFrame(rows)
    for name, kw in ABLATIONS.items():
        cfg = replace(CFG, **kw)
        df[f"label_{name}"] = [relabel(r, cfg) for r in rows]
    df["fp"] = df.positive & df.label_full.isin(FLAGGED)
    df["correct"] = [lab in set(e.split(",")) for lab, e in zip(df.label_full, df.expected)]
    pos, neg = df[df.positive], df[~df.positive]

    abl = {}
    for name in ABLATIONS:
        lab = df[f"label_{name}"]
        abl[name] = dict(
            fp_rate=float((df.positive & lab.isin(FLAGGED)).sum() / max(1, len(pos))),
            negatives_flagged=float((~df.positive & lab.isin(FLAGGED)).sum() / max(1, len(neg))),
        )
    summary = dict(
        meta=run_metadata(),
        n_positive=len(pos),
        n_negative=len(neg),
        fp_rate=float(pos.fp.mean()),
        fp_rate_by_split=pos.groupby("split").fp.mean().to_dict(),
        fp_rate_by_family=pos.groupby("family").fp.mean().to_dict(),
        negatives_correct=float(neg.correct.mean()),
        negatives_correct_by_family=neg.groupby("family").correct.mean().to_dict(),
        labels_by_family=df.groupby(["family", "label_full"]).size().unstack(fill_value=0).to_dict(orient="index"),
        ablation=abl,
    )
    write_json(od / "summary.json", summary)
    fpcols = ["id", "family", "label_full", "gain", "gain_federal_pe", "gain_federal_tc", "gain_benefits", "gain_other_tax", "residual_without_intended", "signature", "circumvents"]
    fps = df[df.fp][fpcols]
    md = (
        "# E0.6 legitimate-planning set and E1.2 check ablation\n\n"
        f"Positives (legitimate planning): {len(pos)}; labelled negatives: {len(neg)}.\n\n"
        f"- **False-positive rate: {summary['fp_rate']:.1%}** (dev {summary['fp_rate_by_split'].get('dev', float('nan')):.1%}, test {summary['fp_rate_by_split'].get('test', float('nan')):.1%}); H1 target <= 5%\n"
        f"- Labelled negatives with the expected label: {summary['negatives_correct']:.1%}\n\n"
        "## Labels by family\n\n" + df.groupby(["family", "label_full"]).size().unstack(fill_value=0).to_markdown() +
        "\n\n## E1.2 ablation (relabelling the same verdicts)\n\n" + pd.DataFrame(abl).T.to_markdown(floatfmt=".3f") +
        "\n\n## False positives\n\n" + (fps.to_markdown(index=False, floatfmt=".2f") if len(fps) else "none") + "\n"
    )
    (od / "summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
