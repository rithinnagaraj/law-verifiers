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
| Models | Search LLMs (C2, three providers, spanning the capability range): **Gemini 4 Carbon** (Google; ceiling, Google's most capable reasoning model), **GPT-6.2 Sol** (OpenAI; mid-priced), **DeepSeek V4.1 Flash** (DeepSeek; low-cost, open weights). Open-weights judge: **GLM-5.3** (Z.AI). RL policy: a 3–4B open-weights instruct model chosen in D0. Exact version IDs are recorded in A9 and never replaced by aliases; each call logs the model ID returned by the API. |
| Cost model | Measured: about 2.9 s per verifier call per worker at 3 years × 3 futures (stage 1: 400 calls in ~19 min per job); 6 workers on the current VM (memory-limited); 24 on the planned A–C machine (see "Compute and cost estimates"). |

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
- **Split (by family, then mechanism; filled in this order):** test first (≥ 8 families, ~40%), then val (≥ 3), then train (the rest) *(freeze)*. At least 2 mechanisms appear only in test. With exactly 20 families: 8 test / 3 val / 9 train. The two magnitudes of a family stay in the same split and count as one unit in every bootstrap.
- **Output:** family manifest (mutations, witnesses, gate results, rejection reasons). Rejected families are logged, not tuned.
- **Staging:** A5 runs in two parts so that a weak generator is caught before the full catalog is spent.
  - **A5a, spike:** 10 candidate families through the full gate above (all five checks, 10 archetypes, both magnitudes). Runs right after A1–A3, before A4 and A7. ~250k calls: ~8 h on 24 workers (~1.4 days on 6).
  - **Gate G0:** ≥ 3 of 10 pass → A4, A5b and A7 proceed with the operators unchanged; the 10 spike candidates count toward the 60 (90). Fewer than 3 → the failure is logged (per-check rejection counts), the operators are revised, and a new 10-candidate spike runs with the revised operators; candidates from a failed spike stay rejected and are not re-gated. At most 2 revisions. If the third spike still has < 3 passes: with 2 of 10, A5b proceeds with the best operator set (projected ~12 of 60, enough for H2's 8 test + 3 val families; H5 likely exploratory); with ≤ 1 of 10, the catalog stops, the build failure is reported as a finding, and H2 and H5 become exploratory on whatever families passed. Why 3 of 10: at a 30% pass rate, 60 candidates give ~18 families and the 90-candidate extension ~27, so G2 stays reachable; below that it does not.
  - **A5b, rest of the catalog:** 50 more candidates (80 if extended), same gate, same operators as the last passing spike.
- **Go/no-go G2:** ≥ 20 families pass → H5 confirmatory (≥ 9 train families). Fewer → H5 exploratory; H2 still gets the first 8 passing families as test (fewer than 8 → H2 exploratory). If the pass rate after 40 candidates (A5a included) projects fewer than 20 from 60, A5b extends to 90 candidates in total before giving up on G2 (≈ +1 day on 24 workers, ≈ +4 on 6).
- **Cost:** ~25k calls (~20 worker-hours) per candidate family, gate-dominated; 60 candidates ≈ 2 days on 24 workers (≈ 8 on 6), see the cost table.

### A6. Matching re-validation (old E0.7)
- **Setup:** on the A5 families: perturbed witnesses (other households, extra moves, reordered, split amounts) and cross-family proposals; ground truth = mutation creates ≥ $50 of a positive gain.
- **Output:** precision and recall over R ∈ {0.05, …, 0.9}. **Check:** R = 0.1 keeps precision ≥ 0.95 and recall ≥ 0.95 on interaction families; otherwise R is re-chosen here, before freezing.

### A7. Beam-enumeration baseline
- **Do:** breadth-first enumeration over the discretized grid per household, households visited in random order, depth 1 then 2 then 3, with duplicate pruning.
- **Validate:** on 3 val families, beam finds the witness when given the witness household and budget ≥ its grid size.

### A8. Pilot and power analysis
- **Setup:** a pilot pool of the 3 val families plus 6 train families (train families are used here for variance only, before any RL; no test family is touched). Random, greedy, beam: 3 seeds at 1,000 calls. GPT-6.2 Sol, plain and disguised: 3 seeds at 300 calls (needs API keys). Token check: all three C2 models, plain, 1 seed × 300 calls on the 3 val families, to measure real input, output and thinking tokens per call before budgets are frozen.
- **Output:** variance of per-family recall and AUC; power for H2 (difference in AUC) and H3 (paired TOST at Δmax = 0.15).
- **Decision:** seeds and budgets *(freeze)*; whether H3 is confirmatory (≥ 80% power at Δ ≤ 0.15) or exploratory.

### A8b. Disguise check (moved from C1)
- **Setup:** before A9, each C2 model gets every disguised description (all splits) and is asked which real provision it describes. No search runs and no verifier results are produced, so no outcome data is seen.
- **Rule:** a disguise identified by > 1 of the 3 models is rewritten and re-checked; all rewrites are logged and frozen in A9. No disguise text changes after A9.

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

### C1. Knowledge probe (old E2.2)
- Each model lists loopholes for each historical pre-closure law with no search; score per model × case, used as a covariate. (The disguise check now runs before the freeze, A8b.)

### C2. Main comparison (H2)
- **Targets:** A5 test families (≥ 8), both magnitudes (≥ 16 targets); the unit of analysis is the family.
- **Conditions:** random, greedy, beam, three LLMs + search (Gemini 4 Carbon, GPT-6.2 Sol, DeepSeek V4.1 Flash; plain text), open base model + search. Secondary analysis: recall against model capability tier (ceiling, mid, low-cost).
- **Budget:** anytime to 1,000 calls *(freeze; 3,000 if compute allows)*; seeds per A8.
- **Primary metric:** AUC of recall vs. log calls on {100, 300, 1,000}.
- **Test:** each LLM vs. the best baseline (chosen on the A8 pilot pool, pre-registered), hierarchical bootstrap by family; Holm across the three LLMs.
- **Logged:** wanted moves, tokens and dollars per run, wall-clock.

### C3. Matched cost, capped at 10× calls (H2 secondary)
- **Setup:** for each LLM condition, measure dollars and wall-clock per run; give each baseline extra calls worth the same cost, **capped at 10× the LLM's call budget**; compare recall at that budget. Where the cap binds, the result is reported as "capped", not as true cost parity.

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

Starts only after G2 (A5), B1–B2 and the D0 throughput gate pass. The GPU is not used for Phase D until D0 passes; it is detached or the VM stopped while idle.

**How the policy is used.** In training and evaluation alike, the model is the *proposer inside the C2 search scaffold*. One episode = one scaffold step: the model sees the rule text, the pool summary and the scaffold's archive (top 15 and last 15 results), proposes a sequence, and may refine it up to 3 times on verifier feedback (≤ 4 calls). Training episodes are started from archives sampled from earlier runs on the **same training family only** (never val or test), generated by the base open model and the random and greedy baselines (no frontier-LLM trajectories, so RL is not warm-started by frontier models); later in training, the policy's own earlier runs are added. The policy thus learns to condition on search history. A 1,000-call evaluation is 250 consecutive episodes sharing one archive, exactly as for the frontier LLMs in C2.

| ID | Experiment | Notes |
|---|---|---|
| D0 | Format and throughput gate | Valid-move rate of the base model (< 80% → small format-only SFT on random valid sequences). Verifier throughput: GRPO at group 8 × batch 16 × ≤ 4 calls needs ~512 calls per step. **Gate: ≥ 20 calls/s sustained** (~25 s per step). At ~2.9 s per call per worker that needs **≥ 60 verifier workers** (~9 GB each, ≈ 540 GB RAM, one or more high-memory CPU nodes) feeding an asynchronous rollout pool, decoupled from gradient updates. Fallback: ≥ 10 calls/s (≥ 30 workers) with batch 8 (~256 calls, ~26 s per step), recorded as a deviation. The current VM (~2 calls/s) passes neither. |
| D1 | RL with verifier reward | GRPO + LoRA, 3–4B model on the A100 40 GB; train families only; reward = federal gain if every check passes (whitelist on), small penalty for invalid moves. 2 seeds. |
| D2 | RL with oracle reward | Same, reward = mutation-attributable gain. 1 seed. Upper bound. |
| D3 | Interface control | Same scaffold, current law with no planted mutation, reward = federal gain with reality and cross-check but **whitelist off**, so ordinary tax minimization is rewarded. Its reward differs from D1's by design: it measures how much a generic "lower the tax bill" skill alone transfers to finding planted loopholes. |
| D4 | Best-of-N control | Base model at matched total inference compute. |
| D5 | Evaluation | D1–D4 on val families during training; final on test families (held-out mechanisms) and historical cases, all **without** the oracle, C2 protocol (250 episodes per 1,000-call run). |
| D6 | Monitoring | Canary hits, `code_disagreement` and `inconsistent` rates per eval; stop a run if canary hits rise over 3 consecutive evals. |

**Decision (H5):** D1 beats the base model, D3 and D4 on held-out-mechanism recall (bootstrap by family). Confirmatory only if G2 passed; the D2–D1 gap is reported as the oracle shift.

**Cost:** ~3 GPU-days per run × 5 runs ≈ 15 GPU-days, *after* D0 passes; plus the verifier node (n2-highmem-80, ≥ 60 workers) for the same period; machines are listed under "Compute and cost estimates". Without the node, Phase D does not start.

---

## Phase E — Review and disclosure

| ID | Experiment | Notes |
|---|---|---|
| E1 | Judge calibration | **Roles:** the three C2 models come from Google (Gemini 4 Carbon), OpenAI (GPT-6.2 Sol) and DeepSeek (V4.1 Flash). Each candidate is judged by a 3-member panel: the two C2 providers that did *not* produce it, plus GLM-5.3 (open weights, not a C2 model). Baseline and RL candidates get Gemini 4 Carbon + GPT-6.2 Sol + GLM-5.3. The exclusion is per candidate, so no provider judges its own model's output. Judges are blind to the source. Calibration set: historical loopholes (+), legitimate planning (−), benefit cliffs (own class), canary exploits (− "not the law"). Output: accuracy per judge, Fleiss' κ, panel vote threshold. |
| E2 | Borderline audit | Every candidate with disagreement > half the tolerance, checked against the statute by the team. |
| E3 | Expert review | ~40 unique strategies (deduplicated by moves and mechanism across C2–C6 and D5), blinded, mixed with 10 decoys of known label. Expert 1 rates all; expert 2 rates a 30% overlap → Cohen's κ; disagreements adjudicated. Output: verifier error rate against adjudicated labels. |
| E4 | Disclosure | Any current-law candidate that survives E1–E3 and has no match in known sources is shared with the relevant authority before publication, described at provision level. |

---

## Gates and order

```
A1 ─ A2 ─ A3 ─ A5a ─ G0: ≥ 3 of 10 pass?
                      no  → log, revise operators, new spike (≤ 2 revisions)
                      yes → A4, A5b ─ A6 ─ A7 ─ A8 ─ A8b ─ A9 (freeze)
                                │
                                └─ G2: ≥ 20 families?  yes → H5 confirmatory / no → exploratory
(A4 and A5b are independent but share the machine, so they run one after the other.)
A9 ─ B1, B2 (H1) ─ B3, B4 (H4) ─ C1 ─ C2 ─ C3, C4, C5, C6 ─ D0…D6 ─ E1…E4
```

| Gate | Condition | If it fails |
|---|---|---|
| G0 | A5a: ≥ 3 of 10 spike candidates pass the full gate | Log, revise the mutation operators, rerun a 10-candidate spike (≤ 2 revisions); then the fallback in A5 (2 of 10 → continue for H2; ≤ 1 → stop the catalog). |
| G1 | B1–B2: H1 holds on both case families and the test split | Fix the verifier, rerun B1–B2 on fresh households; Phase C waits. |
| G2 | A5: ≥ 20 families | H5 exploratory; H2 needs ≥ 8 test families or becomes exploratory. |
| G3 | A8: H3 powered at Δ ≤ 0.15 | H3 exploratory (confidence interval only). |
| G4 | D0: valid-move rate ≥ 80% after format SFT | Report the open-model arm as infeasible at this size. |
| G5 | D0: verifier throughput ≥ 20 calls/s (≥ 60 workers), or ≥ 10 calls/s with the halved batch | Phase D waits for the CPU nodes; the GPU stays detached. |

---

## Compute and cost estimates

### Machines

| Phase | Machine (GCP) | Workers | Notes |
|---|---|---|---|
| A–C | **n2-highmem-32** (32 vCPU, 256 GB), no GPU, cloned from the current VM's boot disk | 24 (~216 GB; `vm_run.sh` MemoryMax and `TAXRED_MEM_GB` raised to ~235 GB) | ~8 calls/s, ~4× the current VM. The A100 VM stays stopped. Faster option: n2-highmem-48 (384 GB, ~38 workers). |
| D, trainer | current **a2-highgpu-1g** (1× A100 40 GB, 12 vCPU, 85 GB) | — | GRPO + LoRA and generation only. D0 checks that group 8 × batch 16 at ~15k-token prompts fits in 40 GB; if not, a2-ultragpu-1g (A100 80 GB). |
| D, verifier | **n2-highmem-80** (80 vCPU, 640 GB), same zone and network as the trainer | 64 (~576 GB) | ~22 calls/s, passes G5. If the per-worker rate drops under load: n2-highmem-96 (768 GB, ~80 workers). Fallback gate (≥ 10 calls/s): n2-highmem-48. Needs 80 N2 vCPUs of regional quota; the trainer–verifier rollout pool is built in D0. |

### Verifier compute

| Block | Verifier calls | Worker-hours (≈2.9 s/call) | Wall-clock, 24 workers (6 on the current VM) | Other |
|---|---|---|---|---|
| A2 | 60k | 48 | 2 h (8 h) | |
| A5a spike (10 candidates; each revision adds the same) | ~250k | ~200 | ~8 h (~1.4 days) | G0 |
| A5b (50 candidates; 80 if extended) | ~1.25M (~2M) | ~1,000 (~1,600) | ~1.7 days (~2.8 days) (current VM: ~7 (~11) days) | biggest CPU cost |
| A8 pilot (9 families × 2 magnitudes) | ~200k | 160 | 7 h (~1.1 days) | LLM pilot needs keys |
| B1–B4 | ~250k | 200 | 8 h (1.5 days) | |
| C2 (7 conditions × 16 test targets × 5 seeds × 1,000 calls) | 560k | 450 | 19 h (~3 days) | |
| C3–C6 | ~400k | 320 | 13 h (2.5 days) | |
| **A–C total** | ~3M | ~2,400 | **~4–5 days** (~17–22 days) | LLM runs are further limited by API latency |
| D | rollouts | on the verifier node | ~15 GPU-days (≈ 3 weeks for both D machines) | stop the verifier node whenever training is not running |

### LLM spend

Assumptions: one LLM call proposes 10 sequences with ~15k input + ~2k output tokens, so a 1,000-verifier-call run is ~100 LLM calls. Standard prices checked 2026-11-22, USD per M tokens (input / output):

| Model | Price | Cost per 1,000-call run | Price notes |
|---|---|---|---|
| Gemini 4 Carbon (`gemini-4-carbon`) | 4 / 20 from 2026-12-01 (2 / 10 before) | ~$10 | All C2 runs fall after the step-up. |
| GPT-6.2 Sol (`gpt-6.2-sol`) | 2 / 10 | ~$5 | |
| DeepSeek V4.1 Flash (`deepseek-flash` → V4.1-Flash-1017) | 0.30 / 1.20 peak; half off-peak | ~$0.35–0.70 | Peak: 01–04 and 06–10 UTC on weekdays; its runs are scheduled off-peak. |
| GLM-5.3 (judge only) | ~1.40 / 4.40 | — | |

| Item | Verifier calls driven by an LLM | Cost |
|---|---|---|
| A8 pilot (GPT-6.2 Sol, plain + disguised, 9 families × 2 magnitudes, 3 seeds × 300) + token check (3 models) | ~32k + ~16k | ~$0.25k |
| A8b disguise check, C1 knowledge probe | single prompts | < $0.05k |
| B3 canaries with LLM conditions (3 models, 10 canaries, 5 seeds) | 150k | ~$0.8k |
| C2 + C4 (3 models × plain/disguised × 16 targets × 5 seeds) | 480k | ~$2.5k |
| C5 temporal arm (only if eligible provisions exist) | ≤ 60k | $0–0.3k |
| C6 robustness (GPT-6.2 Sol, fixed in advance: pool of 200, 10-year horizon, historical targets) | ~165k | ~$0.8–1k |
| E1 judge panel | — | ~$0.1–0.3k |
| Prompt development and smoke tests (mostly on DeepSeek V4.1 Flash) | — | ~$0.5k |
| **Total** | | **~$5.5k** before caching |

All three models bill thinking as output; if thinking adds 50% to output tokens, the total is ~$7–8k. Caching the fixed prompt prefix saves ~10–30%. **Planning figure: ~$5.5k (range $4–8k);** the A8 token check replaces these assumptions before A9. Gemini 4 Carbon is ~60% of the spend; largest single saving: B3 with GPT-6.2 Sol only (~$0.5k). Prompts are developed on val with all three models, not tuned on one.

**Pre-registered cut order** if compute or budget runs short: (1) seeds 5 → 3; (2) the 3,000-call budget is never run; (3) C6 reduced to R = 0.5 and whitelist-off relabelling only (no new runs); (4) 10-year sensitivity dropped; (5) B3 LLM conditions reduced to one model. Moving A–C to the larger CPU machine above comes before any cut.

---

## Stopping rules and integrity

- Test-split data (legitimate-planning test half, A5 test families) is not opened before A9.
- Any change to the verifier after A9 invalidates affected results; they are rerun, and the change and reason are logged in the pre-registration's amendment section.
- A bug found after A9 that changes labels (as F8, F12 did) triggers: fix, regression test, rerun of every affected experiment, and an entry in `results/FINDINGS.md` marking old outputs invalid.
- Families flagged decomposable during search stay in the primary analysis; excluding them is secondary (research plan §6.2).

## Outputs

Each experiment writes `results/<phase>/<id>/` with `summary.md`, `summary.json` (including the git commit and frozen-settings hash) and raw records; summaries are committed, large raw files stay on the VM under `~/lv-results`.
