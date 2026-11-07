# Pre-registration draft (E0.8) — proposal, not yet frozen

**Status:** draft for the researcher's review, 2026-11-07. (E0.7, E2.3 and E2.6b evidence below is from the reruns after bug F12.) Nothing here is
frozen until it is committed as `preregistration.md` before any agent
(LLM) search runs. Each value lists the evidence behind it; numbers come from
`results/FINDINGS.md`.

## Verifier

| Setting | Proposed | Evidence / reason |
|---|---|---|
| Gain threshold | $50 / year (horizon total scales with years) | E1.2: removing it changes no label on the legitimate-planning set; small enough to keep all closure witnesses |
| Reality tolerance | max($1, 0.5%) per component | E0.6: all labelled sacrifices / cliffs caught; no positive falsely failed |
| Cross-check | **tolerance mode**: federal gains agree within max($25, 10%) | E2.6b (after F12): of 173 canary exploits found by search, the ratio test (TC ≥ 50% of PE) caught 29%, the tolerance test 94%; witnesses 3/6 vs 6/6. Child-AMT closure (F3): ratio test passed 44 of 56. Noise floor after the F6 fix (E0.1): 0.4% of 2024 returns (0.4% 2025, 0.6% 2026) differ by > $25, mostly the child AMT (F3). |
| Coverage tag two-calc | ≥ 90% of the gain is comparable federal income tax | unchanged |
| Attribution share (signature) | 0.2 | unchanged |
| Intended residual max | 0.1 | E0.6: 46/46 401(k) and 18/20 IRA scenarios → intended; NIIT avoidance at 11% of gain correctly stays a candidate |
| Anti-abuse override | on | fixes the EITC investment-limit mislabel (test_cases) |
| Horizon | 3 years (2024–2026) | research plan §3; implemented, tested (gain harvesting); **not yet used in any experiment** — budget ×3 per call |

## Matching rule

| Setting | Proposed | Evidence |
|---|---|---|
| Closure-test threshold R | **0.1** (0.2 as the conservative end) | E0.7 after F12, 15 valid planted variants, 956 proposals: R ≤ 0.1 → precision 0.986, recall 1.00; R = 0.2 → recall 0.943; R = 0.3 → precision 1.00, recall 0.908; the plan's 0.8 → recall 0.30. Real instances of a planted loophole often also collect current-law gains (kiddie_age instances: reductions from 0.27). |
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
| Target unit | **pool of 40 households** (witness hidden among random ones) | witness-only targets (after F12): random and greedy search rediscover all 19 targets within 100 calls (H2 cannot be tested there) |
| Budgets | {100, 300, 1,000, 3,000} verifier calls | plan; pool runs pending |
| Seeds | 5 per condition × target × budget | plan |
| Splits | planted families (by family): train = mfs_brackets, ctc_mfs, actc_rate; val = niit_mfs, mfs_std, cg0_single (horizon 3); test = kiddie_age, kiddie_allowance (held out with the historical set); control = dependent_floor | E2.1 run 4: 15 of 16 non-control variants valid; more families needed (≥ 5 per split) before Phase 3 |

## Budget cut order (if throughput falls short)

1. seeds 5 → 3; 2. drop the 3,000 budget; 3. horizon 3 → 1 for the
planted set only.

## Open decisions for the researcher

- Cross-check mode (tolerance vs ratio) — the evidence favours tolerance.
- R = 0.1 vs 0.2.
- Whether benefit-only gains (F9) are reported as candidates or as their own
  category (like benefit cliffs).
- Which frontier models / providers for E2.3 (API keys needed on the VM).
