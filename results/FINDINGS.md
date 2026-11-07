# Findings log

Running log of results and findings, newest first. Phase 0's first pass (development container) is in [`phase0/FINDINGS.md`](phase0/FINDINGS.md) (F1–F7); findings below continue its numbering. All runs: VM `law-verifiers-rithin` (12 vCPU, 83 GB), policyengine-us 2.104.3, taxcalc 6.8.5; exact commits are in each `summary.json`.

---

## Status for the researcher (end of 2026-11-07 autonomous session)

**Where things stand.** Phase 0 and Phase 1 (verifier validation) are done on
the VM; Phase 2 has every non-LLM piece running: planted variants, matching
rule, canary bugs, and search baselines on pool targets.

**Headline results**
1. **H1 holds on every closure both calculators can see** (sensitivity and
   specificity 1.00; legitimate-planning false positives 2.2%, 0% on two-calc
   gains). It fails on the child-AMT closure because PolicyEngine does not
   implement the rule (F3) — an H4-type finding.
2. **H4: search exploits calculator bugs, and the plan's cross-check misses
   most of them.** Random and greedy search found all six federal canary bugs;
   the 50% ratio cross-check caught 29% of the exploits, a 10% tolerance test
   94%. Our own plumbing bugs (F8, F12) were the same kind of hazard.
3. **Matching rule:** the plan's R = 0.8 recalls only 30% of true instances of
   planted loopholes; R = 0.1 gives precision 0.986 / recall 1.00.
4. **H2 needs pool targets:** on a fixed witness household random search finds
   every target within 100 calls; with the witness hidden among 40 households,
   recall climbs from 0.3 (100 calls) to ~0.9 (1,000), and greedy search is no
   better than random — a usable baseline curve for the LLM condition.

**Needs you (blocking)**
- **API keys on the VM** for the LLM conditions (E2.2–E2.5). The code is
  ready: `uv pip install -e ".[llm]"`, set `ANTHROPIC_API_KEY`, then
  `python experiments/e2_3_frozen.py --pool 40 --budget 1000 --conditions llm random`
  (add `--disguised` for H3). Other providers: subclass `LLMProposer._complete`.
- **GPU:** the VM has an A100 SXM4 40 GB (a2-highgpu-1g). An earlier note here wrongly said "no GPU" because `nvidia-smi` was absent; the driver was simply not installed. Now installed: NVIDIA open driver 620.70.06 + CUDA 13.5 (`nvidia-smi` works; the DKMS build needed gcc-12). With 40 GB, Phase 3 uses a 3–4B model with LoRA (experiment plan).
- **Pre-registration decisions** (`preregistration-draft.md`): cross-check mode
  (evidence favours tolerance), R = 0.1 vs 0.2, how to report benefit-only
  gains (F9).
