"""A5. Interaction-mutation catalog.

Stages:
  --stage a5a   spike 1: the first 10 generator-v2 candidates; gate G0
                (>= 3 of 10 pass) decides whether A4, A5b and A7 proceed
  --stage a5a2  spike 2 after G0 revision 1: the first 10 generator-v3
                candidates (spike 1 excluded); a5a3 is reserved for revision 2
  --stage a5b   the next candidates of the last spike's generator
                (up to 50, --extend: 80; v3 has fewer)
  --summary     family manifest, counts by operator and mechanism,
                rejection reasons, G0/G2, split (once A5b is complete)

Each job gates one candidate at both magnitudes (experiment plan A5).

Family status (rule set 2026-11-24, before the A5a spike):
  pass     both magnitudes pass all five checks with a witness of k >= 2 moves
  shallow  no check failed, but at least one magnitude's minimal witness is a
           single move (checks 2 and 4 vacuous); reported with its own count,
           never counted toward G0, G2 or the split
  fail     anything else (no witness, or a failed check)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict

import numpy as np

from taxgap.config import results_dir
from taxgap.mutations.family import gate
from taxgap.mutations.generate import all_families, candidates
from taxgap.runner import read_rows, run

SEED = 0
SPIKE = 10
SPIKES = {"a5a": 2, "a5a2": 3}  # spike stage -> generator version (DECISIONS.md, G0 revisions)
A5B_GEN = 3  # generator of the last spike
STAGES = (*SPIKES, "a5b")
G0_MIN = 3
G2_MIN = 20

DISCLAIMER = (
    "The candidate catalog is constructed: a designed generator pairs parameters at "
    "structures chosen to interact (v2: regular tax vs AMT, the EITC's tests, filing-status parameters; "
    "v3 after G0 revision 1: two tests of one benefit, each of which alone denies it) "
    "and scales them x2 and x4. Pass rates measure how many of these designed candidates "
    "yield gated, non-decomposable interaction families; they are not an estimate of how "
    "common such interactions are in tax law."
)


def status(gates: list) -> str:
    if all(g["passed"] for g in gates):
        return "pass"
    clean = all(g["passed"] or (g.get("shallow") and all(c["ok"] for c in g.get("checks", {}).values())) for g in gates)
    return "shallow" if clean and any(g.get("shallow") for g in gates) else "fail"


def operator(fid: str) -> str:
    return fid.split(":", 1)[0]


def job(j: dict) -> list:
    fam = all_families(SEED)[j["family"]]
    rows = []
    for m in fam.magnitudes:
        rng = np.random.default_rng([int(hashlib.sha1(fam.id.encode()).hexdigest()[:8], 16), int(m * 10)])
        rows.append(gate(fam, m, rng))
    st = status(rows)
    return [{"family": fam.describe(), "stage": j["stage"], "status": st, "passed": st == "pass", "gates": rows}]


def split(passing: list, seed: int = SEED) -> dict:
    """Experiment plan A5 split, by family then mechanism, filled test -> val -> train.
    Two mechanisms (seeded choice) go to test only; test is then filled to
    max(8, 40%) from the other families in seeded order, val to max(3, 15%),
    and train takes the rest. Families are units (both magnitudes together).
    Rule fixed 2026-11-24, before the A5a spike; passing families only."""
    rng = np.random.default_rng(seed)
    n = len(passing)
    mechs = sorted({f["mechanism"] for f in passing})
    order = [mechs[i] for i in rng.permutation(len(mechs))]
    test_only = order[:2] if len(mechs) >= 3 else []
    test = [f["id"] for f in passing if f["mechanism"] in test_only]
    rest = [f["id"] for f in passing if f["mechanism"] not in test_only]
    rest = [rest[i] for i in rng.permutation(len(rest))]
    n_test, n_val = max(8, round(0.4 * n)), max(3, round(0.15 * n))
    while len(test) < n_test and rest:
        test.append(rest.pop(0))
    val = [rest.pop(0) for _ in range(min(n_val, len(rest)))]
    return {"n": n, "test_only_mechanisms": test_only, "test": test, "val": val, "train": rest,
            "note": "" if test_only else "fewer than 3 mechanisms passed: no mechanism reserved for test"}


def _table(rs: list, key, title: str) -> list:
    groups = defaultdict(list)
    for r in rs:
        groups[key(r)].append(r["status"])
    out = [f"| {title} | candidates | pass | shallow | fail |", "|---|---|---|---|---|"]
    for g in sorted(groups):
        c = Counter(groups[g])
        out.append(f"| {g} | {len(groups[g])} | {c['pass']} | {c['shallow']} | {c['fail']} |")
    return out


def summarize(d) -> None:
    rows = [r for s in STAGES for r in read_rows(d / f"{s}.jsonl")]
    for r in rows:
        r.setdefault("status", status(r["gates"]))
        r["passed"] = r["status"] == "pass"
    lines = ["# A5: interaction-mutation catalog", "", DISCLAIMER, "",
             "Counting rule (set before the A5a spike): only families whose minimal witness needs >= 2 moves "
             "at both magnitudes can pass; one-move (shallow) families are reported separately and do not "
             "count toward G0, G2 or the split.", ""]
    g0_met = set()
    for stage in STAGES:
        rs = [r for r in rows if r["stage"] == stage]
        if not rs:
            continue
        c = Counter(r["status"] for r in rs)
        lines.append(f"## {stage}: {c['pass']} of {len(rs)} candidates pass ({c['shallow']} shallow, {c['fail']} fail)")
        if stage in SPIKES:
            if c["pass"] >= G0_MIN:
                g0_met.add(stage)
            lines.append(f"**G0, spike {list(SPIKES).index(stage) + 1} (generator v{SPIKES[stage]}; >= {G0_MIN} of {SPIKE} pass, shallow excluded): {'PASS' if c['pass'] >= G0_MIN else 'FAIL'}**")
        lines.append("")
        lines += _table(rs, lambda r: operator(r["family"]["id"]), "operator") + [""]
        lines += _table(rs, lambda r: r["family"]["mechanism"], "mechanism") + [""]
        lines.append("| candidate | status | m | witness (k) | one-move witnesses | 1 | 2 | 3 | 4 | 5 | gate result |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rs:
            for g in r["gates"]:
                ch = g.get("checks", {})
                ok = lambda k: ("vacuous" if k in g.get("vacuous", []) else "-") if k not in ch else ("ok" if ch[k]["ok"] else "FAIL")
                w = g.get("witness", {})
                wk = f"{w.get('household_id', '-')} ({w.get('k', '-')})" if w.get("found") else "none"
                lines.append(f"| {r['family']['id']} | {r['status']} | {g['magnitude']:g} | {wk} | {w.get('n_one_move', '-')} | {ok('1_witness')} | {ok('2_grid')} | {ok('3_ablation')} | {ok('4_spot')} | {ok('5_reverse')} | {'pass' if g['passed'] else g.get('reason', '')} |")
        lines.append("")
        reasons = Counter((g.get("reason") or "pass") for r in rs for g in r["gates"])
        lines.append("Gate outcomes (per magnitude): " + ", ".join(f"{k}: {n}" for k, n in reasons.most_common()))
        fails = Counter(k for r in rs for g in r["gates"] for k, ch in g.get("checks", {}).items() if not ch["ok"])
        lines.append("Failed checks (per magnitude; a gate can fail several): " + (", ".join(f"{k}: {n}" for k, n in sorted(fails.items())) or "none"))
        lines.append("")
    c = Counter(r["status"] for r in rows)
    lines.append(f"All stages: {c['pass']} pass, {c['shallow']} shallow, {c['fail']} fail of {len(rows)} candidates. "
                 f"G2 (>= {G2_MIN} passing families): {'met' if c['pass'] >= G2_MIN else 'not met'} so far.")
    manifest = [{"family": r["family"], "operator": operator(r["family"]["id"]), "stage": r["stage"], "status": r["status"], "passed": r["passed"],
                 "reasons": [g.get("reason") or "pass" for g in r["gates"]]} for r in rows]
    json.dump(manifest, open(d / "manifest.json", "w"), indent=1)
    cand_file = d / "a5b_candidates.json"
    if cand_file.exists() and len([r for r in rows if r["stage"] == "a5b"]) >= len(json.load(open(cand_file))):
        # passing families of a5b and of spikes that met G0 (a failed spike's candidates stay rejected)
        sp = split([r["family"] for r in rows if r["passed"] and (r["stage"] == "a5b" or r["stage"] in g0_met)])
        json.dump(sp, open(d / "split.json", "w"), indent=1)
        lines += ["", f"Split (passing families only): test {len(sp['test'])} (test-only mechanisms: {', '.join(sp['test_only_mechanisms']) or 'none'}), "
                  f"val {len(sp['val'])}, train {len(sp['train'])}. {sp['note']}"]
    (d / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=STAGES)
    ap.add_argument("--extend", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    d = results_dir("a5")
    if a.stage in SPIKES:
        sel = candidates(SEED, SPIKES[a.stage])[:SPIKE]
    elif a.stage == "a5b":
        sel = candidates(SEED, A5B_GEN)[SPIKE : SPIKE + (80 if a.extend else 50)]
    else:
        sel = []
    if sel:
        json.dump([f.describe() for f in sel], open(d / f"{a.stage}_candidates.json", "w"), indent=1)
        run([{"id": f.id, "family": f.id, "stage": a.stage} for f in sel], job, d / f"{a.stage}.jsonl", workers=a.workers, wave=len(sel))
    summarize(d)


if __name__ == "__main__":
    main()
