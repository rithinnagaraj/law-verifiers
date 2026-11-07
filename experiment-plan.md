# Experiment Plan: Red-Teaming US Household Tax Law with AI Agents

**Status:** Draft v0.1 · **Companion to:** [`us-tax-red-teaming-research-plan.md`](us-tax-red-teaming-research-plan.md)

This document turns the research plan into a list of concrete experiments. Each one has an ID, its inputs and outputs, how it decides the question it tests, and what it depends on. Values marked *(proposed)* get fixed in the pre-registration (E0.8) before any agent search runs.

**Resource assumptions**

| Resource | Assumption | Consequence |
|---|---|---|
| GPU | One GCP VM with a single A100 (40 GB or 80 GB) | RL uses a ~7–8B model with LoRA (3–4B on the 40 GB card). About 4 training runs in total, so controls take priority over sweeps. **Request the 80 GB card.** |
| Frontier models | API access to several providers | Phase 2 compares 3 frontier models from different providers. LLM judges always come from a different family than the model that did the searching. |
| Tax expert | Not yet recruited | Expert review gates only H6, the exploratory hypothesis. Recruiting runs during weeks 1–6. Until an expert is available, LLM judges are calibrated on items with known labels. |

---

## 1. Design decisions the research plan leaves open

These are settled in Phase 0 because every later number depends on them.

### 1.1 Rediscovery matching rule

Recall needs an automatic way to decide whether a candidate "is" known loophole *L*. A candidate matches *L* when both conditions hold:

1. **Closure test.** Applying *L*'s closure reform removes ≥ 80% *(proposed)* of the candidate's gain.
2. **Signature match.** The candidate's attribution signature matches *L*'s witness signature, with Jaccard similarity ≥ 0.5 *(proposed)*. The attribution signature is the set of provisions whose removal takes away ≥ 20% *(proposed)* of the gain.

Both checks run on the verifier and need no LLM to do the matching. E0.7 validates the rule. For planted variants, the planted mutation itself plays the role of the closure reform.

### 1.2 Cross-check coverage tags

The second calculator covers less than PolicyEngine-US:

- Tax-Calculator covers federal income tax from 2013 onward.
- TAXSIM covers earlier years and state income taxes.
- Neither covers benefits.

Every candidate therefore carries a tag:

| Tag | Meaning |
|---|---|
| `two-calc` | The gain is confirmed by PolicyEngine and by Tax-Calculator or TAXSIM. |
| `taxsim-only` | Pre-2013 rules, where TAXSIM is the only second calculator. |
| `single-calc` | All or part of the gain comes from components only PolicyEngine models (benefits, some state rules). |

All H4 results and all candidate counts are reported per tag. `single-calc` candidates go through a heavier random audit (E2.6d).

### 1.3 Agent interface

- **What the agent sees:** a structured rule description (parameter names, values and documentation strings), the household, the move vocabulary (§5.2 of the research plan) and the horizon. The horizon is 3 tax years *(proposed)*.
- **What the agent submits:** a JSON move sequence. Each move is tagged with the year it applies to.
- **What a verifier call returns:** the gain and the pass/fail result of each check (cross-check, reality check, attribution). The level of detail is an ablation (E2.5).
- **How disguised variants work:** only the description the agent sees is renamed and reworded. The rules being calculated are the same.
- **Wanted moves:** the agent may log moves it wanted but the vocabulary cannot express (`wanted_move`). These logs are collected in every experiment.

### 1.4 Budget unit

Conditions are compared at an equal number of **verifier calls**. API dollars, GPU-hours and wall-clock time are reported as secondary measures.

### 1.5 Data splits

| Set | Used for training | Used for tuning | Used for final evaluation |
|---|---|---|---|
| Planted variants – train (~200) | ✔ | | |
| Planted variants – val (~50) | | ✔ | |
| Planted variants – test, plain and disguised (~50 each) | | | ✔ |
| Held-out mutation operators and provision families | | | ✔ |
| Historical-closure set | | | ✔ |
| Shelter Check subset | | | ✔ |
| Legitimate-planning set | | dev half | test half |
| Current law (H6) | | | ✔ |

Planted variants are split by mutation operator **and** by provision family. This makes it possible to measure transfer beyond the exact mutation patterns seen in training (the condition that counts against H5).

