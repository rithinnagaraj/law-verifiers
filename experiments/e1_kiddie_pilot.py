"""E1.1 pilot on the anchor case: the kiddie tax and its staged expansions.

Strategy (witness): a parent gifts an interest-bearing bond to a dependent
child, so the interest is taxed on the child's return.
Law versions: none (pre-1987) -> TRA 1986 (<14) -> TIPRA 2005 (<18) ->
SBWOTA 2007 (<19, students <24), all as counterfactuals on 2024 law.

Prediction (H1 dose-response): the strategy is flagged under `none` for all
child ages; each closure stops flagging the newly covered ages; a
20-year-old non-student is never covered.

    python experiments/e1_kiddie_pilot.py --workers 4
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from common import chunks, out_dir, run_metadata, safe_workers, write_json

from taxred.household import Asset, Household, Person, TaxUnit
from taxred.law import KIDDIE_RULES, Law
from taxred.verifier import Verifier, VerifierConfig

LAWS = ["none", "tra1986", "tipra2005", "sbwota2007"]
CHILD = [(8, False), (13, False), (16, False), (18, False), (20, True), (22, True), (20, False)]


def panel(year: int):
    out = []
    for (wages, married), interest, (age, student) in itertools.product(
        [(40_000, False), (100_000, False), (200_000, True), (400_000, True)],
        [5_000, 20_000, 60_000],
        CHILD,
    ):
        hid = f"w{wages}_i{interest}_a{age}{'s' if student else ''}"
        people = {
            "p1": Person("p1", 45, wages=wages if not married else wages * 0.6, hours=2080,
                         assets=[Asset("bond", interest / 0.05, interest / 0.05, interest_yield=0.05)]),
            "kid": Person("kid", age, is_student=student),
        }
        unit = TaxUnit("t", "p1", dependents=["kid"])
        pairs = []
        if married:
            people["p2"] = Person("p2", 44, wages=wages * 0.4, hours=2080)
            unit.spouse = "p2"
            pairs = [("p1", "p2")]
        out.append(Household(hid, year, "TX", people, [unit], pairs))
    return out


MOVE = [{"op": "gift_asset", "giver": "p1", "recipient": "kid", "asset": "bond", "fraction": 1.0}]


def run(args):
    hhs, key, year = args
    cfg = VerifierConfig(attribution_provisions=(
        "kiddie_tax", "kiddie_allowance", "dependent_std_deduction_floor", "niit", "eitc", "child_amt_exemption_limit"))
    vs = Verifier(Law(year).with_kiddie(key), cfg).evaluate_many([(h, MOVE) for h in hhs])
    rows = []
    for h, v in zip(hhs, vs):
        kid = h.people["kid"]
        rows.append(dict(household_id=h.id, law=key, child_age=kid.age, student=kid.is_student,
                         parent_wages=sum(p.wages for p in h.people.values() if p.id != "kid"),
                         interest=h.people["p1"].taxable_interest, label=v.label, gain=v.gain,
                         gain_fed_pe=v.gain_federal_pe, gain_fed_tc=v.gain_federal_tc,
                         crosscheck=v.crosscheck_pass, signature=",".join(v.signature), residual_without_intended=v.residual_without_intended,
                         attribution=json.dumps({k: round(x, 3) for k, x in v.attribution.items()})))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--from-csv", action="store_true", help="rebuild the summary from saved verdicts")
    a = ap.parse_args()
    hhs = panel(a.year)
    od = out_dir("phase1/kiddie_pilot")
    if a.from_csv:
        df = pd.read_csv(od / "verdicts.csv")
    else:
        jobs = [(c, k, a.year) for k in LAWS for c in chunks(hhs, 21)]
        rows = []
        with ProcessPoolExecutor(safe_workers(a.workers)) as ex:
            for r in ex.map(run, jobs):
                rows += r
        df = pd.DataFrame(rows)
        df.to_csv(od / "verdicts.csv", index=False)

    df["child"] = df.child_age.astype(str) + df.student.map({True: " student", False: ""})
    df["flagged"] = df.label.isin(["candidate", "code_disagreement"])
    flag = df.pivot_table(index="child", columns="law", values="flagged", aggfunc="mean")[LAWS]
    gain = df.pivot_table(index="child", columns="law", values="gain", aggfunc="median")[LAWS]
    disagree = df.pivot_table(index="child", columns="law", values="crosscheck", aggfunc=lambda s: 1 - s.mean())[LAWS]
    # Closure test: share of the `none` gain removed by each later law.
    base = df[df.law == "none"].set_index("household_id").gain
    red = {}
    for k in LAWS[1:]:
        g = df[df.law == k].set_index("household_id").gain
        r = ((base - g) / base).where(base > 0)
        red[k] = df[df.law == k].set_index("household_id").assign(red=r).groupby("child").red.median()
    red = pd.DataFrame(red)

    def covered(age, student, key):
        rule = KIDDIE_RULES[key]
        return bool(rule.enabled and (age < rule.age_under or (student and rule.student_age_under and age < rule.student_age_under)))

    df["should_be_closed"] = [covered(r.child_age, r.student, r.law) for r in df.itertuples()]
    pre = df[~df.should_be_closed]
    post = df[df.should_be_closed]
    summary = {
        "meta": run_metadata(),
        "n_households": len(hhs),
        "flag_rate_not_covered": float(pre.flagged.mean()),
        "flag_rate_covered": float(post.flagged.mean()),
        "label_counts": df.groupby(["law", "label"]).size().unstack(fill_value=0).to_dict(),
    }
    write_json(od / "summary.json", summary)
    (od / "summary.md").write_text(
        "# E1.1 pilot: kiddie tax dose-response\n\n"
        f"Households: {len(hhs)} per law version. Strategy: gift interest-bearing bond to dependent child.\n\n"
        f"- Flag rate where no kiddie rule covers the child (should be high): **{summary['flag_rate_not_covered']:.1%}**\n"
        f"- Flag rate where a kiddie rule covers the child (should be low): **{summary['flag_rate_covered']:.1%}**\n\n"
        "Flagged = label `candidate` or `code_disagreement` (a gain the verifier does not explain as intended).\n\n"
        "## Flag rate\n\n" + flag.to_markdown(floatfmt=".2f") +
        "\n\n## Median gain ($/yr)\n\n" + gain.to_markdown(floatfmt=".0f") +
        "\n\n## Cross-check failure rate\n\n" + disagree.to_markdown(floatfmt=".2f") +
        "\n\n## Median share of pre-closure gain removed by each law (closure test; match if >= 0.8)\n\n" + red.to_markdown(floatfmt=".2f") +
        "\n\n## Labels\n\n" + df.groupby(["law", "label"]).size().unstack(fill_value=0).to_markdown() + "\n"
    )
    print((od / "summary.md").read_text())


if __name__ == "__main__":
    main()
