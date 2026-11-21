# Research Plan v2: Red-Teaming Encoded US Household Tax Rules with Verifier-Guided Search

**Status:** v2, 2026-11-22. Replaces [`us-tax-red-teaming-research-plan.md`](us-tax-red-teaming-research-plan.md) (v0.1) after four rounds of adversarial review. Thresholds marked *(to freeze)* are fixed in the pre-registration before any LLM search runs. Evidence so far is in [`results/FINDINGS.md`](results/FINDINGS.md).

---

## 1. Problem statement

Whether a tax strategy is a loophole is usually settled by experts, often years later. That keeps tax law out of reach of methods that learn from automatic checks. US household tax is an exception: two independent open-source calculators, PolicyEngine-US and Tax-Calculator, encode its statutory core.

Within that encoded scope, the project asks:

1. Can search agents find exploitable gaps in the statutory household rules as encoded?
2. Does success depend on searching rather than on recall of tax history?
3. How often do agents exploit calculator bugs instead of the law, and how much of that does a two-calculator cross-check catch?

**Out of scope by design:** judge-made doctrines (substance over form, step transaction, reasonable compensation, assignment of income), entities (businesses, trusts, partnerships), cross-border structures, and taxes or benefits that only one calculator models. Encoding the doctrines ourselves would reintroduce the formalization bottleneck the project avoids.

## 2. Contributions

1. A two-calculator verifier for household tax loopholes, with known-answer targets (historical closures, planted loopholes, canary bugs).
2. A measurement of the search depth of household statutory loopholes: how much search, and of what kind, they need.
3. A measured rate of verifier gaming: how often search exploits calculator bugs, and how much a cross-check catches. This is also a differential test of two widely used calculators.

## 3. Literature

- Blair-Stanek, Holzenberger & Van Durme (2025), *Can LLMs Identify Tax Abuse?* (Shelter Check): 36 strategies, expert grading. The 5 public strategies are corporate, trust or cross-border; none is expressible as household moves (`results/phase0/E0_4_vocabulary_audit.md`).
- Fratrič, Holzenberger & Restrepo Amariles (2025): LLMs formalize law before searching it; formalization is the bottleneck.
- Holzenberger, Blair-Stanek & Van Durme (2020), SARA, and Merigoux, Chataing & Protzenko (2021), Catala: statutory tax rules can be encoded as code.
- PolicyEngine-US and Tax-Calculator (Policy Simulation Library): household tax encoded at scale.
- DeepSeek-R1 (2025) on learning from verifiable rewards; Krakovna et al. (2020) on specification gaming. Together they predict both fast progress and exploitation of the verifier.

## 4. Definitions

| Term | Definition |
|---|---|
| **Household** | A tax unit and its members: people, incomes, assets, dependents, state. Drawn from PolicyEngine's enhanced CPS 2024 survey (stage 1 onward) or hand-built (witnesses, archetypes). |
| **Move** | One call from a fixed vocabulary of statutory, bright-line actions (§6.3). It may be dated to a year of the horizon and may depend on which future occurs. |
| **Gain** | Reduction in **federal income tax** over the horizon, probability-weighted over the household's possible futures. Credits only one calculator computes (saver's credit) are excluded. |
| **Economic reality unchanged** | Pre-tax income, hours worked and end-of-horizon wealth match the baseline in every future, within max($1, 0.5%). |
| **Intended concession** | A gain of which at most 10% remains when the pre-registered intended provisions are switched off together, and which circumvents no anti-abuse provision. |
| **Candidate** | A move sequence with positive gain, both calculators agreeing, reality unchanged, and not an intended concession. |
| **Mutation-attributable gain** | For planted targets: the proposal's gain under the mutated law minus its gain under current law. Known only offline. |
| **Match** | A candidate whose mutation-attributable gain is at least $50 and at least R of its gain; for historical targets, the closure takes the mutation's place. |
| **Verified loophole** | A candidate that also passes the LLM-judge panel and expert review. |

## 5. Hypotheses