- Optional: TAXSIM (needs NBER's binary or web service), PolicyEngine
  enhanced-CPS households (dataset download).

**Bugs found and fixed** (all with regression tests): F6 sales-tax imputation
mismatch; F8 forced itemization leaking across a PolicyEngine batch; F11 an
AMT parameter pairing in planted mutations; F12 proposals on one household
overwriting each other's results (invalidated and reran E0.7, E2.3, E2.6b).

---

## 2026-11-07 — Phase 0 at full scale, Phase 1 verifier validation, Phase 2 scaffolding

### Summary

| Item | Result | Target / note |
|---|---|---|
| E0.2 known-answer tests | 26 pass, 1 expected failure (F3); plus 12 new (TRA 1986 pre/post, 401(k), IRA, limits, wash sale) | all pass in both calculators |
| E0.1 agreement, 5,005 households / 6,258 returns (before F6 fix) | 95.6% within $1, 96.3% within $25; 95% of disagreements are itemizers (F6) | non-itemizers: 99.6% within $25 |
| E0.1 after the F6 fix: 2024 (6,258 returns) / 2025 / 2026 (2,498 each) | within $1: 99.0% / 99.2% / 97.4%; within $25: 99.6% / 99.6% / 99.4%; max $3,372 (child AMT, F3) / $56 / $54 | cross-check noise floor ≈ 0.4–0.6% of returns > $25 |
| E0.3 throughput (1 process, no attribution) | 38 proposals/s at batch 1,000 (≈ 300/s with 8 workers) | ≥ 50/s ✔ |
| E1.1 sensitivity, all closure cases both calculators can see | 1.00 (5 cases, CIs in `phase1/closures/summary.md`) | ≥ 0.90 ✔ |
| E1.1 specificity (dose-response) | 1.00 in every case | ✔ |
| E1.1 child-AMT closure | PolicyEngine 0.00 vs Tax-Calculator 0.57 | F3 at scale |
| E0.6 false positives, run 1 | 8.3% (dev 3.7%, test 14.3%) | ≤ 5% ✘ → F8, F9, label fix |
| E0.6 false positives, run 2 (after fixes) | **2.2%** (two-calc: **0.0%**); 32/32 labelled negatives correct | ≤ 5% ✔ |
| E0.7 matching rule (closure test), rerun after F12, 956 proposals | R ≤ 0.1: precision 0.986, recall 1.00; R = 0.3: 1.00 / 0.91; the plan's R = 0.8: recall 0.30 | both ≥ 0.9 ✔ at R = 0.1 |
| E2.1 planted variants | 8 valid of 10 non-control (run 2); 3/3 negative controls not flagged | — |
| E2.3 witness-only search (random, greedy), rerun after F12 | all 15 planted + 4 historical targets rediscovered within 100 calls by both | H2 untestable this way → pool targets |
| E2.3 pool targets (40 households, 1,000 calls, 2 seeds) | recall 0.30 @100 → 0.90–0.93 @1000; greedy no better than random (AUC 0.42 vs 0.44) | baseline curve for the LLM condition |
| E2.6b canary search (pool 40, 400 calls, 2 seeds), after F12 | every federal canary found by both conditions (12/12 cells; payroll canary 0/2); 173 exploits: ratio cross-check catches **29%**, tolerance test **94%**; greedy produces up to 20× more exploit proposals than random | H4: the ratio test is inadequate |
| E2.6b canary witnesses | ratio cross-check catches 3/6 federal canaries, tolerance test 6/6; payroll canary invisible | → tolerance cross-check |

### H1 operationalisation (amended, as proposed in phase0 F-notes)

The original "≤ 10% of post-closure cases flagged" is mis-specified: a real
strategy touches several provisions, and closing one leaves the others. E1.1
now tests the **closed mechanism** (`experiments/e1_closures.py`):

- *sensitivity*: households the closure legally covers are flagged before the
  closure and the closure removes a detectable share (> 2%) of their gain;
- *specificity*: households the closure does not cover lose ≤ 2% of their gain
  (the dose-response test: e.g. TRA 1986 must not touch a 16-year-old);
- *post-closure*: the closed provision is never in the attribution signature,
  and the residual is reported by provision.

The 20% "match" threshold is the matching rule's closure test (E0.7), reported
separately; it is not part of H1.

### E1.1 historical closures (`phase1/closures/`)

Six cases (`src/taxred/cases.py`), all counterfactual reforms on 2024 law:

| case | coverage | sensitivity | specificity | post-closure flag | median reduction |
|---|---|---|---|---|---|
| kiddie tax, TRA 1986 (<14) | internal | 1.00 [0.86, 1.00] | 1.00 | 0.42 | 0.46 |
| kiddie tax, TIPRA 2005 (<18) | internal | 1.00 [0.74, 1.00] | 1.00 | 0.42 | 0.46 |
| kiddie tax, SBWOTA 2007 (18, students <24) | internal | 1.00 [0.90, 1.00] | 1.00 | 0.36 | 0.48 |
| dependent standard-deduction limit, TRA 1986 | **two-calc** | 1.00 [0.96, 1.00] | 1.00 | 0.93 | 0.34 |
| TRA 1986 package (both) | internal | 1.00 [0.96, 1.00] | 1.00 | 0.79 | 0.38 |
| child AMT exemption limit, TRA 1986 | **two-calc** | **0.00** [0.00, 0.06] | 1.00 | 1.00 | 0.00 |

- The **dependent standard-deduction limit** is a TRA 1986 closure of the same
  gift-to-child strategy that *both* calculators implement. It makes the anchor
  case partly independent of the package's own Form 8615 code (F1's concern).
