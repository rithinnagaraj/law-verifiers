"""E0.1 Calculator agreement baseline.

Federal income tax (after credits) per filing unit, PolicyEngine-US vs
Tax-Calculator, on random households + archetypes, with no agent involved.
Output: per-unit CSV, summary.json, summary.md in results/phase0/e0_1/.

    python experiments/e0_1_agreement.py --n 5000 --workers 8
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
from common import chunks, out_dir, run_metadata, write_json

from taxred.generate import archetypes, random_households
from taxred.household import compile_filing_units
from taxred.law import Law
from taxred.taxes import evaluate_households


def unit_features(hh):
    rows = {}
    for fu in compile_filing_units(hh):
        filers = fu.filers()
        deps = fu.dependents
        s = lambda a: sum(getattr(p, a) for p in filers)
        rows[fu.id] = dict(
            household_id=hh.id,
            filing_status=fu.filing_status,
            dependent_filer=fu.is_dependent_filer,
            n_dependents=len(deps),
            n_kids_u17=sum(d.age < 17 for d in deps),
            n_students_18_23=sum(d.is_student and 18 <= d.age < 24 for d in deps),
            wages=s("wages"),
            self_employment=s("self_employment"),
            interest=s("taxable_interest"),
            qualified_dividends=s("qualified_dividends"),
            long_term_gains=s("long_term_gains"),
            itemizable=s("charitable_cash") + s("mortgage_interest"),
            childcare=s("childcare_expenses"),
            head_age=fu.head.age,
            any_65plus=any(p.age >= 65 for p in filers),
        )
    return rows


def run_chunk(args):
    hhs, law = args
    pe = evaluate_households(hhs, law, "policyengine", with_benefits=False)
    tc = evaluate_households(hhs, law, "taxcalc", with_benefits=False)
    rows = []
    for hh, a, b in zip(hhs, pe, tc):
        feats = unit_features(hh)
        tcu = {u.unit_id: u for u in b.units}
        for u in a.units:
            v = tcu[u.unit_id]
            rows.append(
                dict(
                    unit_id=u.unit_id,
                    **feats[u.unit_id],
                    pe_fed=u.fed_income_tax,
                    tc_fed=v.fed_income_tax,
                    pe_regular=u.regular_tax,
                    tc_regular=v.regular_tax,
                    pe_amt=u.amt,
                    tc_amt=v.amt,
                    pe_taxable_income=u.taxable_income,
                    tc_taxable_income=v.taxable_income,
                )
            )
    return rows


def summarize(df: pd.DataFrame) -> dict:
    d = (df.pe_fed - df.tc_fed).abs()
    rel = d / np.maximum(df[["pe_fed", "tc_fed"]].abs().max(axis=1), 1.0)
    out = {
        "n_units": int(len(df)),
        "n_households": int(df.household_id.nunique()),
        "agree_within_1": float((d <= 1).mean()),
        "agree_within_25": float((d <= 25).mean()),
        "agree_within_1pct_or_25": float(((d <= 25) | (rel <= 0.01)).mean()),
        "abs_diff_p50": float(d.quantile(0.5)),
        "abs_diff_p90": float(d.quantile(0.9)),
        "abs_diff_p99": float(d.quantile(0.99)),
        "abs_diff_max": float(d.max()),
        "regular_tax_agree_within_1": float(((df.pe_regular - df.tc_regular).abs() <= 1).mean()),
        "amt_agree_within_1": float(((df.pe_amt - df.tc_amt).abs() <= 1).mean()),
        "taxable_income_agree_within_1": float(((df.pe_taxable_income - df.tc_taxable_income).abs() <= 1).mean()),
    }
    groups = {
        "filing_status": df.filing_status,
        "dependent_filer": df.dependent_filer,
        "has_self_employment": df.self_employment > 0,
        "has_ltcg_or_qd": (df.long_term_gains + df.qualified_dividends) > 0,
        "has_kids_u17": df.n_kids_u17 > 0,
        "has_student_18_23": df.n_students_18_23 > 0,
        "has_childcare": df.childcare > 0,
        "itemizable_gt_0": df.itemizable > 0,
        "any_65plus": df.any_65plus,
    }
    out["by_group"] = {}
    for name, key in groups.items():
        g = (d <= 25).groupby(key)
        out["by_group"][name] = {str(k): {"n": int(v.size), "agree_within_25": float(v.mean())} for k, v in g}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--chunk", type=int, default=250)
    ap.add_argument("--out", default="phase0/e0_1")
    args = ap.parse_args()

    law = Law(args.year)
    hhs = archetypes(args.year) + random_households(args.n, args.seed, args.year)
    jobs = [(c, law) for c in chunks(hhs, args.chunk)]
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        for r in ex.map(run_chunk, jobs):
            rows += r
            print(f"  {len(rows)} units", flush=True)
    df = pd.DataFrame(rows)
    df["abs_diff"] = (df.pe_fed - df.tc_fed).abs()
    od = out_dir(args.out)
    df.to_csv(od / "units.csv.gz", index=False)
    summary = {"meta": run_metadata(), "law": law.label, "summary": summarize(df)}
    write_json(od / "summary.json", summary)
    top = df.sort_values("abs_diff", ascending=False).head(25)
    cols = ["unit_id", "filing_status", "dependent_filer", "wages", "self_employment", "interest", "qualified_dividends", "long_term_gains", "n_kids_u17", "pe_fed", "tc_fed", "pe_amt", "tc_amt"]
    (od / "summary.md").write_text(
        "# E0.1 calculator agreement\n\n```json\n"
        + __import__("json").dumps(summary["summary"], indent=2)
        + "\n```\n\n## Largest disagreements\n\n"
        + top[cols].to_markdown(index=False)
        + "\n"
    )
    print(__import__("json").dumps(summary["summary"], indent=2))


if __name__ == "__main__":
    main()