| | Hypothesis | Decision rule |
|---|---|---|
| **H1** | The verifier separates households a closure covers from those it does not, and gives at most 5% false positives on legitimate planning. | Historical closures (per case): sensitivity ≥ 0.9 and specificity ≥ 0.9 *(to freeze)*. Legitimate-planning **test split**: false-positive rate ≤ 5%. |
| **H2** | *Sample efficiency.* On non-decomposable interaction targets, LLM + search beats the best baseline (random, greedy, beam enumeration). | Area under recall vs. log verifier calls; confidence intervals by hierarchical bootstrap (families, then seeds). Secondary: baselines given equal wall-clock and dollar cost. If a baseline matches the LLM, report that household rules within scope are shallow. |
| **H3** | *Surface invariance.* Recall does not depend on whether rule text is plain or disguised. | Paired TOST, equivalence margin Δmax = 0.15 recall, fixed in advance. If a pilot shows < 80% power at ≤ Δmax, H3 is reported as an exploratory confidence interval. |
| **H4** | Search exploits divergent calculator bugs, and the cross-check catches most of them. | (a) Cross-check catches ≥ 80% of canary-bug exploits. (b) Calculator disagreement among flagged proposals exceeds the random-sampling floor (E0.1). |
| **H5** | RL with the verifier reward improves recall on held-out mechanisms. | **Exploratory unless ≥ 20 families exist.** Two arms: oracle reward (upper bound) and verifier reward; both evaluated without the oracle. |

Deeper structural memorization is addressed by counterfactual interaction mutations (no historical analogue) and by the temporal arm, not by H3.

## 6. Method

### 6.1 Verifier

| Check | Rule |
|---|---|
| Valid moves | The move layer enforces bright-line statutory rules (contribution limits, HDHP coverage for HSAs, wash sales, no head-of-household or single status for a married person living with the spouse). |
| Gain | Federal income tax, both calculators, over the horizon and the futures (§4). |
| Reality | §4. |
| Cross-check | Tax-Calculator and PolicyEngine agree on the gain within **max($10, 2%)** *(to freeze; 1–10% sensitivity sweep reported)*. A disagreement is labelled `code_disagreement`. |
| Intended concessions | Pre-registered whitelist: EITC, CTC, head-of-household status, retirement contributions, saver's credit, dependent standard-deduction floor, kiddie-tax allowance. Anti-abuse provisions (kiddie tax, dependent standard-deduction limit, child AMT limit, EITC investment-income limit) override the whitelist. **All results are also reported with the whitelist off.** |
| Coverage tags | `two-calc`; `shared-code` where ≥ 10% of the gain comes from this package's own Form 8615 implementation; `single-calc` components (benefits, payroll, state) are reported separately. |
| Consistency | Flagged proposals may be re-evaluated alone (`recheck_flagged`) to guard against batch-composition bugs (F8, F12). |

Terminal valuation: where moves change a traditional IRA balance, each calculator adds the federal tax on distributing the remaining balance in the final year. This is a stated convention.

### 6.2 Targets

| Set | Content | Role |
|---|---|---|
| **Historical closures** | Two families reported as case studies: (1) gift income to a child — kiddie tax TRA 1986 / TIPRA 2005 / SBWOTA 2007 and the TRA 1986 dependent standard-deduction limit; (2) Roth recharacterization, repealed by TCJA 2017. Child AMT (TRA 1986) is reported as an H4 finding (PolicyEngine lacks the rule). | H1, H2 case studies |
| **Interaction mutations** | **≥ 20 families**, each decoupling two provisions in both calculators, split into train / val / test **by mechanism** (thresholds, phase-outs, filing-status splits, income shifting). | H2, H3, H5 |
| **Negative controls** | Mutations that make an intended provision more generous (e.g. the dependent floor). They must not be flagged. | Verifier check |
| **Canary bugs** | Documented bugs injected into PolicyEngine only. | H4 |
| **Temporal arm** | Provisions that postdate a model's training cutoff and are encoded in both calculators, where they exist. | Memorization control |
| **Legitimate-planning suite** | Pre-registered, dev/test split. Positives: 401(k), IRA and HSA contributions; itemizing vs. standard deduction; joint vs. separate filing; which unmarried parent claims a child; gifts within the kiddie-tax allowance; donation bunching. Labelled negatives: real sacrifices, benefit cliffs, wash sales, NIIT-avoiding gifts (expected flagged). | H1 |

**Non-decomposability gate.** Every interaction family must pass, before any search runs:

1. Exhaustive check on **10 stratified archetypes** (income level × family type, witness included): no sequence of k−1 moves from a discretized grid, dated across the horizon, gets ≥ R of its gain from the mutation.
2. Neither of the two mutations alone gets ≥ R of the witness gain.
3. A random sample of continuous amounts passes the same test.

Families that fail are dropped, not tuned, and the rejection rate is reported. Any (k−1)-move match found during search on any household flags the family as decomposable. The primary analysis keeps all pre-registered families (to avoid selecting on the outcome); excluding flagged families is a secondary analysis.