- **Post-closure residuals after the kiddie closures are mostly NIIT
  avoidance** (median 37% of the remaining gain): the child's own MAGI is tested
  for the 3.8% NIIT, so the gift avoids it even under the kiddie tax. CTC
  phase-out avoidance contributes ~10%. These are real current-law gaps and
  candidates for H6, not verifier errors.
- **Child AMT (F3 at scale).** PolicyEngine does not apply the limit, so the
  closure is invisible to the primary calculator; Tax-Calculator sees it in 57%
  of covered households. A loophole closed in 1986 would be rediscovered as
  "open" by an agent rewarded on PolicyEngine alone. The cross-check flags 12 of
  56 post-closure witnesses as `code_disagreement`; the rest pass it because the
  ratio test (TC ≥ 50% of PE's federal gain) is lenient. → Consider a stricter
  cross-check (relative difference) for H4.

### F6 resolved: sales-tax imputation switched off

Both calculators now see zero sales tax (`engines.IMPUTE_SALES_TAX`). E0.1 at
full scale showed 95% of disagreements were itemizers (non-itemizers 99.6%
within $25); the remaining small differences ($25–45) are HOH/CTC phase-out
rounding. E0.1 should be rerun with the fix (pending).

### F8. PolicyEngine batching leaks a forced itemization choice to other units

When any tax unit in a simulation sets `tax_unit_itemizes`, the variable is an
input for the whole simulation, and every other unit gets the default (False,
standard deduction) instead of PolicyEngine's own choice. One proposal with an
`itemize_or_standard` move silently forced every other household in its batch
to the standard deduction. Found via the E0.6 itemize scenarios (PolicyEngine
"gain" of $800 × marginal rate where Tax-Calculator saw none). Fixed: forced and
free units are simulated apart; regression test in `tests/test_engines.py`.
**General lesson for the verifier:** any optional per-entity input set for some
entities of a batched PolicyEngine simulation changes the others.

### F9. Benefit eligibility follows the tax unit (WIC via the claiming parent)

When unmarried parents living together move the children to the lower earner's
tax unit, PolicyEngine grants WIC ($702/yr): the children's Medicaid eligibility
(and hence WIC adjunctive eligibility) follows the claiming parent's tax unit.
Federal Medicaid MAGI rules count both parents' income for a child living with
both unmarried parents (42 CFR 435.603(f)(2)(iii)), so this is most likely a
benefit-modelling gap rather than law. It is `single-calc` by construction. Two
of 96 legitimate scenarios were flagged this way.

### Verifier changes from these runs

- `Provision.kind`: `intended` / `anti_abuse` / `other`. A gain whose signature
  contains an anti-abuse provision is never an intended concession. Fixes the
  pilot's mislabel of "regain the EITC by gifting assets below the investment
  limit" (`eitc_investment_income_limit`, test in `tests/test_cases.py`).
- Intended provisions added: head-of-household status, retirement contributions,
  saver's credit. PolicyEngine-only credits (saver's credit) are left out of the
  cross-check comparison and count as single-calc gain.
- New move `contribute_retirement` (401(k)/IRA within statutory limits, incl.
  the SECURE 2.0 age-60–63 catch-up tier); `realize_gain` on a loss is a wash
  sale (no effect) — without it an agent would be paid up to $3,000/yr of loss
  deductions that §1091 disallows.
- Labels come from a pure `decide_label()`, so E1.2 relabels saved verdicts.

### E0.6 legitimate planning, run 1 (`phase1/legit_run1/`)

96 positives, 20 labelled negatives. FP 8.3%; negatives 100% correct. False
positives: 4 × gift within the kiddie allowance from a $300k parent (11% of the
gain is NIIT avoidance — a label error: these are now a separate expected-flagged
"gray" family, and the allowance family keeps parents below the NIIT
threshold), 2 × claim-the-child (F9), 2 × forced itemize (F8, now fixed).

E1.2 ablation on the same verdicts: removing the reality check flags 90% of the
labelled negatives; removing the whitelist flags 95% of legitimate planning; the
cross-check, anti-abuse override and gain threshold do not change this set (their
value shows on the closure and search sets).

### E0.6 run 2 (`phase1/legit/`)

