"""E1.1 main H1 test on the historical-closure set (taxred.cases).

For each closure case and each witness household:
  - verdict under pre-closure law (no attribution) and post-closure law
    (with attribution, so the residual gain can be decomposed);
  - reduction = share of the pre-closure gain the closure removes, measured
    on PolicyEngine's total gain and, separately, on each calculator's
    federal income-tax gain (so a closure invisible to one calculator shows).

H1 on the closed mechanism (amended; see FINDINGS.md):
  sensitivity  households the closure legally covers: flagged pre-closure and
               the closure removes a detectable share (> R_EPS) of the gain
  match rate   covered households where the reduction is >= R_MIN (the
               closure-test half of the matching rule; R_MIN is set in E0.7)
  specificity  households the closure does not cover: |reduction| <= R_EPS
  post         the closed provision is not in the post-closure signature;
               the residual is reported by provision.

    python experiments/e1_closures.py --workers 8
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
from common import out_dir, run_metadata, write_json

from taxred.cases import closure_cases
from taxred.law import PROVISIONS
from taxred.verifier import Verifier, VerifierConfig

R_MIN = 0.2  # proposed; to be fixed from E0.7
R_EPS = 0.02
FLAGGED = ("candidate", "code_disagreement")


def clopper_pearson(k: int, n: int, alpha: float = 0.05):
    if n == 0:
        return (float("nan"), float("nan"))
    from scipy.stats import beta

    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return (lo, hi)


def _red(pre: float, post: float) -> float:
    return (pre - post) / pre if pre > 1e-9 else np.nan


def run_case(args):
    name, year = args
    case = closure_cases(year)[name]
    hhs = case.panel(year)
    props = [(h, case.witness(h)) for h in hhs]
    pre = Verifier(case.law_pre, VerifierConfig(run_attribution=False)).evaluate_many(props)
    post = Verifier(case.law_post, VerifierConfig()).evaluate_many(props)
    rows = []
    for h, a, b in zip(hhs, pre, post):
        rows.append(
            dict(
                case=name,
                household_id=h.id,
                covered=bool(case.covered(h)),
                label_pre=a.label,
                label_post=b.label,
                gain_pre=a.gain,
                gain_post=b.gain,
                fed_pe_pre=a.gain_federal_pe,
                fed_pe_post=b.gain_federal_pe,
                fed_tc_pre=a.gain_federal_tc,
                fed_tc_post=b.gain_federal_tc,
                crosscheck_pre=a.crosscheck_pass,
                crosscheck_post=b.crosscheck_pass,
                coverage_post=b.coverage,
                signature_post=",".join(b.signature),
                circumvents_post=",".join(b.circumvents),
                closed_in_post_signature=bool(set(case.closed) & set(b.signature)),
                residual_without_intended=b.residual_without_intended,
                attribution_post=json.dumps({k: round(x, 4) for k, x in b.attribution.items()}),
            )
        )
    return rows


def summarize(df: pd.DataFrame, cases, year: int = 2024) -> tuple[dict, str]:
    df = df.copy()
    # Recompute coverage from the case definitions (CSV may predate a change).
    cov = {}
    for name in df["case"].unique():
        c = cases[name]
        cov.update({(name, h.id): bool(c.covered(h)) for h in c.panel(year)})
    df["covered"] = [cov[(c, h)] for c, h in zip(df["case"], df.household_id)]
    df["red"] = [_red(a, b) for a, b in zip(df.gain_pre, df.gain_post)]
    df["red_fed_pe"] = [_red(a, b) for a, b in zip(df.fed_pe_pre, df.fed_pe_post)]
    df["red_fed_tc"] = [_red(a, b) for a, b in zip(df.fed_tc_pre, df.fed_tc_post)]
    df["flag_pre"] = df.label_pre.isin(FLAGGED)
    df["flag_post"] = df.label_post.isin(FLAGGED)
    df["sens"] = df.flag_pre & (df.red > R_EPS)
    df["match"] = df.red >= R_MIN
    df["sens_pe_fed"] = df.red_fed_pe > R_EPS
    df["sens_tc_fed"] = df.red_fed_tc > R_EPS
    df["spec"] = df.red.abs().fillna(0) <= R_EPS
    out, lines = {}, []
    for name, g in df.groupby("case", sort=False):
        c = cases[name]
        cov, unc = g[g.covered], g[~g.covered]
        k, n = int(cov.sens.sum()), len(cov)
        ks, ns = int(unc.spec.sum()), len(unc)
        res_attr = {}
        flagged_post = cov[cov.flag_post]
        if len(flagged_post):
            att = pd.DataFrame([json.loads(s) for s in flagged_post.attribution_post])
            res_attr = att.median().round(3).to_dict()
        out[name] = dict(
            coverage=c.coverage,
            closure=c.closure,
            n_covered=n,
            n_not_covered=ns,
            sensitivity=k / n if n else None,
            sensitivity_ci=clopper_pearson(k, n),
            sensitivity_pe_federal=float(cov.sens_pe_fed.mean()) if n else None,
            sensitivity_tc_federal=float(cov.sens_tc_fed.mean()) if n else None,
            match_rate=float(cov.match.mean()) if n else None,
            specificity=ks / ns if ns else None,
            specificity_ci=clopper_pearson(ks, ns),
            flag_rate_pre_covered=float(cov.flag_pre.mean()) if n else None,
            flag_rate_post_covered=float(cov.flag_post.mean()) if n else None,
            closed_in_post_signature=float(cov.closed_in_post_signature.mean()) if n else None,
            median_reduction_covered=float(cov.red.median()) if n else None,
            median_reduction_not_covered=float(unc.red.median()) if ns else None,
            post_labels=g[g.covered].label_post.value_counts().to_dict(),
            post_residual_median_attribution=res_attr,
        )
        s = out[name]
        f = lambda x: "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2f}"
        lines.append(
            f"| {name} | {c.coverage} | {n} | {f(s['sensitivity'])} [{f(s['sensitivity_ci'][0])}, {f(s['sensitivity_ci'][1])}] "
            f"| {f(s['sensitivity_pe_federal'])} | {f(s['sensitivity_tc_federal'])} | {f(s['match_rate'])} "
            f"| {ns} | {f(s['specificity'])} | {f(s['flag_rate_post_covered'])} | {f(s['closed_in_post_signature'])} "
            f"| {f(s['median_reduction_covered'])} |"
        )
    md = (
        "# E1.1 historical closures: H1 on the closed mechanism\n\n"
        f"Sensitivity: legally covered households flagged pre-closure where the closure removes > {R_EPS:.0%} of the gain "
        f"(95% Clopper-Pearson CI). PE/TC fed: same test on each calculator's federal income-tax gain. "
        f"Match: share of covered households where the closure removes >= {R_MIN:.0%} (closure-test half of the matching rule). "
        f"Specificity: households the closure should not affect, with |reduction| <= {R_EPS:.0%}. "
        "Post flag: share of covered households still flagged after the closure (residual from other provisions). "
        "Closed in sig: the closed provision appears in the post-closure attribution signature (should be 0).\n\n"
        "| case | coverage | n cov | sensitivity | PE fed | TC fed | match @R_MIN | n not cov | specificity | post flag | closed in sig | median red. |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(lines) + "\n\n## Post-closure residual: median attribution share among still-flagged covered households\n\n"
    )
    for name, s in out.items():
        if s["post_residual_median_attribution"]:
            top = sorted(s["post_residual_median_attribution"].items(), key=lambda kv: -kv[1])
            md += f"- **{name}**: " + ", ".join(f"{k} {v:.2f}" for k, v in top if abs(v) >= 0.01) + "\n"
    md += "\n## Post-closure labels (covered households)\n\n"
    for name, s in out.items():
        md += f"- **{name}**: {s['post_labels']}\n"
    return out, md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--cases", nargs="*", default=None)
    ap.add_argument("--from-csv", action="store_true")
    a = ap.parse_args()
    cases = closure_cases(a.year)
    names = a.cases or list(cases)
    od = out_dir("phase1/closures")
    if a.from_csv:
        df = pd.read_csv(od / "verdicts.csv")
    else:
        rows = []
        with ProcessPoolExecutor(min(a.workers, len(names))) as ex:
            for r in ex.map(run_case, [(n, a.year) for n in names]):
                rows += r
        df = pd.DataFrame(rows)
        df.to_csv(od / "verdicts.csv", index=False)
    summ, md = summarize(df, cases)
    write_json(od / "summary.json", {"meta": run_metadata(), "R_MIN": R_MIN, "R_EPS": R_EPS, "cases": summ})
    (od / "summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