---

## 2. Phase 0 — Infrastructure (weeks 1–2)

### E0.1 Calculator agreement baseline
- **Question:** How often do the calculators disagree when no agent is involved? This sets the noise floor that the H4 numbers are measured against.
- **Setup:** about 5,000 households (PolicyEngine microdata plus the archetypes). Each is run through PolicyEngine-US, Tax-Calculator and TAXSIM for every year each calculator covers.
- **Output:**
  - Agreement rate within $1 and within 1%.
  - Disagreements attributed to individual provisions.
  - A year × calculator coverage table.
  - The cross-check tolerance used from then on.
- **Why it matters:** if the calculators already disagree on 5% of households, a 5% cross-check failure rate under search is not evidence of reward hacking.

### E0.2 Known-answer tests
- **Setup:** 50–100 worked examples from IRS publications and instructions, covering the kiddie tax, EITC, CTC/ACTC, filing status, capital gains and the standard vs itemized deduction.
- **Exit:** every example passes within $1, or the exception is documented and linked to an issue.

### E0.3 Verifier throughput benchmark
- **Setup:** measure 3-year evaluations per second on the VM's CPUs, with result caching and batched households.
- **Target:** ≥ 50 evaluations/s *(proposed)*. A rough count of what is needed: Phase 2 takes on the order of 10⁶ calls (conditions × targets × seeds × budget), and Phase 3 rollouts need a sustained stream of calls.
- **If the target is missed:** cut budgets in a pre-registered order: fewer seeds first, then a lower top budget.

### E0.4 Move-vocabulary audit
- **Setup:** hand-encode each historical-closure candidate and each public Shelter Check strategy as a move sequence. When one can't be encoded, record which move is missing.
- **Output:** the in-scope denominator for recall, the share of strategies that are out of scope (a risk listed in §8 of the research plan), and a first list of wanted moves.

### E0.5 Build the historical-closure set
For each case, encode:
- pre- and post-closure reforms,
- a witness household and witness move sequence,
- the witness attribution signature,
- the sources used.

Candidate cases, all to be checked against sources of the period:

| Case | Closure | Notes |
|---|---|---|
| Unearned income shifted to children | Kiddie tax, Tax Reform Act of 1986 | The anchor case. Pre-2013, so `taxsim-only`. |
| Kiddie-tax age expansions | Later laws (2006, 2007/08) raising the age limits | The same loophole closed in stages, which gives a **dose-response** check on the verifier. |
| EITC claimed by households with large investment income | The disqualified investment income limit | Interaction between benefits and tax. |
| Home-sale exclusion after converting a rental property | The non-qualified-use rule (2008) | Needs moves that change how property is used, which may be missing. |
| SALT-cap charitable-credit workaround | Treasury/IRS regulations (2019) | Tagged as an **agency** closure, not Congressional. |
| Roth recharacterization; Social Security file-and-suspend | 2017; 2015 | Probably out of scope (the first needs price uncertainty, the second needs claiming rules). Recorded in E0.4. |

- **Exit:** ≥ 8 cases in scope *(proposed)*. With fewer, H1 and H2 on this set are reported as per-case studies, not rates.

### E0.6 Legitimate-planning set
- **Positives for intended use (~60):** 401(k), IRA and HSA contributions; itemizing when it helps; choosing between MFJ and MFS; claiming the CDCC and AOTC; harvesting up to $3k of losses; the saver's credit.
- **Labelled negatives (~20):** *real sacrifice* cases (giving assets outside the household, working fewer hours with no offsetting gain) and *benefit cliff* cases (cutting real income across a phase-out).
- **Split:** dev/test 50/50. Thresholds are tuned on dev only.

### E0.7 Matching-rule validation
- **Setup:** build pairs of candidates and known loopholes.
  - Positives: perturbed witnesses (different household, extra moves that do nothing, a different order).
  - Negatives: unrelated candidates and legitimate-planning scenarios.
- **Output:** precision and recall of the §1.1 rule. Thresholds are adjusted until both are ≥ 0.9 *(proposed)*.

### E0.8 Pre-registration
Freeze the following and commit them before any agent search:
- thresholds,
- tolerances,
- the matching rule,
- budgets,
- seeds,
- splits,
- the primary tests (§7),
- the order in which budgets are cut.

