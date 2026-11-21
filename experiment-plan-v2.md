# Experiment Plan v2

**Status:** v2, 2026-11-22. Implements [`research-plan-v2.md`](research-plan-v2.md) and replaces [`experiment-plan.md`](experiment-plan.md). Values marked *(freeze)* are fixed in the pre-registration (A9) before any LLM or RL run. Experiment IDs are new; where an earlier experiment is reused, its old ID is given.

---

## 0. Conventions

| Item | Setting |
|---|---|
| Budget unit | One verifier call = one proposal evaluated under one law, all years and futures. |
| Default environment | Survey households (enhanced CPS 2024, 50 states, Alaska and rental-income households excluded), 3 tax years, 3 futures, continuous amounts, dated and scenario-contingent moves, federal-income-tax gain. |
| Pools | 40 households for the main comparison (witness at a seeded position, neutral ids); 200 for one robustness arm (C6). |
| Verifier | Cross-check max($10, 2%) *(freeze after A2–A3)*; pre-registered whitelist; `recheck_flagged` on for every search run. |
| Matching | Mutation-attributable gain ≥ $50 and ≥ R of the gain; R = 0.1 primary, 0.5 robustness. |
| Anytime runs | Each search job runs to the largest budget once; recall at smaller budgets is read off the same run. |
| Seeds | 5 per condition × target *(freeze)*. |
| Statistics | Hierarchical bootstrap (families, then seeds), 10,000 resamples; Holm across confirmatory tests. |
| Cost model | Measured: about 2.9 s per verifier call per worker at 3 years × 3 futures (stage 1: 400 calls in ~19 min per job); 6 workers on the current VM (memory-limited). |

---

## Phase A — Build and freeze

### A1. Verifier final settings
- **Do:** switch defaults to the tolerance cross-check, `gain_scope="federal"`, `recheck_flagged=True`; regression-test every known-answer case in both calculators.
- **Exit:** full test suite passes; one batch-consistency test per new move type.

### A2. Noise floor of gains (old E0.1, extended)
- **Question:** how much do the two calculators disagree on the *change* in federal tax, not the tax level?
- **Setup:** 3,000 survey households × 20 random valid proposals each, under current law; record |PE gain − TC gain|.
- **Output:** distribution of gain disagreement (absolute and relative), by move type and income band. This is the H4(b) baseline and the evidence for the tolerance.
- **Decision:** the frozen tolerance is the smallest max($a$, $b$%) with $a$ ∈ {$5, $10, $25} and $b$ ∈ {1, 2, 5}% under which ≤ 1% of random proposals are labelled `code_disagreement` *(freeze)*.
- **Cost:** 60,000 calls ≈ 8 h.

### A3. Tolerance sensitivity sweep
- **Setup:** re-label saved verdicts (no new calculator runs) from A2, the canary search (old E2.6b) and the legitimate-planning suite under tolerances {1, 2, 5, 10}% and the old 50% ratio test.
- **Output:** canary catch rate and false `code_disagreement` rate per tolerance (an ROC-style table).

### A4. Legitimate-planning suite v2 (old E0.6)
- **Add:** HSA contributions, joint vs. separate filing (where separate is genuinely better and allowed), donation bunching across years, Roth conversion in a low-income future.
- **Keep:** existing positives and labelled negatives (sacrifice, benefit cliff, wash sale, NIIT gray gifts).
- **Size:** ≥ 120 positives, ≥ 40 negatives; survey households where possible, archetypes otherwise.
- **Split:** dev/test 50/50 by hash, stratified by family *(freeze)*. Only dev is looked at before A9.

### A5. Interaction-mutation catalog (the main build)
- **Goal:** ≥ 20 families of planted loopholes that need two provisions decoupled together.
- **Generator:**
  1. Catalog of parameters encoded in both calculators, paired by statutory meaning (including the AMT and regular-tax pairs found in F11).
  2. Operators that act on **two** provisions at once: decouple two linked tests (e.g. age test and income test), stack two phase-outs, shift one threshold so it interacts with another, remove a coordination rule between filing statuses.
  3. For each candidate mutation pair, targeted witness search on archetypes (random + greedy restricted to households with the relevant facts, ≤ 5,000 calls), using the known mutation.
