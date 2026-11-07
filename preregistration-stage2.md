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