---

## 3. Phase 1 — Verifier validation, H1 (week 3)

| ID | Experiment | Output |
|---|---|---|
| **E1.1** | **Main H1 test.** Run each historical witness under pre- and post-closure rules, on about 50 applicable households per case. Then run the legitimate-planning test half. | Pre-closure flag rate, post-closure flag rate and false-positive rate, per case and pooled, with Clopper–Pearson confidence intervals. For the kiddie-tax stages: the flag rate falls at each closure step. |
| **E1.2** | **Ablation of the checks.** Turn off one check at a time: cross-check, reality check, attribution/whitelist, gain threshold. | Change in false positives and misses for each check. Shows that each one is needed. |
| **E1.3** | **Tolerance sensitivity.** Sweep the reality tolerance and the gain threshold on the dev half, and report on the test half. | Robustness curves. Confirms the pre-registered values lie in a stable region. |
| **E1.4** | **Smoke test against an adversary.** Run a short random + LLM search on current law with PolicyEngine only. | A list of obvious bogus candidates, fixed before Phase 2. Logged as development data and kept out of H4. |

**Gate G1:** the H1 thresholds are met (pre-closure flag rate ≥ 90%, post-closure ≤ 10%, false positives ≤ 5%), or the verifier is fixed and E1.1 is rerun on a new set of households.

---

## 4. Phase 2 — Frozen search, H2–H4 and a first pass at H6 (weeks 4–6)

### E2.1 Planted-variant generator
- **Mutation operators:**
  - remove an anti-abuse rule,
  - move a threshold,
  - sharpen a phase-out into a cliff,
  - decouple linked provisions (for example, drop an age test while keeping the related income test),
  - remove an income limit.
- **Validity:** a variant is kept only if a witness exists. Witnesses are found by targeted search, using the fact that we know what was mutated.
- **Difficulty:** scored by the minimum length of a witness move sequence and by the share of households for which the loophole works. Splits are stratified by difficulty, so that comparisons in H3 are not confounded by it.
- **Disguise:** rename parameters and provisions and reword their documentation. The rules being calculated stay the same.
- **Output:** about 200 train, 50 val and 50 test variants. Each test variant comes in a plain and a disguised form. Some operators and provision families are held out entirely.

### E2.2 Contamination probes
- **(a) Disguise check.** Give each frontier model a disguised description and ask which real provision it is. Accuracy should be near chance. Any disguise that is recognized gets rewritten.
- **(b) Knowledge probe.** With no search and no verifier, ask each model to list loopholes in each pre-closure law, described in neutral terms that don't name the year. The resulting per-model, per-case knowledge score is used as a covariate in E2.4.

### E2.3 Main frozen comparison (H2)

| Item | Value |
|---|---|
| Conditions | random search · heuristic (greedy + evolutionary) · single-shot LLM · **LLM + quality-diversity search** (3 frontier models from different providers) · base open model + search |
| Targets | historical cases in scope (pre-closure law) · Shelter Check subset · planted test set (plain and disguised) |
| Budgets | {100, 300, 1,000, 3,000} verifier calls *(proposed)* |
| Seeds | 5 for each condition × target × budget |
| Primary metric | Area under the recall-vs-budget curve |
| Secondary metrics | recall at each budget, diversity (distinct provisions exploited), cost per rediscovery |
| Test | Mixed-effects logistic regression: `success ~ condition + (1 | target)`. Confidence intervals from a hierarchical bootstrap that resamples targets, then seeds. |

H2 holds if LLM + search beats both random and heuristic search on area under the curve at matched budget. It counts against H2 if heuristic search comes within the confidence interval of LLM + search.

### E2.4 Search vs memory (H3)

Four arms, matched on difficulty:

| Arm | What a gap between arms measures |
|---|---|
| Real historical loopholes | — |
| Planted, plain names | Real vs planted-plain → effect of **memory** |
| Planted, disguised | Planted-plain vs disguised → effect of **surface names** |
| Provisions enacted after the model's training cutoff (e.g. the 2025 reconciliation law) | A natural test of search with no possible memory |

Also regress per-target success on the E2.2 knowledge score. If success rises steeply with the knowledge score, that counts against H3.