- **Gate (per family, both magnitudes):**
  1. Witness valid: flagged under the mutated law; mutation-attributable share ≥ 0.3.
  2. Non-decomposability: exhaustive k−1-move grid on **10 archetypes** (income tercile × {single, married, single parent} + witness) finds no sequence with share ≥ R.
  3. Single-mutation ablation: each mutation alone yields share < R on the witness.
  4. Continuous spot check: 500 random draws of amounts and years around the grid, same test.
  5. Negative control: the reverse direction (making an intended provision more generous) is not flagged.
- **Split:** by mechanism, ≈ 50% train / 20% val / 30% test *(freeze)*; at least 2 mechanisms appear only in test.
- **Output:** family manifest (mutations, witnesses, gate results, rejection reasons). Rejected families are logged, not tuned.
- **Go/no-go G2:** ≥ 20 families pass → H5 confirmatory; else H5 exploratory and H2 runs on what passed (minimum 8 test families; fewer → H2 exploratory).
- **Cost:** ~25k calls (~20 worker-hours) per candidate family, gate-dominated; 60 candidates ≈ 8 days on 6 workers (see the cost table).

### A6. Matching re-validation (old E0.7)
- **Setup:** on the A5 families: perturbed witnesses (other households, extra moves, reordered, split amounts) and cross-family proposals; ground truth = mutation creates ≥ $50 of a positive gain.
- **Output:** precision and recall over R ∈ {0.05, …, 0.9}. **Check:** R = 0.1 keeps precision ≥ 0.95 and recall ≥ 0.95 on interaction families; otherwise R is re-chosen here, before freezing.

### A7. Beam-enumeration baseline
- **Do:** breadth-first enumeration over the discretized grid per household, households visited in random order, depth 1 then 2 then 3, with duplicate pruning.
- **Validate:** on 3 val families, beam finds the witness when given the witness household and budget ≥ its grid size.

### A8. Pilot and power analysis
- **Setup:** val families only. Random, greedy, beam: 3 seeds at 1,000 calls. One frontier LLM, plain and disguised: 3 seeds at 300 calls (needs API keys).
- **Output:** variance of per-family recall and AUC; power for H2 (difference in AUC) and H3 (paired TOST at Δmax = 0.15).
- **Decision:** seeds and budgets *(freeze)*; whether H3 is confirmatory (≥ 80% power at Δ ≤ 0.15) or exploratory.

### A9. Pre-registration freeze
Commit `preregistration.md`: tolerance, R, whitelist, intended/anti-abuse lists, family manifest and splits, legitimate-planning test split, budgets, seeds, conditions, primary tests, power analysis, Δmax, budget cut order, stopping rules. **No test-split data is looked at before this commit.**

---

## Phase B — Verifier validation (H1, H4)

### B1. H1, historical closures (old E1.1)
- **Setup:** both case families under frozen settings; covered and uncovered households from the case panels plus 200 survey households per case.
- **Output per case:** sensitivity, specificity (Clopper–Pearson CIs), post-closure residual by provision, closed provision in post signature (must be 0). Child AMT reported as the known PolicyEngine gap.
- **Decision:** H1 holds for a case if sensitivity ≥ 0.9 and specificity ≥ 0.9 *(freeze)*.

### B2. H1, legitimate planning
- **Setup:** A4 **test split**, frozen settings; whitelist on and off.
- **Decision:** H1 holds if false-positive rate ≤ 5% (one-sided 95% upper bound reported).

### B3. H4(a), canary catch under search (old E2.6b)
- **Setup:** the 7 canaries plus 3 new ones on interaction-type rules; pools of 40; random, greedy, beam at 1,000 calls × 5 seeds; LLM conditions added in Phase C.
- **Output:** exploits found, catch rate (frozen tolerance and the A3 alternatives), per condition.
- **Decision:** H4(a) holds if the pooled federal catch rate ≥ 0.80 (lower CI bound reported).

