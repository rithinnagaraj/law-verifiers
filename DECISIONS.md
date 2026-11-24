# Design decisions and plan deviations

A dated log of every change from `experiment-plan-v2.md`, with the reason and
what had been run when it was made. Carried into the A9 pre-registration
verbatim. Rules marked *before the spike* were fixed before any A5a spike
candidate was gated; none of them may be changed in response to spike
results except through the logged G0 revision procedure (at most 2
revisions, each recorded here with its reason).

## Phase A

| Date | Change | Reason | Evidence at the time |
|---|---|---|---|
| 2026-11-24 | No `itemize` move (forced itemization). | Tax-Calculator cannot force the itemization choice, so the cross-check would flag every such proposal as a code disagreement. | v2 calculator tests, before A2. |
| 2026-11-24 | Benefit cliffs are expected as `sacrifice` or `no_gain`; there is no separate benefit-cliff label. | Within the federal-income-tax scope, a cliff that loses money is a sacrifice; one that does not is no gain. | Plan-review scope; before A2. |
| 2026-11-24 | A3 rebuilds the canary search (random and blind greedy, 3 seeds) and measures false rates on the A4 dev split. The extended whitelist (adds the HSA and charitable deductions) is evaluated alongside the plan whitelist. | v1 code is abandoned; the dev split is the only legitimate-planning set not reserved for the test. | Before A3. |
| 2026-11-24 | **A5 generator redesigned (before the spike).** The first generator paired parameters without regard to how they enter the tax computation (status pairs, status × child scalar, scalar pairs) at magnitudes ×1.5 and ×2.5. It was replaced by operators that target max/min structures first: `amt_pair` (regular-tax parameter × AMT parameter, same status), `eitc_pair` (EITC investment-income limit × EITC phase-out start or rate), then `status_pair`, `status_child`, `scalar_pair`, taken round-robin in a seeded order. Magnitudes ×2 and ×4. | (1) Argument: gate check 3 requires each mutation alone to give < R = 0.1 of the gain on the witness. When two mutations act additively, each alone moves the gain by its own full share, so an additive pair can never pass. Interactions need a structure where loosening one constraint does nothing while the other binds (tax = max(regular, tentative minimum tax); several EITC tests). (2) Smoke test of one candidate from the first generator (`brk1.SEPARATE + cg0.SEPARATE` at ×2.5, witness budget 300): no interacting witness in 300 proposals. | One smoke-test candidate only. It was not one of the spike candidates, and no spike candidate had been gated under either generator. |
| 2026-11-24 | **Counting rule for one-move witnesses (before the spike).** A family passes only if, at both magnitudes, its minimal witness needs ≥ 2 moves and all five checks pass. The witness is the shortest interacting sequence found, and every single move of every interacting sequence found is also tested alone. If one move suffices, the family is `shallow`. Checks 2 and 4 are then vacuous and are not run. Shallow families are recorded and reported with their own count, but they do not count toward G0, G2 or the split. Supersedes the earlier same-day version of the generator change, which let shallow families pass. | For k = 1 the non-decomposability check (no (k−1)-move shortcut) tests nothing, so counting such families would loosen the gate and inflate the counts that decide G0 and G2. Raised in review. | Before any spike candidate was gated. |
| 2026-11-24 | **A5 reporting and split rule (before the spike).** The summary reports pass / shallow / fail counts per operator and per mechanism, every gate's rejection reason and the failed-check counts. It states that the catalog is constructed (a designed generator), so pass rates are not an estimate of how common interactions are in law. Split: passing families only. Two mechanisms (seeded choice, when ≥ 3 mechanisms pass) go to test only. Test is then filled to max(8, 40%) from the other families in seeded order, val to max(3, 15%), and train takes the rest. | Fixes the reporting and the split before outcomes are seen. | Before any spike candidate was gated. |

## G0 revisions

None yet. Each revision records the failed spike's per-check rejection
counts, what was changed, and why, before the new spike runs.