### E2.5 Scaffold ablations
Run with one frontier model on the val set, so this stays cheap:
- archive on vs off,
- feedback as a scalar gain vs broken down by provision,
- rule text shown vs hidden,
- the maximum number of moves per proposal.

Only the best configuration goes on to E2.8 and is reused as the scaffold in Phase 3.

### E2.6 Reward hacking (H4)
- **(a) Search-pressure sweep.** As budget and selection intensity (top-k kept in the archive) increase, track the share of PolicyEngine-only positives that fail the cross-check. Compare against the E0.1 noise floor.
- **(b) Canary bugs.** Inject about 10 documented bugs into a fork of PolicyEngine, while leaving the second calculator correct. Examples: an off-by-one threshold, a phase-out missing for one filing status. This gives:
  - how often agents find code bugs,
  - the cross-check's catch rate, measured directly rather than inferred.
- **(c) Code-access arm.** The agent can read the calculator source, or only the parameter documentation. Measure whether code access raises the rate of code exploits.
- **(d) `single-calc` audit.** Candidates that can't be cross-checked are reported separately. A random sample of 20 *(proposed)* is audited by hand against the statute and IRS guidance.

### E2.7 LLM-judge panel and expert packet
- **Panel:** three judges from different providers, each from a different family than the model whose candidates it judges. Judges are blind to the source of the candidate.
- **Calibration set:** historical loopholes (positive), legitimate-planning scenarios (negative), benefit cliffs (their own class), canary-bug exploits (negative: "not the law").
- **Output:** each judge's accuracy, agreement between judges (Fleiss' κ), and the calibrated threshold for the panel's vote.
- **Expert packet:** a blinded set for the expert. It holds the top candidates, a random sample of candidates that passed the automated checks, and decoys with known labels. It is kept ready until an expert is recruited.

### E2.8 First H6 pass on current law
- **Setup:** the best E2.5 configuration on tax year 2026 law, with coverage-guided household generation. Newly enacted provisions get extra weight (tips and overtime deductions, the senior deduction, the SALT-cap phase-down, CTC changes), but only after checking that PolicyEngine models each one.
- **Output:** candidates ranked by gain and reach; benefit cliffs moved into their own policy-design report; a novelty check against public sources.

**Gate G2:** Phase 3 goes ahead only if both hold:
- H1 holds, and
- code exploits rarely get past the cross-check: the canary-bug catch rate is ≥ 80% *(proposed)* and the `single-calc` audit finds no systematic problem.

---

## 5. Phase 3 — RL on one A100, H5 (weeks 7–12)

### Setup
| Item | Choice |
|---|---|
| Model | An open instruct model of about 7–8B parameters, or 3–4B on a 40 GB card. Also used as the "base open model" in E2.3. |
| Method | GRPO with LoRA. Rollouts and training share the GPU (vLLM colocated with TRL or verl). The verifier runs in parallel CPU workers. |
| Episode | At most 4 verifier calls: propose a sequence, read the feedback, refine it. |
| Reward | Normalized gain (gain ÷ baseline net resources, clipped), paid **only** when all automated checks pass. Plus a novelty bonus for an attribution signature not yet in the archive, and a small penalty for invalid moves. |
| Budget | About 3 GPU-days per run *(proposed)*. 4 runs fit in the phase, leaving time for evaluation. |

### Experiments

| ID | Experiment | Runs |
|---|---|---|
| **E3.0** | **Format check.** Measure the base model's rate of valid moves. If it is below 80%, do a small format-only SFT on random valid sequences, which carry no loophole information. | — |
| **E3.1** | **Main run** on the planted train set. Evaluate on the val set every N steps. | 2 seeds |
| **E3.2** | **Interface control.** The same RL, but on law with **no planted loopholes**, where the only reward comes from legitimate planning. This separates "learned the tool and format" from "learned to find loopholes". | 1 |
| **E3.3** | **Distillation control.** SFT on frontier-model search traces from the train set, at a matched data budget. Compares RL with imitation. | 1 |
| **E3.4** | **Best-of-N control.** The base model at matched total inference compute. | inference only |
| **E3.5** | **Final held-out evaluation** (see the list below). | inference only |
| **E3.6** | **Monitoring during training.** Log the rates of PolicyEngine-only passes, canary-bug hits and reality-check failures. Training stops early if the canary-hit rate rises over 3 consecutive evaluations. | logged |

