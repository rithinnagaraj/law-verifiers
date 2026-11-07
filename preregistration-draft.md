# Pre-registration draft (E0.8) — proposal, not yet frozen

**Status:** draft for the researcher's review, 2026-11-07. **The E0.7 (R) and E2.3 evidence cited below came from runs invalidated by bug F12; reruns are pending and the values must be re-checked before freezing.** Nothing here is
frozen until it is committed as `preregistration.md` before any agent
(LLM) search runs. Each value lists the evidence behind it; numbers come from
`results/FINDINGS.md`.

## Verifier

| Setting | Proposed | Evidence / reason |
|---|---|---|
| Gain threshold | $50 / year (horizon total scales with years) | E1.2: removing it changes no label on the legitimate-planning set; small enough to keep all closure witnesses |
| Reality tolerance | max($1, 0.5%) per component | E0.6: all labelled sacrifices / cliffs caught; no positive falsely failed |
| Cross-check | **tolerance mode**: federal gains agree within max($25, 10%) | E2.6b (after F12): of 173 canary exploits found by search, the ratio test (TC ≥ 50% of PE) caught 29%, the tolerance test 94%; witnesses 3/6 vs 6/6. Child-AMT closure (F3): ratio test passed 44 of 56. Cost: E0.1 noise floor is 3.7% of returns differing by > $25 (mostly F6, now fixed) — rerun E0.1 with the F6 fix to confirm the floor before freezing. |
| Coverage tag two-calc | ≥ 90% of the gain is comparable federal income tax | unchanged |
| Attribution share (signature) | 0.2 | unchanged |
| Intended residual max | 0.1 | E0.6: 46/46 401(k) and 18/20 IRA scenarios → intended; NIIT avoidance at 11% of gain correctly stays a candidate |
| Anti-abuse override | on | fixes the EITC investment-limit mislabel (test_cases) |
| Horizon | 3 years (2024–2026) | research plan §3; implemented, tested (gain harvesting); **not yet used in any experiment** — budget ×3 per call |

## Matching rule

| Setting | Proposed | Evidence |
|---|---|---|
| Closure-test threshold R | **0.1–0.2** (E0.7 picks 0.1; 0.2 is the conservative end) | E0.7 on 8 planted variants: R ≤ 0.1 → precision 0.989, recall 1.00; R = 0.2 → recall 0.967; the plan's 0.8 → recall 0.37. Real instances of a planted loophole often also collect current-law gains (kiddie_age instances: reductions from 0.27). |
| Signature Jaccard | drop as a requirement; report it | for planted variants the signature half reduces to the closure test (the mutation is the provision); historical cases have no independent signature either |

## H1 (amended operationalisation)

Measured on the closed mechanism (`experiments/e1_closures.py`):
sensitivity (covered households flagged pre-closure with > 2% of the gain
removed) ≥ 0.9; specificity (uncovered households lose ≤ 2%) ≥ 0.9;
closed provision never in the post-closure signature; legitimate-planning
false-positive rate ≤ 5% overall and reported per coverage tag.
Current status: met on all cases both calculators can see (child-AMT fails
on PolicyEngine — reported as an H4 finding, not hidden).

## Search experiments (E2.3)

| Setting | Proposed | Evidence |
|---|---|---|
| Target unit | **pool of 40 households** (witness hidden among random ones) | witness-only targets: random search rediscovered 10/10 within 200 calls (H2 cannot be tested there) |
| Budgets | {100, 300, 1,000, 3,000} verifier calls | plan; pool runs pending |
| Seeds | 5 per condition × target × budget | plan |
| Splits | planted families: train = mfs_brackets, ctc_mfs; val = niit_mfs (one magnitude); test = kiddie_age, kiddie_allowance (held out with the historical set) + controls | E2.1; more families needed (≥ 5 per split) before Phase 3 |

## Budget cut order (if throughput falls short)

1. seeds 5 → 3; 2. drop the 3,000 budget; 3. horizon 3 → 1 for the
planted set only.

## Open decisions for the researcher

- Cross-check mode (tolerance vs ratio) — the evidence favours tolerance.
- R = 0.1 vs 0.2.
- Whether benefit-only gains (F9) are reported as candidates or as their own
  category (like benefit cliffs).
- Which frontier models / providers for E2.3 (API keys needed on the VM).