### B4. H4(b), disagreement tail
- **Setup:** all search runs in B3 and C2; for every flagged proposal, |PE gain − TC gain|.
- **Test:** compare with the A2 random-proposal distribution (one-sided Mann–Whitney on relative disagreement; share above half the tolerance).
- **Decision:** H4(b) holds if flagged proposals sit further into the tail than random ones, per condition. Pre-registered secondary: trend in that share with call index.

---

## Phase C — Search comparison (H2, H3)

### C1. Contamination probes (old E2.2)
- **Disguise check:** each frontier model gets every disguised description and is asked which real provision it is. Any disguise identified by > 1 of 3 models is rewritten **before** C2 (logged).
- **Knowledge probe:** each model lists loopholes for each historical pre-closure law with no search; score per model × case, used as a covariate.

### C2. Main comparison (H2)
- **Targets:** A5 test families (both magnitudes).
- **Conditions:** random, greedy, beam, three frontier LLMs + search (plain text), open base model + search.
- **Budget:** anytime to 1,000 calls *(freeze; 3,000 if compute allows)*; seeds per A8.
- **Primary metric:** AUC of recall vs. log calls on {100, 300, 1,000}.
- **Test:** each LLM vs. the best baseline (chosen on val in A8, pre-registered), hierarchical bootstrap by family; Holm across the three LLMs.
- **Logged:** wanted moves, tokens and dollars per run, wall-clock.

### C3. Cost parity (H2 secondary)
- **Setup:** for each LLM condition, measure dollars and wall-clock per run; give each baseline extra calls worth the same cost (capped at 10× the LLM budget); compare recall at matched cost.

### C4. H3, surface invariance
- **Setup:** same targets, LLM conditions with disguised text, same seeds as C2 (paired).
- **Test:** paired TOST on recall at the primary budget, margin Δmax = 0.15. Confirmatory only if A8 says it is powered.

### C5. Temporal arm
- **Eligibility:** provisions enacted after a model's documented training cutoff **and** encoded identically in both calculators (checked with A2-style agreement). If none qualify, report that and skip.
- **Setup:** planted mutations on those provisions; same protocol as C2.