**E3.5 evaluation sets:**
- in-distribution val,
- held-out operators,
- held-out provision families,
- disguised test,
- real historical,
- Shelter Check,
- current law.

**How H5 is decided:**
- It is supported if E3.1 beats the base model, E3.2 and E3.4 on real-historical recall, and the gap to the frontier baseline from E2.3 narrows.
- It counts against H5 if the gains show up only on the in-distribution val set and the held-out operators, and not on held-out provision families or real loopholes.

---

## 6. Phase 4 — Expert review, disclosure and write-up (weeks 13–14, or later if an expert arrives late)

- **E4.1 Expert session.** The E2.7 packet goes to a CPA or tax attorney, plus Phase 3 survivors. The judge panel's accuracy is re-estimated against the expert's labels. If a second expert is available, measure agreement between the two.
- **E4.2 Disclosure.** Novel survivors are shared with the relevant experts or authorities before publication, described only at the level of provisions (research plan §9).
- **Write-up.** H1–H5 do not depend on the expert. Until expert review happens, H6 claims read "passed the automated checks and the calibrated LLM judges".

---

## 7. Statistics

- **Primary tests (pre-registered, Holm-corrected across five):**
  - H1: post-closure vs pre-closure flag rate.
  - H2: area under the recall curve, LLM + search vs the best non-LLM baseline.
  - H3: real-historical recall vs disguised recall.
  - H4: trend in the cross-check failure rate as search pressure increases.
  - H5: real-historical recall of the RL model vs the base model and vs the interface control.
- **Everything else** is exploratory and labelled as such.
- **Few historical cases:** always report per-case results alongside pooled numbers, and never report a pooled rate without its interval.

---

## 8. Hypothesis → experiment map

| Hypothesis | Experiments |
|---|---|
| H1 Verifier is valid | E0.1–E0.7, E1.1–E1.3 |
| H2 LLM + search beats baselines | E2.3, E2.5 |
| H3 Search, not memory | E2.2, E2.4 |
| H4 Code exploits are caught by the cross-check | E0.1, E2.6, E3.6 |
| H5 RL transfers to real loopholes | E3.0–E3.5 |
| H6 Novel candidates exist under current law | E2.8, E4.1 |

## 9. Timeline

| Weeks | Main track | Parallel track |
|---|---|---|
| 1–2 | E0.1–E0.8 | Start recruiting an expert; request the A100-80GB |
| 3 | E1.1–E1.4 → Gate G1 | E2.1 generator prototype |
| 4–6 | E2.1–E2.8 → Gate G2 | Build the RL environment and run E3.0 (weeks 5–6) |
| 7–12 | E3.1–E3.6 | E2.8 follow-ups; assemble the expert packet |
| 13–14 | E4.1–E4.2, write-up | — |

## 10. Risks this plan adds to the research plan's list

| Risk | Mitigation |
|---|---|
| No second calculator for benefits, so cliff and benefit gains can't be cross-checked | `single-calc` tag, separate reporting, hand audit (E2.6d) |
| Pre-2013 cases can only be cross-checked against TAXSIM | `taxsim-only` tag; extra known-answer tests for those years |
| Planted variants are easier or harder than real loopholes | Difficulty scoring and stratified, difficulty-matched comparisons (E2.1, E2.4) |
| RL gains come from learning the interface, not from finding loopholes | Interface control (E3.2) |
| A single GPU limits seeds and runs | Controls take priority over hyperparameter sweeps; budgets fixed in advance |
| LLM judges share blind spots with the searcher | Judges come from different families; calibration on canary bugs and cliffs |
| PolicyEngine is too slow | E0.3 benchmark and a pre-registered order for cutting budgets |

## 11. Suggested changes to the research plan

1. Add the rediscovery matching rule (§1.1) to the definitions in research plan §3.
2. Add the cross-check coverage tags (§1.2) to the verifier stack in research plan §5.1.
3. Add canary bugs (E2.6b) as the direct measurement for H4.
4. Add the interface and distillation controls (E3.2, E3.3) to the baselines in research plan §5.4.
5. Add the temporal held-out arm (E2.4) to H3.
6. Note that expert review gates only H6, and that LLM judges are calibrated against labelled items until an expert is available.