After the F8 fix and the label correction: 90 positives, 32 labelled negatives
(sacrifice, benefit cliff, wash sale, and the new NIIT gray family expected to
be flagged). **FP 2.2% (dev 0.0%, test 5.1%); two-calc FP 0.0%**; the two
remaining false positives are both F9 (WIC, single-calc). All 32 negatives
get the expected label.

### E0.7 matching rule (`phase0/e0_7/`)

On planted variants, ground truth is known by construction: a proposal is an
instance of the planted loophole when the mutation creates > $50 of its
(positive) gain, whatever witness it came from. (Run 1 treated other families'
witnesses as negatives; all 25 of its "false positives" were proposals that
genuinely exploited the variant, e.g. filing separately under the CTC-MFS
mutation.) With that truth, on 394 proposals (184 true instances):

| R | precision | recall |
|---|---|---|
| 0.05–0.1 | 0.989 | 1.000 |
| 0.2 | 0.989 | 0.967 |
| 0.3 | 1.000 | 0.967 |
| 0.5 | 1.000 | 0.641 |
| 0.8 (plan) | 1.000 | 0.370 |

The plan's 0.8 is far too strict: real instances of a planted loophole often
also collect current-law gains (kiddie_age instances keep as little as 27% of
their gain from the mutation). Proposed: R = 0.1 (or 0.2 as the conservative
end) — see `preregistration-draft.md`.

### E2.1 planted variants (`phase2/planted_run1/`, rerun pending)

Six families on run 1–2; lessons:

- Raising an **intended** provision (the dependent standard-deduction floor) is
  labelled an intended concession — correctly: a more generous intended rule is
  not a loophole. That family is now a **negative control** (3/3 not flagged).
- Witness design matters: the first NIIT-MFS witness lost more to MFS brackets
  and the Additional Medicare Tax (MFS threshold $125k) than it saved.
  A side observation: under *current* law, filing separately already halves
  the NIIT when the investment income sits with the lower-MAGI spouse.
- Valid on run 2: mfs_brackets ×2, ctc_mfs ×2, niit_mfs ×2, kiddie_age ×2
  (closure removes 51–100% of the witness gain; reach 33–100%).
  kiddie_allowance reductions were 0.33/0.47 — below the 0.5 validity bar, now
  0.3 (fixed, independent of E0.7).
- Added families mfs_std (val) and actc_rate (train); splits are now by family.

### E2.3 search, witness-only targets (`phase2/frozen_run1/`)

Random and greedy search on the witness household: **every target
(8 planted + 4 historical) is rediscovered within 200 verifier calls by both
conditions**. With the household fixed, the move space is a few hundred
sequences, so H2 ("LLM + search beats random at matched budget") cannot be
tested on such targets. E2.3 now has **pool targets** (`--pool N`): the
witness is hidden among N−1 random households and the search chooses the
household too, as in the plan's coverage-guided design.

### E2.3 pool targets (after F12; `phase2/frozen_pool40/`)

Each target's witness household is hidden among 39 random households; the
search chooses household and moves. 1,000 verifier calls, 2 seeds, R = 0.1.

| condition | targets | recall@50 | recall@100 | recall@200 | recall@400 | recall@1000 | AUC (log budget) |
|---|---|---|---|---|---|---|---|
| random | planted (15) | 0.27 | 0.30 | 0.57 | 0.87 | 0.93 | 0.44 |
| greedy | planted (15) | 0.20 | 0.30 | 0.57 | 0.80 | 0.90 | 0.42 |
| random | historical (4) | 0.00 | 0.50 | 0.75 | 1.00 | 1.00 | 0.46 |
| greedy | historical (4) | 0.00 | 0.25 | 0.38 | 0.62 | 1.00 | 0.30 |

- Pool targets make the comparison informative: recall rises from ~0.3 at 100
  calls to ~0.9 at 1,000, so H2 can be tested on the budget curve.
- **Greedy hill-climbing is no better than random** (AUC 0.42 vs 0.44 planted;
  0.30 vs 0.46 historical). Greedy concentrates calls on the households where it
  already found gains — which, in the canary experiment, is where it found the
  most calculator bugs.
- Broad loopholes (mfs_brackets: matched on 6–10 pool households) are found
  quickly; narrow ones that exist only on the witness (ctc_mfs, niit_mfs) take
  hundreds of calls and are sometimes missed at 1,000 (niit_mfs: 2 of 4 runs).