**Matching.** R = 0.1 primary (E0.7: precision 0.986, recall 1.00), R = 0.5 robustness, plus the $50 floor. The distribution of mutation-attributable shares is reported.

### 6.3 Environment

- Households: enhanced CPS 2024 survey households, 50 states, sampled by survey weight. Excluded (outside the calculators' overlap): Alaska, households with rental income. Pools of 40–200 households, witness hidden at a seeded position under a neutral id.
- Horizon: 3 tax years (2024–2026) with three possible futures from 2025 (assets ±25%, wages halved). Sensitivity run over 10 years (both calculators project law to 2035).
- Moves: filing status, assign dependent, gift asset, shift business income, realize gain, set hours, itemize, retirement contributions, HSA, cash donations and their timing, donate appreciated asset, Roth conversion, recharacterization (where law permits). Continuous amounts; moves may be dated and scenario-contingent.
- The distractor and decoy moves of exploratory stage 2 are not primary evidence.

### 6.4 Conditions

| Condition | Notes |
|---|---|
| Random search | Fresh random household and sequence each try. |
| Greedy search | Top-5 elite list, 40% exploration, mutate by add / drop / replace one move. |
| Beam enumeration | Breadth-first over the discretized grid, per household. |
| Frontier LLM + search | Plain or disguised rule text; knowledge probe as covariate. Several providers. |
| Open model + search | Same scaffold, before RL. |
| RL-trained open model | GRPO + LoRA on the A100 (40 GB → 3–4B model). Oracle-reward arm and verifier-reward arm. |

**What agents see:** only the verifier's output (gain and check results), in every condition. Mutation-attributable gain is used only for offline scoring and as the oracle-arm reward.

### 6.5 Metrics

| Metric | Hypotheses |
|---|---|
| Sensitivity, specificity, false-positive rate | H1 |
| Recall vs. verifier calls (AUC); cost-parity recall | H2, H3, H5 |
| Canary catch rate; disagreement among flagged vs. random | H4 |
| Diversity (distinct mechanisms found) | H2, H5 |
| Verifier error rate vs. adjudicated expert labels | all |
| Calls, wall-clock and dollars per match | all |

### 6.6 Downstream review

- **LLM-judge panel:** three models from different providers, none from the searching model's family, calibrated on labelled items (historical loopholes, legitimate planning, benefit cliffs, canary exploits).
- **Borderline audit:** every candidate whose calculator disagreement exceeds half the tolerance.
- **Expert review:** about 40 unique strategies (deduplicated by moves and mechanism across conditions), blinded, one CPA or tax attorney; a second expert on a 30% overlap for Cohen's κ; disagreements adjudicated.
- Judge or expert disagreement with the verifier is reported as a verifier error rate. It never relabels results. H1–H5 do not depend on expert review.

## 7. Statistics

- Pre-registered primary tests: H1, H2, H3 (if powered), H4. Holm correction across the confirmatory set.
- Clustering: targets are clustered in families; all intervals resample families, then seeds. Historical closures are per-case studies, never pooled rates.
- Seeds: 5 per condition × target × budget *(to freeze)*. Budgets {100, 300, 1,000, 3,000} verifier calls *(to freeze)*.
- Budget cut order if compute falls short (pre-registered): seeds 5 → 3; drop the 3,000 budget; 10-year sensitivity run last.

## 8. Current evidence (2026-11-22)

All results so far are pre-registration and exploratory. Details in `results/FINDINGS.md`.

| Hypothesis | Status | Evidence |
|---|---|---|
| H1 | Preliminary support | Historical cases both calculators model: sensitivity 1.00, specificity 1.00; legitimate planning 0% false positives (federal scope, unfrozen set, ratio cross-check). Roth case 3/9; child AMT fails (F3). |
| H2 | Not answered | Baselines only, on single-parameter targets: random / greedy recall at 400 calls 0.87 / 0.80 (synthetic pools), 0.72 / 0.62 (survey households), 0.44 / 0.25 (with decoys and distractors). |
| H3 | Not answered | No LLM runs. |
| H4 | Partly answered | Search exploited every planted federal-tax bug; a 10% tolerance caught 94% (ratio test 29%). Drift toward disagreement: weak exploratory trend only. |
| H5 | Not started | GPU ready. |

Other findings: calculators agree within $25 on 99.7% of 4,122 survey returns; E0.7 matching threshold (R = 0.1); pre-registered 3-step loopholes could not be built without 2-step shortcuts; calculator issues F1–F12 (missing child-AMT rule in PolicyEngine, batching bugs, parameter pairings).

## 9. Work plan

| # | Work | Status |
|---|---|---|
| 1 | Interaction-mutation catalog (≥ 20 families) and the 10-archetype non-decomposability gate | To do. Main risk: if < 20 families pass, H5 stays exploratory. |
| 2 | Legitimate-planning suite extended (HSA, joint vs. separate, donation bunching); dev/test split frozen | To do |
| 3 | Beam-enumeration baseline; cost-parity check; 10-year sensitivity run | To do |
| 4 | Verifier defaults switched to the final settings (tolerance cross-check, max($10, 2%)) | To do |
| 5 | Pilot power analysis for H3; full pre-registration frozen | To do |
| 6 | H1 and H4 rerun under frozen settings | To do |
| 7 | LLM conditions (H2, H3), judge panel, temporal arm | Needs API keys |
| 8 | RL (H5) | After 1 and 6 |
| 9 | Expert review; disclosure; write-up | Needs two experts |

Already built: verifier stack (federal scope, tolerance mode, scenarios, horizon, terminal valuation); historical cases; canary bugs; survey households; random and greedy search; LLM proposer code; non-decomposability check for one household; legitimate-planning set.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Fewer than 20 interaction families pass the gate | H5 stays exploratory; report the rejection rate as a finding about search depth. |
| Random search matches everything (H2 fallback) | Reported as a result: household rules within scope are shallow. |
| Both calculators share a simplification | Audit of certified candidates against the statute; expert review. Not measurable by the cross-check. |
| Optimizers concentrate in the calculators' disagreement tail | H4(b) measures it; borderline audit. |
| Whitelist encodes a judgment | Pre-registered, published, and every result reported with it off. |
| Three-year horizon favors short-term strategies | 10-year sensitivity run; terminal valuation for retirement balances. |
| Memorization beyond surface wording | Counterfactual interaction mutations; temporal arm. |
| Expert time and single-rater bias | Deduplication to ~40 strategies; second expert for κ. |

## 11. Ethics and disclosure

- Findings are tax-avoidance strategies and could be misused. Novel verified findings are shared with relevant authorities before publication and described at the level of provisions, not step-by-step.
- No real taxpayer data: survey households are public, anonymized microdata.
- Trained agents are not released as standalone loophole-finding tools.

## 12. Changes from v0.1 (decision log)

| Topic | v0.1 + experiment plan | v2 | Why |
|---|---|---|---|
| Scope | "US household tax law" | Statutory household rules as encoded in two calculators; judge-made doctrines out | Review round 1 |
| Gain | Benefits minus all taxes | Federal income tax only | Only the overlap can be cross-checked |
| Cross-check | TC confirms ≥ 50% of PE's gain | Agree within max($10, 2%) | Canary catch 29% vs. 94%; review round 2 |
| Matching | Closure removes ≥ 80% + signature Jaccard | Mutation-attributable ≥ $50 and ≥ R, R = 0.1 (0.5 robustness) | E0.7; review rounds 1–2 |
| Historical set | ≥ 8 cases, pooled rates | Two families, per-case studies | Effective N ≈ 2; review round 1 |
| Planted set | Single-parameter mutations | ≥ 20 interaction families, split by mechanism, non-decomposability gate on 10 archetypes | Review rounds 1–4 |
| Shelter Check | Recall target | Reported as out of scope (0/5 public in scope) | E0.4 |
| H2 | LLM beats random at matched compute | Sample efficiency, plus beam baseline and cost parity; shallow-rules fallback | Review rounds 1, 3, 4 |
| H3 | Disguised ≈ real recall | Paired TOST, Δmax = 0.15 fixed in advance; surface invariance only | Review rounds 2–4 |
| H4 | Failure rate rises with pressure | Canary catch ≥ 80%; disagreement tail measured; borderline audit | Review round 3 |
| H5 | Headline | Exploratory unless ≥ 20 families; oracle and verifier-reward arms | Review rounds 2–3 |
| H6 (novel finds) | Exploratory hypothesis | Folded into downstream review and disclosure | Simplification |
| Expert review | Unspecified | Judge panel + borderline audit + ~40 strategies, two experts with κ | Review rounds 2–3 |
| Horizon | 3 years | 3 years + futures + terminal valuation; 10-year sensitivity | Review round 1 |
| Stage 2 | Pre-registered artificial difficulty | No valid targets; decoys and distractors demoted to exploratory | Stage 2 outcome |
