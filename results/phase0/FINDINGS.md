# Phase 0 findings (development container, first pass)

Status: preliminary. Everything below came from the development container (4 CPUs, 15 GB). Full-scale runs happen on the VM (`scripts/run_phase0.sh`). Versions: policyengine-us 1.x / Tax-Calculator 6.x (exact versions are in each `summary.json`).

## F1. Neither calculator models the regular kiddie tax (Form 8615)

- **PolicyEngine-US** models only the AMT child exemption rule (`amt_kiddie_tax_applies`), not Form 8615.
- **Tax-Calculator** has no kiddie-tax parameter or logic.
- **What we did:** the kiddie tax is implemented in this package (`taxred/taxes.py::apply_kiddie_tax`), including siblings' combined NUI and pro-rata allocation. Law versions are `none`, `tra1986`, `tipra2005` and `sbwota2007` (`taxred/law.py`). A hand-computed known-answer test pins it: the child owes $6,220 in `tests/test_known_answers.py`.
- **Consequence for the research design.** The plan's anchor case (research plan §5.3) can only be represented by formalizing law ourselves, which is the bottleneck the project meant to avoid. Its effect is also common to both calculators, so the two-calculator cross-check does not cover it. **H1 results on this case partly test our own implementation.** Other historical cases need the same check (E0.4) before they are treated as independent tests of the verifier.

## F2. PolicyEngine drops a dependent's income inside the parent's tax unit

If a dependent with $20k of interest is placed in the parent's PolicyEngine tax unit, the interest appears on no return (the unit's AGI excludes it) and nothing is taxed. An agent would find this immediately ("gift assets to your child"): a calculator gap, not a loophole in the law.

- **What we did:** `compile_filing_units` gives every dependent with income their own return in both calculators. A test pins the PolicyEngine behaviour.

## F3. PolicyEngine misses the child AMT exemption limit

A child with $20k of interest and no kiddie tax:

- **PolicyEngine:** $2,012 (regular tax only).
- **Tax-Calculator:** $2,795 (adds AMT; the exemption is limited to earned income + $9,250). Tax-Calculator is right.

This is recorded as a strict `xfail` known-answer test. In the pilot, the cross-check catches it: low-income parents with large gifts show `code_disagreement`, because PolicyEngine reports a gain while Tax-Calculator reports a loss. **This is the first concrete H4 evidence:** an agent rewarded on PolicyEngine alone would be paid for a calculator gap.

## F4. Tax-Calculator's current law contains a random EITC/ACTC take-up model

- **The model:** `eitc_claim_prob_*` and `actc_claim_prob_*` drop the credit for some records, using a per-record random draw seeded by **row position**.
- **The effect:** the same return got EITC in one batch position and not in another. In early pilot runs this produced spurious cross-check failures.
- **What we did:** the adapter sets both claim-probability scales to 9e99 (everyone claims), and `tests/test_engines.py` checks that results don't depend on batch position.
- **For any project using Tax-Calculator as a verifier:** its default "current law" is not deterministic statutory law.

## F5. Calculator year coverage

- Tax-Calculator covers 2013 onward.
- Many PolicyEngine parameters start in 2018; the dependent standard-deduction floor, for example, has no values before 2018.
- The 1986/2005/2007 kiddie-tax closures are therefore encoded as **counterfactual reforms on 2024 law**, not as period law.
- TAXSIM, the only calculator spanning earlier years, is blocked by the development container's network. Its adapter is still to do, and it will run on the VM.

## F6. PolicyEngine imputes a sales-tax deduction

With no expenses entered, PolicyEngine still imputes an itemized state/local sales-tax deduction from income ($382 for a child with $5k of interest in TX). Tax-Calculator does not. This matters for itemizers and for counterfactuals that remove the standard deduction, and it is a source of `single-calc` gain.

## F7. Engineering: PolicyEngine reforms are expensive

- **Time:** building a reformed tax-benefit system takes ~16 s. `Simulation(reform=...)` rebuilds it on every call; the adapter caches one system per reform (0.1 s per simulation afterwards).
- **Memory:** ~1.5 GB for the base system plus ~0.6 GB per cached reform, which caused OOM kills with 4 workers in 15 GB. Workers should be sized at about 7 GB each.
- **Throughput (E0.3, one process, no attribution):**

  | Batch size | Proposals/s |
  |---|---|
  | 1 | ~0.5 |
  | 50 | ~13 |
  | 200 | ~44 |

  Attribution multiplies cost by the number of provisions plus 1.

## E1.1 pilot: kiddie-tax dose-response (`results/phase1/kiddie_pilot/`)

**Setup:** 84 households × 4 law versions. The strategy is to gift an interest-bearing bond to a dependent child.

| Measure | Result | H1 target |
|---|---|---|
| Flag rate, child not covered by the law version | **100%** | ≥ 90% ✔ |
| Flag rate, child covered | **82%** | ≤ 10% ✘ |
| Gain drops at exactly the right closure for each age group | **yes**: 8 and 13 at TRA 1986, 16 at TIPRA 2005, 18 and students at SBWOTA 2007, never for a 20-year-old non-student | — |

**Why the post-closure flag rate is high.** The residual gain under each closure is real and comes from other provisions:

- **The kiddie-tax allowance (intended).** The first $2,600 is outside NUI: $1,300 standard deduction plus $1,300 at the child's rate. This gives a $442 gain for a 22–24% parent. Joint attribution of intended provisions explains about 80% of it. The rest is partly the F6 sales-tax imputation in the counterfactual.
- **NIIT avoidance (real, current law).** The 3.8% NIIT is computed on the child's own MAGI, so shifting investment income to a child avoids it even under the kiddie tax. This explains 20–46% of high-income residuals.
- **CTC phase-out avoidance (real, current law).** The child's NUI does not count toward the parent's AGI, so the parent can drop below the CTC phase-out. This explains 20–30% of the residual for $400k married parents (measured with the `ctc` provision switched off).
- **EITC investment-income limit avoidance (real; mechanically whitelisted).** A low-income parent who gifts the asset falls under the EITC investment-income limit. Because EITC is on the intended list, this is labelled `intended_concession`. That is wrong: it circumvents the anti-abuse rule. Provision-level whitelisting is too coarse here.

**Implication for H1 and the matching rule.** A real strategy usually touches several provisions, so "≤ 10% of post-closure cases flagged" is mis-specified. **Proposed amendment, for pre-registration (E0.8):** measure H1 on the *closed mechanism*. The share of gain removed by the closure reform should be

- \> 0 before the closure, and
- = 0 after it (the closure is already in force),

and the residual should be reported, decomposed by provision. The 80% reduction threshold in the matching rule is also too high: median reductions in the pilot are 46–48%. Set it from E0.7 instead.

## Open items before the full Phase 0 run

1. A TAXSIM adapter (on the VM).
2. A PolicyEngine enhanced-CPS household loader to replace synthetic draws.
3. A multi-year horizon.
4. The remaining historical cases (E0.4/E0.5): which ones can each calculator express *without* package-side law?
5. Re-scoping the intended-concession whitelist, e.g. "EITC claimed on unchanged facts" vs "EITC gained by moving assets".