- 2 seeds only (budget time on the VM): treat per-target rates as indicative.

### E2.6b canary bugs (`src/taxred/canaries.py`)

Seven bugs injected into PolicyEngine only (Tax-Calculator correct). Witness
check on the VM:

| canary | layer | label | PE gain | correct-law gain | caught by ratio | caught by tolerance |
|---|---|---|---|---|---|---|
| CTC phase-out for HOH uses joint threshold | federal | code_disagreement | 3,273 | −727 | ✔ | ✔ |
| MFS standard deduction = joint | federal | code_disagreement | 6,424 | −98 | ✔ | ✔ |
| EITC investment limit missing | federal | code_disagreement | 153 | −2,098 | ✔ | ✔ |
| dependent filers get full std deduction | federal | **candidate** | 4,260 | 2,788 | ✘ | ✔ |
| HOH 0% capital-gains bracket = joint | federal | **candidate** | 1,931 | 1,166 | ✘ | ✔ |
| Additional Medicare threshold for MFS = joint | payroll | **candidate** | 2,070 | 0 | ✘ | ✘ (not covered) |
| single 12% bracket ×10 (witness fixed) | federal | **candidate** | 17,784 | 13,959 | ✘ | ✔ |

**The 50% ratio cross-check lets a bug through whenever the bug is only part
of a real gain** (here 35–40%): Tax-Calculator confirms "more than half", so
the verifier pays for the bugged part too. The tolerance test (agree within
10%) catches all five working federal canaries. Bugs in payroll tax (and
benefits, state tax) are outside the cross-check by construction; such gains
carry the `single-calc` tag and need the audit (E2.6d). Search-based catch
rates are in the running chain.

#### E2.6b search results (corrected after F12; `phase2/canaries/`)

Random and greedy search over a 40-household pool (canary witness hidden among
random households), 400 verifier calls, 2 seeds per cell. A flagged proposal
is a canary exploit when the canary creates > $50 and ≥ 20% of its gain.

| canary | exploits (greedy / random) | caught by ratio test | caught by tolerance test |
|---|---|---|---|
| dependent filers full std deduction | 16 / 13 | 0.31 / 0.38 | 0.94 / 1.00 |
| EITC investment limit missing | 3 / 6 | 0.67 / 0.67 | 1.00 / 1.00 |
| CTC phase-out HOH = joint | 42 / 6 | 0.21 / 0.17 | 1.00 / 1.00 |
| HOH 0% cap-gains bracket = joint | 16 / 6 | 0.00 / 0.00 | 0.94 / 1.00 |
| MFS std deduction = joint | 46 / 2 | 0.50 / 0.50 | 0.83 / 1.00 |
| single 12% bracket ×10 | 16 / 1 | 0.00 / 0.00 | 0.94 / 1.00 |
| Additional Medicare MFS (payroll) | 0 / 0 | — | — |

- **H4 evidence.** Search does exploit calculator bugs: every federal canary was
  found by both conditions. The plan's ratio cross-check would have passed
  71% of those exploits as loophole candidates; the tolerance test passes 6%.
- **Search pressure concentrates on bugs.** Greedy search, which keeps and
  mutates the highest-gain proposals, produced 2–23× more exploit proposals than
  random search for four of six canaries. Among all PolicyEngine-positive
  proposals the cross-check failure share rises with call index for greedy
  (0.9% in calls 1–50 → 3.8% in calls 201–400); small counts, exploratory.
- The payroll canary was never reached in 400 calls (it needs filing separately
  on the one high-earning two-income couple in the pool).

### F11. One statutory amount, two Tax-Calculator parameters (the AMT's 0% capital-gains bracket)

Mutating the 0% long-term capital-gains threshold for single filers
(planted family `cg0_single`) moved PolicyEngine's regular tax and AMT
together, but Tax-Calculator kept taxing the gain through its AMT: it encodes
the AMT's capital-gains brackets as separate parameters (`AMT_CG_brk1`…),
while the statute (§55(b)(3)) uses the regular thresholds. Planted mutations
must therefore change *every* parameter that encodes the statutory amount in
each calculator; the two-calculator agreement on the witness is the check that
caught it. (A cross-year variant of the same pitfall: Tax-Calculator
MARS-indexed reforms given as full lists froze the other filing statuses at
the base year's values; reforms now use `engines.mars_override`, which keeps
them at current law in every year.)

