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

| 2026-11-25 | **A2 rerun after two PolicyEngine adapter fixes.** (1) The saver's credit is set to 0 as a PolicyEngine input instead of adding the computed credit back. (2) Care expenses go to the tax unit as paid, so PolicyEngine's imputed childcare subsidy is not subtracted. The first A2 run is kept in `~/taxgap-results/a2-prefix-0a2fde9` and is not used for the tolerance choice. | The first run's disagreements clustered at $333 and $667 (a $1,000 or $2,000 difference in one of three futures). A decomposition of 12 sampled single-move cases traced 10 of them to these two causes, and the other 2 fit the same pattern. Both are adapter bugs, not differences in law between the calculators. | First A2 run: `code_disagreement` 1.3%, p99 $333. 300-household probe after the fix: 0.17%, p99 $15. The remaining cases are $6–48 (Roth conversions and capital gains, higher incomes). |
| 2026-11-25 | **Tolerance frozen at max($5, 1%) by the A2 rule** (plan A2 "Decision"), replacing the provisional max($10, 2%) in `Config` before A3 and the A5a spike. A3 reports it alongside the plan's sweep (the $10 rows keep their $10 floor). | The pre-set rule (smallest max($a, b%) with ≤ 1% of random proposals labelled `code_disagreement`) picks the tightest cell of the grid. | Full A2 rerun (59,298 proposals, 2,965 households): 0.38% `code_disagreement` at max($5, 1%), 0.22% at max($10, 2%); p99 abs. disagreement $25, p99.9 $1,066. The tail is concentrated in `set_filing_status` (p99 $518) and incomes above $200k (p99 $490–1,208). |
| 2026-11-25 | **A7 operationalization (before A7 ran).** "Beam finds the witness" means: given the witness household alone and a budget equal to its grid size up to depth k, beam reaches a match for the family's law (labelled candidate, attributable gain ≥ $50 and ≥ R). | The witness's amounts and dates are continuous, and beam enumerates the discretized grid, so the exact witness sequence cannot be reproduced. | Before A7 ran. |

## G0 revisions

Each revision records the failed spike's per-check rejection counts, what
was changed, and why, before the new spike runs.

### Spike 1 (generator v2, 2026-11-25): G0 not met, 0 of 10 pass