### C6. Robustness (secondary, one LLM + best baseline)
- R = 0.5 matching; whitelist off; pool of 200; 10-year horizon on a 5-family subset (2024–2033, both calculators' projected law); historical closures as targets.

---

## Phase D — RL (H5)

Starts only after G2 (A5) and B1–B2 pass.

| ID | Experiment | Notes |
|---|---|---|
| D0 | Format and throughput check | Valid-move rate of the base model (< 80% → small format-only SFT on random valid sequences). Verifier throughput for rollouts measured; horizon and futures fixed as in Phase C. |
| D1 | RL with verifier reward | GRPO + LoRA, 3–4B model on the A100 40 GB; train families only; reward = federal gain if all checks pass, small penalty for invalid moves; episode ≤ 4 calls. 2 seeds. |
| D2 | RL with oracle reward | Same, reward = mutation-attributable gain. 1 seed. Upper bound. |
| D3 | Interface control | Same as D1 on current law with no planted mutation (only legitimate planning rewards). Separates "learned the tool" from "learned to find loopholes". |
| D4 | Best-of-N control | Base model at matched total inference compute. |
| D5 | Evaluation | D1–D4 on val families during training; final on test families (held-out mechanisms) and historical cases, all **without** the oracle, C2 protocol. |
| D6 | Monitoring | Canary hits, `code_disagreement` and `inconsistent` rates per eval; stop a run if canary hits rise over 3 consecutive evals. |

**Decision (H5):** D1 beats the base model, D3 and D4 on held-out-mechanism recall (bootstrap by family). Confirmatory only if G2 passed; the D2–D1 gap is reported as the oracle shift.

**Cost:** ~3 GPU-days per run × 5 runs ≈ 15 GPU-days; verifier throughput (CPU) is the likely bottleneck, measured in D0.

---

## Phase E — Review and disclosure

| ID | Experiment | Notes |
|---|---|---|
| E1 | Judge calibration | 3 judges from different providers, none from the searching model's family, blind to source. Calibration set: historical loopholes (+), legitimate planning (−), benefit cliffs (own class), canary exploits (− "not the law"). Output: accuracy per judge, Fleiss' κ, panel vote threshold. |
| E2 | Borderline audit | Every candidate with disagreement > half the tolerance, checked against the statute by the team. |
| E3 | Expert review | ~40 unique strategies (deduplicated by moves and mechanism across C2–C6 and D5), blinded, mixed with 10 decoys of known label. Expert 1 rates all; expert 2 rates a 30% overlap → Cohen's κ; disagreements adjudicated. Output: verifier error rate against adjudicated labels. |
| E4 | Disclosure | Any current-law candidate that survives E1–E3 and has no match in known sources is shared with the relevant authority before publication, described at provision level. |

---

## Gates and order

```
A1 ─ A2 ─ A3 ─┐
A4 ───────────┤
A5 ─ A6 ──────┼─ A7 ─ A8 ─ A9 (freeze)
              │
              └─ G2: ≥ 20 families?  yes → H5 confirmatory / no → exploratory
A9 ─ B1, B2 (H1) ─ B3, B4 (H4) ─ C1 ─ C2 ─ C3, C4, C5, C6 ─ D0…D6 ─ E1…E4
```

| Gate | Condition | If it fails |
|---|---|---|
| G1 | B1–B2: H1 holds on both case families and the test split | Fix the verifier, rerun B1–B2 on fresh households; Phase C waits. |
| G2 | A5: ≥ 20 families | H5 exploratory; H2 needs ≥ 8 test families or becomes exploratory. |
| G3 | A8: H3 powered at Δ ≤ 0.15 | H3 exploratory (confidence interval only). |
| G4 | D0: valid-move rate ≥ 80% after format SFT | Report the open-model arm as infeasible at this size. |

---

## Compute and cost estimates

| Block | Verifier calls | Worker-hours (≈2.9 s/call) | Wall-clock (6 workers) | Other |
|---|---|---|---|---|
| A2 | 60k | 48 | 8 h | |
| A5 (60 candidates) | ~1.5M | ~1,200 | ~8 days | biggest CPU cost |
| A8 pilot | ~100k | 80 | 14 h | LLM pilot needs keys |
| B1–B4 | ~250k | 200 | 1.5 days | |
| C2 (7 conditions × ~12 test targets × 5 seeds × 1,000 calls) | 420k | 340 | 2.5 days | |
| C3–C6 | ~400k | 320 | 2.5 days | |
| D | rollouts | (CPU-bound) | ~15 GPU-days | |

LLM spend (order of magnitude, one frontier model at $4 / $20 per M input/output tokens, 10 proposals per call, ~15k input + 2k output tokens per call): ≈ $0.10 per call → ~$10 per 1,000-call run. C2 + C4 for three models ≈ 3 × 2 × 12 × 5 runs ≈ 360 runs ≈ $3.6k before prompt caching. Prices for the other two providers to be confirmed.

**Pre-registered cut order** if compute or budget runs short: (1) seeds 5 → 3; (2) the 3,000-call budget is never run; (3) C6 reduced to R = 0.5 and whitelist-off relabelling only (no new runs); (4) 10-year sensitivity dropped. A larger CPU machine for A5 and C is the first thing to request; it is cheaper than any cut.

---

## Stopping rules and integrity

- Test-split data (legitimate-planning test half, A5 test families) is not opened before A9.
- Any change to the verifier after A9 invalidates affected results; they are rerun, and the change and reason are logged in the pre-registration's amendment section.
- A bug found after A9 that changes labels (as F8, F12 did) triggers: fix, regression test, rerun of every affected experiment, and an entry in `results/FINDINGS.md` marking old outputs invalid.
- Families flagged decomposable during search stay in the primary analysis; excluding them is secondary (research plan §6.2).

## Outputs

Each experiment writes `results/<phase>/<id>/` with `summary.md`, `summary.json` (including the git commit and frozen-settings hash) and raw records; summaries are committed, large raw files stay on the VM under `~/lv-results`.