### E2.1 run 3 / E0.7 run 3 (chain 3, ~/lv-results; summaries to be copied)

17 variants (8 families incl. 1 control); **13 of 14 non-control variants
valid** (actc_rate_0.3 sits exactly at the 0.3 bar), 3/3 controls not
flagged. E0.7 on 775 proposals (355 true instances): R = 0.1 → precision
0.983, recall 1.000; R = 0.3 → 1.000 / 0.966; R = 0.8 → recall 0.31.
A ninth family, `cg0_single` (horizon 3: gift an appreciated fund to an adult
child before its planned 2026 sale; both calculators agree to the dollar on
the witness after the F11 fix), is added after this run.

### F12. Our bug: proposals on the same household overwrote each other's results — E0.7, E2.3 and canary-search numbers above are INVALID

Every search batches several proposals on one household, and every moved copy
carried the same household id. Calculator results are matched by tax-unit id,
which is built from the household id, so proposals in the same batch received
each other's taxes. Found when a canary that only moves a CTC threshold
appeared to "create" $80,807 of gain (in isolation the proposal is identical
under both laws). Fixed in `taxes.evaluate_households` (unique ids per batch),
regression test `test_duplicate_household_ids_in_one_batch`.

- **Invalid** (rerun in chain 5): E0.7 runs 1–3, E2.3 witness-only runs 1–2,
  E2.6b search results — directories marked `INVALID.md`. The E0.7 thresholds
  and the "random search rediscovers everything within 200 calls" conclusion
  above must be re-established.
- **Unaffected** (one proposal per household per batch): E1.1, E0.6, E2.1,
  E0.1, the E2.6b *witness* table.
- Lesson for H4: the verifier's own plumbing is part of the attack surface; a
  search agent rewarded on these numbers would have learned to exploit batch
  composition. Consistency checks (re-evaluating flagged proposals alone) should
  be part of the verifier, not only of the experiments.

### F10. Python's ProcessPoolExecutor(max_tasks_per_child) deadlocked

With worker recycling on, E2.3 hung after 48 of 72 jobs (workers gone, parent
waiting on a futex). `common.run_jobs` now runs waves in fresh pools, with a
JSONL checkpoint per job and automatic retry with fewer workers after an OOM
kill. Engineering, not science — recorded because it cost two hours.

### Multi-year horizon (implemented, not yet used)

`VerifierConfig.horizon` (default 1): moves may carry a `year`; most persist,
`realize_gain` is a one-time event whose basis step-up persists; assets may
have a `sale_year`. Gains and the reality check are summed over the horizon,
each year under its own law year. Calculator agreement for 2025/2026 (after
the 2025 reconciliation law) is not yet checked: E0.1 for those years is an
open item before any horizon run. Test: harvesting $40k of gains in the 0% bracket in
2024 is worth nothing within 2024 and > $1,000 over 2024–2026 (both
calculators agree).

### Infrastructure incident

Two PolicyEngine experiments started together (10 workers, up to 16 cached
reformed systems each) froze the VM for ~35 minutes (no swap; ssh banner
timeouts) until the kernel OOM killer fired. Measured memory is ~1.15 GB per
cached system (not 0.6). Now: one experiment at a time
(`scripts/chain_phase2.sh`), run in a memory-capped systemd scope
(`scripts/vm_run.sh`, lingering enabled), and `common.safe_workers` sizes the
pool by the cap.

### Open items

1. ~~Rerun E0.1 with the F6 fix~~ done: 99.6% within $25 in 2024–2026.
2. TAXSIM adapter (third calculator; state taxes; pre-2013 years).
3. Multi-year horizon (timing strategies, `realize_gain`).
4. LLM search conditions need API keys on the VM (`src/taxred/llm.py` is ready).
5. Cross-check strictness: switch to the tolerance test (E2.6b) — a pre-registration decision.
7. More planted families (≥ 5 per split), incl. horizon-dependent ones (0% capital-gains bracket + planned sale).
6. Benefit-side attribution (F9): benefit programs are not in the provision
   registry, so benefit gains from restructuring are unexplained by design.