- Candidates: 2 `amt_pair`, 2 `eitc_pair`, 2 `status_pair`, 2 `status_child`, 2 `scalar_pair` (list in `results/a5/a5a_candidates.json`).
- Result: 0 pass, 0 shallow, 10 fail. Per gate (20 = 10 families × 2 magnitudes): no interacting witness 19; witness found but failed check 2 (grid) 1 (`eitc_pair:eitc_inv+eitc_prt1` ×2, 3-move witness on `w_partners_low`). No other check was reached.
- These 10 candidates stay rejected and are not re-gated.
- Diagnosis (scratch script `diag_a5.py`, run after the spike; 200 random sequences of ≤ 3 moves per family and magnitude on the 30 witness archetypes, plus each mutated law's effect on tax levels with no moves):
  - No bug found: every parameter that should affect a witness archetype changes its tax level (for example `brk4.SINGLE` on 14 of 270 household-years, `ctc_amt` on 102). The parameters with no level effect are limits that no archetype reaches under current law (`amt_ps.SINGLE`, `amt_ps.SEPARATE`, `brk5.SEPARATE`, `salt.HEAD_OF_HOUSEHOLD`, `eitc_inv`, `dep_std`).
  - Structure-blind operators (`status_pair`, `status_child`, `scalar_pair`, 6 candidates): 0 interacting sequences. Every sequence with attributable gain ≥ $50 either had one mutation alone ≥ R of the gain (additive) or the attributable gain was < 0.3 of the gain. This is what the additivity argument above predicts.
  - `amt_pair` (2 candidates): inert. The AMT never binds on any archetype, even with the regular-tax mutation applied (the combined law's level effect equals the regular-tax mutation's alone), so the AMT parameter never matters.
  - `eitc_pair` (2 candidates): the only witness. The investment-income test denies the whole credit, so loosening it does nothing for a household that is also phased out, and vice versa (an AND structure).

### Revision 1 (2026-11-25, before spike 2): generator v3, AND structures only

Chosen by the user from three options (AND structures over a wider catalog; AND structures over the current catalog; stop A5 and report).

- **Principle.** Check 3 requires each mutation alone to give < R of the gain on the witness. Only structures in which each of two conditions alone denies the benefit can pass that reliably. Every v3 operator pairs two parameters of one benefit from *different statutory subsections*, each of which on its own caps or denies the benefit:
  - `eitc_gate`: EITC investment-income limit (§32(i)) × each EITC range parameter (maximum credit, phase-out start, phase-out rate; §32(b)), for 0–3 children. 12 pairs.
  - `eitc_age`: childless-EITC minimum or maximum age (§32(c)(1)(A)(ii)) × the childless range parameters (§32(b)). 6 pairs.
  - `ctc_phase_out`: CTC or ODC amount (§24(h)(2), (h)(4)) × CTC phase-out threshold (§24(b), (h)(3)). A household beyond the phase-out end gains from neither alone. 2 × 4 statuses = 8 pairs.
  - `qbi_phase_in`: any two of the QBI rate (§199A(b)(2)), threshold (§199A(e)(2)) and phase-in range (§199A(b)(3)(B)); a self-employed filer with no W-2 wages beyond the range gets no deduction. 3 × 4 statuses = 12 pairs.
- **Dropped:** `status_pair`, `status_child` and `scalar_pair` (additive, as predicted and as seen in spike 1); `amt_pair` (inert: the AMT does not bind on any archetype); pairs within one EITC subsection (max × start × rate are all §32(b), so they would not be two provisions).
- **Catalog additions**, verified equal in both calculators for 2024–2026 by `catalog.verify()`, which drops any that differ: `eitc_age_min`, `eitc_age_max`, `qbi_thd.<status>`, `qbi_gap.<status>`, `qbi_rt`. Not added: the CTC phase-out rate, which PolicyEngine encodes as $50 per $1,000 and Tax-Calculator as 0.05, so it cannot pass the equal-values check.
- **Statuses:** v3 uses all four filing statuses. The v2 restriction to statuses a household can move into belonged to the filing-status operators, and the v3 structures do not involve a status choice.
- **Unchanged:** magnitudes (×2, ×4), archetypes, gate checks and thresholds (R, witness share, $50 floor, witness budget, grid cap, spot size), counting rule and split rule.
- **Selection:** the same as v2 (operators round-robin, each operator's candidates in a seeded order, seed 0). Spike 1's 10 candidates are excluded (two of them, `eitc_inv+eitc_ps1` and `eitc_inv+eitc_prt1`, would otherwise reappear in `eitc_gate`). Spike 2 takes the first 10; A5b takes the rest.
- **Known consequence, stated before the spike:** v3 has at most 36 candidates (fewer if any catalog addition fails verification), so A5b has at most 26. The plan's 60 (90) candidates and its G2 extension rule cannot be met in full. G2 (≥ 20 passing families) needs ≥ 20 of 36 to pass.
- **Expected weak spots, stated before the spike:** the archetypes' highest income is $320k, below the joint CTC phase-out end ($488k with two children) and the joint QBI threshold ($394,600), so those joint pairs may be inert. The archetypes stay unchanged.
- **Bug fix found by a pre-spike check (before spike 2 ran).** Before gating, the spike-1 diagnostic was rerun on the 10 spike-2 candidates to check that each mutated law takes effect. The age limits could not be checked that way (no archetype is a childless earner outside ages 25–64), so they were tested directly. Tax-Calculator rejects non-integer ages (25 × ½ = 12.5), so every `eitc_age_min` candidate would have errored in the gate. Fix: integer parameters are scaled and rounded to the nearest whole year, halves up (minimum age 13 at ×2 and 6 at ×4). Tax-Calculator also caps ages at 125, so the maximum age is clipped there: 64 × 2 = 128 and 64 × 4 = 256 both become 125, which means no upper age limit in both calculators. The `eitc_age_max` families therefore have the same age change at both magnitudes (only their range parameter differs between ×2 and ×4). The pre-check is used only to find bugs: operators and candidates are unchanged whatever it shows.

### Positive controls (2026-11-26, after spike 2's diagnosis, before revision 2; set before they were run)

Spike 2 failed (9 of 10 candidates gated so far, none passing). A diagnostic scan scored every reality-preserving grid sequence of one or two moves on the 30 witness households (37,706 sequences) for the 10 spike-2 candidates at both magnitudes, using PolicyEngine only. For 8 of the 10 it found no interacting two-move sequence at all. Every candidate had one-move matches on the gate households, so check 2 would fail all 10 even with a perfect search. Before revision 2 is chosen, the machinery is checked on loopholes known to have existed (the research plan's historical closures). The script is `experiments/a5_controls.py`; it changes nothing in the gate or the generator.

| Control | Law | Expected (stated before running) |
|---|---|---|
| `pre1986` | kiddie tax and dependent standard-deduction limit both undone (TRA 1986); each undone alone as L1, L2 | One-move loopholes found: a gift of an interest- or dividend-paying asset to a minor, labelled `candidate`, with the anti-abuse attribution naming the kiddie tax. Each closure undone alone keeps much of the gain (an OR, not an AND), so the gate finds no interacting witness. |
| `pre2006` | kiddie tax under age 14 only (before TIPRA 2005) | A one-move gift to the 15-year-old of `g_parent_*`, labelled `candidate` |
| `pre2008` | kiddie tax under 18, no student extension (before SBWOTA 2007) | A one-move gift to the 20-year-old student of `w_parent_student_*`, labelled `candidate` |
| `pre1996` | no EITC investment-income limit | Uncertain: no household combines EITC-range earnings with investment income above the limit, so possibly nothing |

How the result is used:
- If a control's loophole is missed or mislabelled, that is a bug and is fixed before revision 2.
- If all four behave as expected, the machinery recognizes real loopholes, and real income-shifting loopholes are one-move in this move set. Revision 2 then has to build depth into the planted structure rather than expect it from generous rescaling.

Correction to an option raised in the spike-2 diagnosis: narrowing check 2 to count only *interacting* one-move shortcuts is not admissible. The research plan defines non-decomposability as "no k−1-move sequence gets ≥ R of its gain from the mutation", and A6 matching counts any such sequence as finding the target. A one-move match therefore makes the target shallow for H2. Check 2 stays as written.

### Revision 2 (2026-11-26, before spike 3): witness search v2, generator v4 with a pre-gate screen

The user gave standing autonomy to iterate ("keep iterating independently and get things to work", 2026-11-26). This is the plan's last allowed G0 revision. Any later change is a plan deviation and will be logged here as one.

- **What the diagnosis showed.** The search was not the main cause, and the gate's thresholds were not either. Every spike-2 candidate rescales a parameter that some ordinary gate household is near, so one move already reaches the mutation, and check 2 (which stays as written; see the correction above) fails whatever the interaction structure. The positive controls agree: real income-shifting loopholes reached through the kiddie-tax rules are one-move in this move set. Depth has to come from where the mutation acts, not from the AND structure alone.
- **Witness search v2 (`family.witness_search(version=2)`).** First, every reality-preserving grid sequence of one or two moves on the 30 witness households is scored. Then the unchanged random/elite search runs for continuous amounts and three- or four-move sequences, now discarding sequences that change real income, hours or wealth before scoring them. Those discards do not count toward the 1,250 budget. Reason: spike 2's search spent its budget on hour cuts that check 1 labels sacrifices, and exhaustive enumeration of the grid dominates random sampling of it. Spikes 1 and 2 stay reproducible with version 1.
- **Generator v4 (`generate.candidates_v4`).** The operator is unchanged: two parameters from different provisions, both moved the tax-lowering way, ×2 and ×4. It now draws from every cross-provision pair of the verified catalog (3,277 pairs; spike 1 and 2 candidates excluded), in a seeded order. Mechanism = the two provisions' groups (`mechanism_v4`).
- **Pre-gate screen (`mutations/screen.py`).** Two necessary conditions of the gate, checked in the seeded order:
  - *hidden:* no one-move grid sequence on the 9 gate households is a match under L at either magnitude. This is check 2's own test (PolicyEngine filter, then the full verifier), without the witness household, which is not known yet.
  - *alive:* at both magnitudes, at least one of 1,500 sampled reality-preserving two-move grid sequences on the witness households has a gain over $50 and an attributable gain of at least $50 and at least 0.3 of its gain.
  - A mutated law that a calculator rejects is recorded as `invalid_law` and fails. For example, Tax-Calculator refuses a bracket threshold scaled past the next one. This was found in a 30-candidate timing test of the screen.
  - The screen never relaxes the gate: survivors are gated in full, all five checks, both magnitudes, unchanged thresholds.
- **Spike 3** = the first 10 screen survivors in the seeded order (stage `a5a3`), gated with search v2. A5b, if G0 passes, takes the next survivors.
- **Reporting.** The screen's counts are reported: screened, invalid law, visible to one move, not alive, survived. A pre-screened pass rate is not comparable with spikes 1–2 and is not an estimate of anything about tax law (the catalog is constructed).
- **Unchanged:** R, the witness share, the $50 floor, magnitudes, archetypes (gate and witness), all five checks, the counting rule and the split rule.
- **Timing test, stated for transparency.** Before this entry, the screen ran on the first 30 v4 candidates in a scratch results folder (`~/taxgap-scratch`), to time it and find crashes. It produced the invalid-law fix above. It changed no rule, and its rows are not used: the official screen runs from scratch.

### Positive controls: results (2026-11-26; `results/a5/controls.jsonl`)

All four behaved as expected, and no bug was found. The machinery recognizes real loopholes.

| Control | One-move matches (PE), households | Verifier on the 25 largest | Notes |
|---|---|---|---|
| `pre1986` | 168, 13 households | 8 `candidate`, 17 `code_disagreement` | Gift of the bond to a child. Each closure undone alone keeps 54–92% of the gain (an OR), and the gate finds no interacting witness, as predicted. The disagreements are gifts to the 13-year-old. With `child_amt_limit` also switched off, both calculators give $29,043. So they are Tax-Calculator's child-AMT rule, which PolicyEngine lacks (the research plan's H4 finding), not a bug. |
| `pre2006` | 30, 3 households | 25 `candidate` | Gifts to the 15-year-old of `g_parent_high` and the 20-year-old student of `w_parent_student_*` |
| `pre2008` | 21, 2 households | 21 `candidate` | Gifts to the 20-year-old student |
| `pre1996` | 9, 1 household | 9 `intended_concession` | 401(k) contributions that reach the EITC: the whitelist correctly calls them intended. Two-move: 2 `candidate` (of 5). |

One expectation was wrong in detail: the anti-abuse attribution does not name the kiddie tax for `pre1986`. That attribution removes the rule from L, and L has already removed it, so it explains nothing. The labels are as expected. All real loopholes found are reachable in one move. This is the premise of revision 2.

**Amendment to the revision-2 screen (2026-11-26, before spike 3; no gate had run).** The official screen started and was stopped after 85 of 300 candidates. Its rows are kept as `a5s4_draft1.jsonl` and not used. The survivors' names showed a gap in the *alive* condition. Most survivors paired a parameter that no household reaches (an AMT parameter, a separate-filer bracket) with one that some household does. The two-move gain such a pair shows comes from one mutation alone, so check 3 would reject it. The witness must be *interacting*: an attributable share of at least 0.3 *and* each mutation alone moving the gain by less than R. That is a cheap necessary condition of the gate, and it had been left out of the screen by oversight. *Alive* now requires a sampled interacting two-move sequence at both magnitudes. *Hidden* is unchanged. The screen restarts from scratch. Only survivor names and the screen's own counts were seen, never a gate result.

### Spike 2: final result (2026-11-26; `results/a5/a5a2.jsonl`)

0 of 10 pass; **G0 FAIL** (it needed 3 of 10). There were no crashes, and the last family took about a day in its check-2 grid. Per magnitude (20 gates):
- 14 found no interacting witness.
- 3 had a one-move (shallow) witness.
- 3 had a two-move or longer witness that failed checks.
- Failed checks: 1_witness 5, 2_grid 2, 4_spot 2.

The informative cases:
- **`eitc_gate:eitc_inv+eitc_prt2` at ×2:** a two-move witness that passed checks 2, 3, 4 and 5. It failed only check 1, because its moves were two hour cuts (`sacrifice`).
- **`eitc_gate:eitc_inv+eitc_max2` at ×2:**
  - its witness also changed hours;
  - check 2 found a real one-move match: shifting $9,500 of income to a child on `g_parent_mid`.

So the AND structures did produce interacting multi-move witnesses. The search spent its budget on hour changes, which revision 2's search v2 fixes.

### Revision-2 screen: result (2026-11-26; `results/a5/a5s4.jsonl`)

The first 600 of 3,277 v4 candidates were screened. Outcomes:
- 110 invalid law;
- 308 visible to one move;
- 182 not alive;
- **0 survived**.

Spike 3 as specified in revision 2 cannot run. Breakdown:
- Of the 182 not alive, 95 had no sampled two-move sequence with the attributable share at ×2 at all. The other 87 had such sequences (up to 51), but none was interacting: on every one, one mutation alone moved the gain by at least R. Random cross-provision pairs act additively.
- The one-move matches came mostly from `roth_convert`, which picks up rate-structure changes through the terminal valuation; then `shift_income` to a child and `set_filing_status`.
- The *alive* sample was thin. The full reality-preserving one- and two-move grid on the 30 witness households is 37,706 sequences, and the screen sampled 1,500 (about 4%). That makes *alive* a weak test. It does not explain the 87 additive cases.

### G0 revision 3: a plan deviation (2026-11-26, before spike 3)

The plan allows two G0 revisions, and this is a third. It is made under the user's standing instruction to keep iterating ("keep iterating independently and get things to work", 2026-11-26). It is reported as a deviation wherever G0 is reported.

Diagnosis. Revision 2 changed two things at once, and the evidence splits them:
- The search change was right: spike 2's best candidates failed on hour-change witnesses, which search v2 discards.
- The generator change was wrong: random pairs have no AND structure (the screen above).

The rules, fixed before any v5 candidate is gated or screened:
- **Generator v5 (`generate.candidates_v5`).** v3's four operators (two tests of one benefit, each of which alone caps or denies it), plus two structures of the same kind from the statute:
  - `amt_max`: a regular-tax parameter × the AMT exemption or exemption phase-out start, same filing status, all four statuses (s.55(a): the tax is the larger of regular tax and tentative minimum tax);
  - `dep_std_cap`: the dependent standard deduction's earned-income add-on × the single basic standard deduction (s.63(c)(5): the smaller of the basic amount and the larger of the floor and earned income plus the add-on).
  - Operators are taken round-robin, each operator's candidates in a seeded order. Spike 1 and 2 candidates are excluded. Ids are `v5:{operator}:{p1}+{p2}`.
  - Chosen on principle, before outcomes: each is a min or max in the statute, where loosening one side does nothing while the other binds. That is the property the ablation check (3) requires. No v5 candidate has been run.
- **No screen.** Every selected candidate is gated in full. Reasons:
  - The v5 catalog is small (tens, not thousands), so screening saves little.
  - A screen's thin sample would add a selection step that the gate itself does not need.
- **Valid laws only.** A candidate is skipped at selection if Tax-Calculator rejects any law the gate builds for it (L, L1, L2, Lrev at either magnitude, any horizon year). An example is a bracket threshold scaled past the next one. The skipped candidates are recorded in `v5_invalid_laws.json`. This is a property of the law, checked before any gate.
- **Spike 3** = the first 10 valid v5 candidates (stage `a5a3`), gated with witness search v2. A5b, if G0 passes, takes the next valid v5 candidates.
- **Unchanged:** R, the witness share, the $50 floor, magnitudes, archetypes, all five checks, the counting rule and the split rule. Check 2 stays as written.

### Spike 3: result (2026-11-27; `results/a5/a5a3.jsonl`)

0 of 10 pass; **G0 FAIL** (it needed 3 of 10). There were no crashes. Per magnitude (20 gates):
- 17 found no interacting witness (no grid or random sequence on the 30 witness households had an attributable share of 0.3 with each mutation alone under R).
- 1 found a two-move witness: `ctc_phase_out:ctc_amt+ctc_ps.SINGLE` at ×4 on `w_parent_student_high` (a 401(k) contribution, then filing as single). It failed three checks:
  - check 1: labelled `intended_concession`;
  - check 2: a one-move Roth-conversion match on `g_married_mid`;
  - check 4: a one-move match shifting income to a child on `g_parent_high`.
- `eitc_gate:eitc_inv+eitc_max1` found witnesses on `w_partners_high` at both magnitudes (three moves at ×2, two at ×4: moving a child to the other partner's return and giving that partner a bond holding). Both failed check 2, through matches one move shorter than the witness (at ×2 on `g_married_low`: giving half a bond holding to the spouse, then a Roth conversion), and both failed check 4. At ×2 the witness was also labelled `intended_concession`.
- Failed checks per magnitude: 1_witness 2, 2_grid 3, 4_spot 3.

**The plan's stop rule applies.** Spike 3 is the third spike. Its ≤ 1 of 10 passes, so under the plan (A5, gate G0) "the catalog stops, the build failure is reported as a finding, and H2 and H5 become exploratory on whatever families passed" (none passed). A5b does not run. A6 and A7 have no families to run on. Spike 3 was already a plan deviation (revision 3), so it could not have rescued G0 on its own terms. Its result only confirms the stop.

### Dense-pool diagnostic (2026-11-27; `experiments/diag/`, `results/a5/diag/`)

A diagnostic, not an experiment: it changes nothing in the gate, and it ran only on families already rejected. Its question: is the failure a search failure (the 30 witness households miss the regions where the mutations interact), or does the gain not exist?

The household pool was fixed before the diagnostic ran (`diag_pool.py`):
- 8 types (single or married, 0 to 3 children);
- 13 wage levels ($10k to $400k);
- 4 investment levels;
- 416 households in all.

Every reality-preserving grid sequence of one or two moves (516,490) is scored under current law and under the family's law at ×2 (PolicyEngine only). Every sequence with an attributable share ≥ 0.3 then gets the full interaction test.

| Spike-3 family (×2) | Households with an interacting sequence | Interacting sequences | One-move | Households where only two moves work |
|---|---|---|---|---|
| `eitc_gate:eitc_inv+eitc_max3` | 34 | 6,568 | 211 | 13 |
| `eitc_gate:eitc_inv+eitc_max1` | 32 | 1,655 | 70 | 10 |
| the other 8 | 0 | 0 | 0 | 0 |

Reading:
- **For 8 of 10, no gain to find exists.** Neither the generic witness households nor a pool 14 times larger has any interacting sequence of one or two moves. These mutations need facts the pools do not hold, such as filers over 64 (`eitc_age`), business income (`qbi_*`), dependents with earnings (`dep_std_cap`), or binding AMT (`amt_max`). For `ctc_phase_out` the two changes simply add up.
- **For the 2 EITC investment-limit families, the interaction exists but is shallow.** Interacting sequences appear on 32–34 households. On 10–13 of them, only two moves work: for example, gifting half a bond holding to a child and then converting part of an IRA to a Roth. On other households, one move does it (gifting the bond alone). Under the counting rule, which tests every single move of every interacting sequence found, both families are shallow.
- **Depth is a property of a law and a household together, not of the law alone.** Under the gate as written, a family counts only if no household anywhere reaches it in one move. With mutations that rescale parameters ordinary households already sit near, some household nearly always does. The rule is kept as written. The user decides on any change.

### Census of the next candidates (2026-11-27, before it ran)

This turns the failure into a measured finding on more than 10 families. The next 20 valid v5 candidates in the seeded order (the first 20 A5b would have gated) get the same dense-pool scan at ×2 (`experiments/diag/diag_census.py`, output `results/a5/diag/census.jsonl`). It reports the same four counts per family. It is a description of the generator, not a gate. No candidate is selected, passed or gated by it, and A5b stays stopped.

### Per-household probe (2026-11-27, before it ran; exploratory)

The probe asks whether the two EITC investment-limit families would give usable targets if depth were judged per household, not over every household searched. It is evidence for a decision the user makes. It does not change the counting rule, and it gates nothing.
- **Households:** for `eitc_inv+eitc_max3`, all 13 dense-pool households where only two-move sequences interact at ×2. For `eitc_inv+eitc_max1`, the 6 such households printed in the run-2 log (the log prints at most 6 of the 10).
- **Magnitudes:** ×2 and ×4.
- **Witness:** the household's interacting two-move sequence with the largest attributable gain at that magnitude.
- **Checks reported:**
  - checks 1, 3 and 5 as in the gate;
  - one-move matches on the witness household itself;
  - one-move matches on the 9 gate archetypes (check 2 as written).
- **Script:** `experiments/diag/probe_instance.py`.

### Census: result (2026-11-27; `results/a5/diag/census.jsonl`)

Over the 30 v5 candidates scanned on the dense pool at ×2 (the 10 from spike 3 and the 20 from the census):

| Operator | Candidates | Any interacting sequence | One-move interacting somewhere | Some household needs exactly two moves |
|---|---|---|---|---|
| `eitc_gate` (investment limit × EITC amount, start or rate) | 7 | 7 | 7 | 7 (2–16 households each) |
| `ctc_phase_out` | 6 | 1 (`ctc_amt+ctc_ps.HEAD_OF_HOUSEHOLD`, 7 households) | 1 | 0 |
| `qbi_phase_in` | 9 | 0 | 0 | 0 |
| `amt_max` | 4 | 0 | 0 | 0 |
| `eitc_age` | 3 | 0 | 0 | 0 |
| `dep_std_cap` | 1 | 0 | 0 | 0 |

Reading:
- No candidate is deep under the counting rule. Every candidate with an interacting sequence also has a one-move interacting sequence on some household.
- The 22 candidates with no interaction at all act on facts the pool does not hold: business income, binding AMT, filers outside the EITC age band, or adult dependents.
- The eitc_gate operator is the only one that reliably creates an AND structure that moves can reach.
- This is a description of generator v5 on one fixed pool, not an estimate of how common interactions are in law.

### Per-household probe: result (2026-11-27; `results/a5/diag/probe_instance.jsonl`)

38 rows: 19 households × 2 magnitudes, for the two EITC families from spike 3.
- 5 rows had no interacting two-move sequence at that magnitude.
- **0 of the other 33 witnesses passed every check.** Failures by check:
  - check 1 failed on 32. The verifier labelled 20 `intended_concession`: the moves run through retirement contributions or Roth conversions. It labelled 12 `code_disagreement`: PolicyEngine and Tax-Calculator disagree on the gain. The one witness labelled `candidate` (`eitc_inv+eitc_max3` ×4, `d_s3_30k_i3`) had 15 one-move matches on its own household.
  - one-move matches on the witness household itself: 11;
  - one-move matches on the 9 gate archetypes: 11 (all for `eitc_inv+eitc_max1`; `eitc_inv+eitc_max3` had none at either magnitude);
  - checks 3 and 5 passed on all 33.
- Caveat: the witness was the household's largest-gain interacting sequence, chosen without regard to its label. A label-aware choice could do better. It was not tried here, because the probe's rules were fixed before it ran.

Reading: judging depth per household would not by itself have produced families here. The binding checks were the witness label and one-move routes. The 12 calculator disagreements on gift-to-child EITC strategies are worth noting for H4.

## Hand-authored catalog (plan deviation, 2026-11-27)

**Decision (the user, in chat, 2026-11-27).** After the stop rule, the user chose to build planted loopholes by hand instead of with a generator. The user accepted three risks: the author is an AI, new rules must be implemented in both calculators, and this is a plan change. This deviation is reported wherever A5 is reported. Everything below was fixed before any code for it ran.

**What carries over unchanged:** the gate (all five checks, R = 0.1, witness share 0.3, $50 floor), the counting rule (≥ 2 moves at both magnitudes; one-move families are shallow), the witness search (v2), the 9 gate archetypes, the verifier and its whitelist, and the split rule.

**What is new:**
- **Base law B.** Real current law plus two planted provisions, written like statute and modelled on real anti-abuse and low-income rules. They are implemented in this package on top of each calculator's own results (as Form 8615 already is). The verifier tags gains from them as shared-code, because the cross-check cannot vouch for them.
  - **Donor attribution of recent gifts** (analogue s.644; assignment of income). A long-term gain realized on property received as a gift from a household member, in the year of the gift or the next year, is taxed to the donor: it moves to the donor's return.
  - **Small-investor credit** (modelled on the saver's credit, s.25B). It is 10% of the return's realized long-term gains up to $10,000. It is nonrefundable, limited to the income tax left after all other credits, and available only where AGI ≤ the saver's-credit AGI limit for the filing status and year. That limit is taken from PolicyEngine's parameters: the joint limit, × 0.5 for single and separate returns, × 0.75 for head of household. It is not available to a filer who is claimed as a dependent (s.25B(c)(2)(B)).
- **Reference law.** For a planted family, the attributable gain is the gain under L minus the gain under B, not current law. B is the law before the flaw. Without this, ordinary use of a new provision would count as a loophole.
- **Family structure.** Each family is one flaw made of two changes, c1 and c2. Each change relaxes one guard, and the guards sit in series on one exploit path, so either guard alone blocks it. L1 = B + c1, L2 = B + c2, L = B + both. There are two magnitudes, f = 0.5 and f = 1, where f sets the size of the relaxed benefit. Lrev makes an intended provision more generous with the guards intact (the plan's wording for check 5).
- **Witness pool.** The 30 witness archetypes, plus any household the author adds for a family. The plan's A5 wording allows households "with the relevant facts". Every household added is recorded with its family.

**Pilot (3 families):**

| id | mechanism | c1 | c2 | intended exploit |
|---|---|---|---|---|
| `h:kid_gain` | income shifting | the kiddie tax ignores a share f of a child's realized long-term gains | donor attribution removed | gift appreciated property to a child, who sells it (child's 0% rate) |
| `h:kid_credit` | income shifting via a credit | dependents get the small-investor credit at f × its amount | donor attribution removed | gift to a child, who sells; the credit offsets the child's tax |
| `h:kid_gain_timing` | timing | as `h:kid_gain` | donor attribution covers only the gift year | gift in one year, child sells in the next |

Lrev: for `kid_gain` and `kid_gain_timing`, the kiddie-tax allowance × (1 + f); for `kid_credit`, the credit rate × (1 + f).

**Integrity rules for the hand-authored catalog:**
- Every design, version and gate outcome is recorded.
- A design that fails the gate is not edited. A replacement gets a new id, and the number of attempts is reported.
- Designs never change after any search result from Phase B or C.
- Parameter values come from real-law analogues (above). They are never tuned to the archetype households.
- **Pilot decision rule:** if ≥ 2 of 3 pass, the full catalog is written under these rules (≥ 20 families, ≥ 4 mechanisms). If fewer pass, report and wait for the user.
