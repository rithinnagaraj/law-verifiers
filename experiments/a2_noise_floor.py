"""A2. Noise floor of gains: how much do the two calculators disagree on the
change in federal tax that a random valid proposal causes?

3,000 survey households x 20 random valid proposals, current law, default
environment (3 years, 3 futures). Records PolicyEngine and Tax-Calculator
gains and full verdicts; summary by move type and income band; the frozen
tolerance is chosen by the rule in the experiment plan (summary step).

Usage: python experiments/a2_noise_floor.py [--n 3000] [--per 20] [--summary]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

from taxgap import ecps
from taxgap.config import results_dir
from taxgap.law import CURRENT_LAW
from taxgap.runner import read_rows, run
from taxgap.search.sample import random_sequence
from taxgap.verifier import Config, Verifier

HH: list = []


def band(hh) -> str:
    g = sum(p.gross_income for p in hh.people.values())
    for lo, name in ((500_000, "500k+"), (200_000, "200-500k"), (100_000, "100-200k"), (50_000, "50-100k"), (25_000, "25-50k")):
        if g >= lo:
            return name
    return "<25k"


def job(j: dict) -> list:
    v = Verifier(CURRENT_LAW, Config())
    props, meta = [], []
    for k in j["households"]:
        hh = HH[k]
        rng = np.random.default_rng([j["seed"], k])
        for t in range(j["per"]):
            seq = random_sequence(hh, rng)
            if not seq:
                continue
            props.append((hh, seq))
            meta.append({"hh": hh.id, "k": k, "t": t, "band": band(hh), "moves": seq, "ops": sorted({m["op"] for m in seq})})
    t0 = time.time()
    out = v.evaluate(props)
    dt = time.time() - t0
    return [{**m, "verdict": vd.to_dict(), "sec": dt / max(len(props), 1)} for m, vd in zip(meta, out)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--per", type=int, default=20)
    ap.add_argument("--jobsize", type=int, default=10)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--tag", default="a2")
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    out = results_dir(a.tag) / "proposals.jsonl"
    if not a.summary:
        HH.extend(ecps.load(a.n, seed=0))
        print(f"[a2] {len(HH)} survey households", flush=True)
        jobs = [{"id": f"j{s}", "households": list(range(s, min(s + a.jobsize, len(HH)))), "per": a.per, "seed": a.seed} for s in range(0, len(HH), a.jobsize)]
        run(jobs, job, out, workers=a.workers)
    summarize(read_rows(out), results_dir(a.tag))


TOLS_ABS = (5.0, 10.0, 25.0)
TOLS_REL = (0.01, 0.02, 0.05)


def summarize(rows: list, d) -> None:
    from taxgap.verifier import label

    valid = [r for r in rows if r["verdict"]["error"] is None]
    if not valid:
        print("no rows")
        return
    gp = np.array([r["verdict"]["gain"] for r in valid])
    gt = np.array([r["verdict"]["gain_tc"] for r in valid])
    dis = np.abs(gp - gt)
    rel = dis / np.maximum(np.abs(gp), 1.0)
    nz = np.abs(gp) > 1
    q = lambda x: {f"p{p}": float(np.percentile(x, p)) for p in (50, 90, 95, 99, 99.9)} if len(x) else {}
    lines = ["# A2: noise floor of gains (current law, random valid proposals)", ""]
    lines.append(f"Proposals: {len(rows)} ({len(valid)} valid), households: {len({r['hh'] for r in rows})}.")
    lines.append(f"Proposals with a PolicyEngine gain or loss above $1: {int(nz.sum())}.")
    lines.append("")
    lines.append("| | all valid | gain or loss > $1 |")
    lines.append("|---|---|---|")
    for k in ("p50", "p90", "p95", "p99", "p99.9"):
        lines.append(f"| abs. disagreement {k} | ${q(dis)[k]:,.2f} | ${q(dis[nz])[k]:,.2f} |")
    for k in ("p50", "p90", "p95", "p99"):
        lines.append(f"| rel. disagreement {k} | {q(rel[nz])[k]:.4f} | |")
    lines.append(f"| share exactly equal (< $0.5) | {np.mean(dis < 0.5):.4f} | {np.mean(dis[nz] < 0.5):.4f} |")
    lines.append("")
    # tolerance rule
    lines.append("## Tolerance grid: share of valid random proposals labelled code_disagreement")
    lines.append("")
    lines.append("| abs \\ rel | " + " | ".join(f"{r:.0%}" for r in TOLS_REL) + " |")
    lines.append("|---|" + "---|" * len(TOLS_REL))
    from taxgap.verifier import Verdict

    vs = [Verdict.from_dict(r["verdict"]) for r in valid]
    grid = {}
    for ta in TOLS_ABS:
        row = []
        for tr in TOLS_REL:
            cfg = Config(tol_abs=ta, tol_rel=tr)
            share = float(np.mean([label(v, cfg) == "code_disagreement" for v in vs]))
            grid[(ta, tr)] = share
            row.append(f"{share:.4f}")
        lines.append(f"| ${ta:g} | " + " | ".join(row) + " |")
    passing = [k for k, s in grid.items() if s <= 0.01]
    med = float(np.median(np.abs(gp[gp > 50]))) if (gp > 50).any() else 1000.0
    choice = min(passing, key=lambda k: (max(k[0], k[1] * med), k[1])) if passing else None
    lines.append("")
    lines.append(f"Rule: the smallest max($a, b%) with <= 1% of random proposals labelled code_disagreement; 'smallest' = smallest tolerance at the median gain of proposals with a gain (${med:,.0f}), ties to the smaller b.")
    lines.append(f"**Choice: {('max($%g, %g%%)' % (choice[0], choice[1] * 100)) if choice else 'none passes'}**")
    lines.append("")
    # by move type and income band
    lines.append("## By move type (proposals containing the op; gain or loss > $1)")
    lines.append("")
    lines.append("| op | n | p50 abs | p95 abs | p99 abs | share > $10 |")
    lines.append("|---|---|---|---|---|---|")
    ops = sorted({o for r in valid for o in r["ops"]})
    for o in ops:
        m = np.array([o in r["ops"] for r in valid]) & nz
        if m.any():
            x = dis[m]
            lines.append(f"| {o} | {int(m.sum())} | {np.percentile(x, 50):.2f} | {np.percentile(x, 95):.2f} | {np.percentile(x, 99):.2f} | {np.mean(x > 10):.3f} |")
    lines.append("")
    lines.append("| income band | n | p50 abs | p95 abs | p99 abs | share > $10 |")
    lines.append("|---|---|---|---|---|---|")
    for b in ("<25k", "25-50k", "50-100k", "100-200k", "200-500k", "500k+"):
        m = np.array([r["band"] == b for r in valid]) & nz
        if m.any():
            x = dis[m]
            lines.append(f"| {b} | {int(m.sum())} | {np.percentile(x, 50):.2f} | {np.percentile(x, 95):.2f} | {np.percentile(x, 99):.2f} | {np.mean(x > 10):.3f} |")
    lines.append("")
    labels = {}
    for v in vs:
        labels[v.label] = labels.get(v.label, 0) + 1
    lines.append("Labels at the default tolerance max($10, 2%): " + ", ".join(f"{k} {n}" for k, n in sorted(labels.items())))
    secs = [r["sec"] for r in valid]
    lines.append(f"Mean verifier time per proposal (per worker): {np.mean(secs):.2f} s.")
    (d / "summary.md").write_text("\n".join(lines) + "\n")
    worst = sorted(valid, key=lambda r: -abs(r["verdict"]["gain"] - r["verdict"]["gain_tc"]))[:50]
    (d / "worst50.json").write_text(json.dumps(worst, indent=1, default=float))
    json.dump({"tolerance_grid": {f"{a}|{b}": s for (a, b), s in grid.items()}, "choice": choice, "n": len(valid)}, open(d / "summary.json", "w"), indent=1)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
