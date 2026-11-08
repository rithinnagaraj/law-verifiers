# Pre-registration: stage 2 artificial difficulty (frozen before any stage 1 result)

**Committed:** 2026-11-07, before stage 1 (realistic enlargement) has run.
These settings are not changed after stage 1 results are seen. Stage 2 is
reported separately from stage 1 (user decision, 2026-11-07).

## Why two stages

E2.3 on 40-household pools: random search found 93% of planted loopholes
within 1,000 verifier calls, and greedy search was no better. Stage 1 makes the
search space *realistic* (survey households, several states, a multi-year
horizon, continuous amounts and timing, more move types, uncertain futures).
If random search still succeeds there, that is reported as a finding
(household loopholes within calculator scope are simple). Stage 2 adds
*artificial* difficulty on top of stage 1, to test whether search strategies
separate when the problem is made hard on purpose.

## Fixed stage 2 settings

| Knob | Setting | Notes |
|---|---|---|
| Base | the stage 1 environment unchanged (households, states, horizon, moves, scenarios, verifier) | |
| Minimum witness length | **3 coordinated moves**, at least one dated in a later year of the horizon | planted families are redesigned so that no shorter sequence gets ≥ R of the gain from the mutation; checked by exhaustive search over all sequences of length ≤ 2 on the witness household (a family fails this check → dropped, not tuned) |
| Eligibility rarity | pool of **200** households, **1** of them eligible (the witness); eligibility is a conjunction of ≥ 3 household facts | rarity checked by evaluating the witness sequence (adapted by role) on every pool household under the mutated law |
| Distractor moves | **15** extra move types that are valid and plausible but never create a federal gain under the mutated law (e.g. changing withholding, rebalancing within the same asset class, moving cash between accounts of one person) | they enlarge the branching factor only |
| Decoys | **5** move patterns that produce *intended* gains (retirement contributions, itemizing) in every household | they reward greedy search for climbing toward intended concessions |
| Budgets | {100, 300, 1,000, 3,000} verifier calls | |
| Seeds | 5 per condition × target × budget | |
| Matching | closure test, R = 0.1 | as stage 1 |
| Cross-check | tolerance mode, max($25, 10%) | as stage 1 |
| Gain scope | federal income tax only | user decision |
| Conditions | random, greedy (hill-climbing), and — after stage 1 is done — LLM + search, base open model + search | no LLM runs before stage 1 is done |
| Primary metric | area under the recall-vs-log-budget curve, reported per target and pooled with hierarchical bootstrap CIs | |

## What counts as a result

- Stage 2 is an *artificial* stress test; its recall numbers are not claims
  about real household tax law, and they are never pooled with stage 1.
- If random search matches every other condition in stage 2 too, the report
  says so: the knobs above did not make search matter.

## Outcome of the pre-registered construction, and a labelled deviation (2026-11-08)

**Pre-registered stage 2: no valid targets.** Two new families (CTC phase-out
threshold for married filing separately raised; exploited by filing
separately, moving the children to the lower-income spouse, and moving bond
income or business income to that spouse, dated 2025) were built with two
magnitudes each (`experiments/e2_s2_prepare.py`, `results/phase2/stage2/`):

- business variants: the witness loses money overall, and a two-move
  shortcut exists (separate, then pay a young child the business income as
  wages — stopped in reality by the judge-made reasonable-compensation
  doctrine, which the vocabulary deliberately does not enforce);
- bond variants: valid witnesses (the mutation creates 40-42% of the gain),
  but six two-move sequences get >= R of their gain from the mutation —
  separating and gifting the bonds suffices, because in the "income halves"
  future the high earner keeps the children and falls under the mutated
  threshold.

As pre-registered, failing families were dropped, not tuned.

**Deviation (decided by the researcher, 2026-11-08, before running).** An
exploratory run applies the remaining stage 2 settings — 200-household survey
pools, the 15 distractors and 5 decoys, sequences of up to 4 moves, the
tolerance cross-check — to the **stage 1 targets** (16 planted, 5 historical),
with random pools (the rarity filter exists only for the stage 2 families),
400 verifier calls and 2 seeds (stage 1's budget, so the two are comparable).
It is reported separately, labelled exploratory, and never pooled with
stage 1 or presented as the pre-registered stage 2.
