# law-verifiers

Red-teaming US household tax law with AI agents, using existing tax
calculators as an exact verifier.

- Research plan: [`us-tax-red-teaming-research-plan.md`](us-tax-red-teaming-research-plan.md)
- Experiment plan: [`experiment-plan.md`](experiment-plan.md)
- Findings log: [`results/FINDINGS.md`](results/FINDINGS.md) (Phase 0 first pass: [`results/phase0/FINDINGS.md`](results/phase0/FINDINGS.md))
- Pre-registration draft (E0.8): [`preregistration-draft.md`](preregistration-draft.md)

## What is here

```
src/taxred/
  household.py   Household / Person / Asset / TaxUnit model; compile_filing_units; economic snapshot
  moves.py       the action vocabulary (research plan §5.2) + contribute_retirement; wash-sale rule
  law.py         Law versions, kiddie-tax rule versions, provision registry (intended / anti_abuse / other)
  engines.py     PolicyEngine-US and Tax-Calculator adapters (batched)
  taxes.py       evaluate households under a law; kiddie tax (Form 8615), implemented here
  verifier.py    the verifier stack: gain, reality check, cross-check, attribution, labels (decide_label)
  matching.py    rediscovery matching rule (closure test, signature Jaccard)
  cases.py       historical-closure set (E0.5) and seed known current-law strategies
  planning.py    legitimate-planning set and labelled negatives (E0.6)
  planted.py     planted-loophole variants, plain and disguised (E2.1)
  search.py      random / greedy proposers and the batched search loop (E1.4, E2.3 baselines)
  generate.py    archetypes and a seeded random household generator
experiments/
  e0_1_agreement.py     E0.1 calculator agreement baseline
  e0_3_throughput.py    E0.3 verifier throughput benchmark
  e0_6_legit.py         E0.6 false positives on legitimate planning + E1.2 check ablation
  e0_7_matching.py      E0.7 matching-rule (closure test) validation on planted variants
  e1_closures.py        E1.1 H1 on the historical-closure set
  e1_kiddie_pilot.py    E1.1 pilot: kiddie-tax closures, dose-response (superseded by e1_closures)
  e1_4_search_smoke.py  E1.4 random / greedy search against the verifier on current law
  e2_1_planted.py       E2.1 validate planted variants, measure reach
tests/
  test_known_answers.py E0.2 hand-computed known-answer tests
  test_cases.py         closure cases (pre/post TRA 1986 known answers), anti-abuse rule
  test_retirement.py    401(k) / IRA known answers, limits, wash sale
  test_moves.py         moves and economic-reality invariants
scripts/
  setup_vm.sh           clone/update + environment + tests on the experiment VM
  run_phase0.sh         run Phase 0 experiments and commit results
  run_phase1.sh         tests + E0.6/E1.2 + E1.1 + E1.4
  vm_run.sh             run one experiment in the background in a memory-capped scope
results/                experiment outputs (summaries committed)
```

**Memory on the VM.** Each worker holds a PolicyEngine system per cached
reform (`TAXRED_PE_CACHE`, ~0.6 GB each, plus ~1.5 GB base). Experiments cap
workers by available memory (`common.safe_workers`); run one experiment at a
time, through `scripts/vm_run.sh`.

## Quick start

```bash
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -e ".[dev]"
python -m pytest -q
```

```python
from taxred.household import Asset, Household, Person, TaxUnit
from taxred.law import Law
from taxred.verifier import Verifier

hh = Household("demo", 2024, "TX",
    {"p": Person("p", 45, wages=300_000, hours=2080,
                 assets=[Asset("bond", 400_000, 400_000, interest_yield=0.05)]),
     "k": Person("k", 10)},
    [TaxUnit("t", "p", dependents=["k"])])
moves = [{"op": "gift_asset", "giver": "p", "recipient": "k", "asset": "bond"}]

for kiddie in ["none", "current"]:
    v = Verifier(Law(2024).with_kiddie(kiddie)).evaluate(hh, moves)
    print(kiddie, v.label, round(v.gain), v.signature)
```

## Workflow

All code goes through GitHub: develop locally → push → `git pull` on the VM →
run there → copy result summaries back (scp) and commit them from the
development checkout (the VM has no push credentials).

```bash
# on the VM
bash scripts/setup_vm.sh          # first time: curl the script from GitHub, or clone and run it
bash scripts/run_phase0.sh        # Phase 0 (E0.1-E0.3, kiddie pilot)
bash scripts/run_phase1.sh        # Phase 1 (E0.6, E1.1, E1.2, E1.4)
bash scripts/vm_run.sh e2_1 python experiments/e2_1_planted.py --workers 6
```

## Verifier labels

| Label | Meaning |
|---|---|
| `invalid` | a move could not be applied |
| `no_gain` | net resources rose by less than the threshold |
| `benefit_cliff` | gain came from lower real income across a benefit phase-out |
| `sacrifice` | economic reality changed (income, hours, wealth) |
| `code_disagreement` | Tax-Calculator does not confirm the federal gain |
| `intended_concession` | gain explained by whitelisted (intended) provisions |
| `candidate` | everything else with a gain: a candidate loophole |

Coverage tag `two-calc` means ≥ 90% of the gain is federal income tax, so the
cross-check covers it; `single-calc` means part of the gain (payroll, state
tax, benefits) is seen only by PolicyEngine.

## Known limitations

- **Single tax year.** The plan's 3-year horizon is not yet implemented, so
  timing strategies (`realize_gain`) can only show same-year effects.
- **Kiddie tax is implemented in this package**, not in either calculator
  (neither models Form 8615). Its effect is therefore common to both
  calculators and not independently cross-checked; it is covered by
  known-answer tests instead. Not modelled: the earned-income support test
  for ages 18–23, and the Form 8814 election.
- **TAXSIM is not wired in yet.** It is unreachable from the development
  container's network; the adapter will be added and tested on the VM.
- **Benefits come from PolicyEngine only.** Benefit gains are `single-calc`.
- **Saver's credit is PolicyEngine-only** (Tax-Calculator takes it as an
  input); it is left out of the cross-check comparison and counts as
  `single-calc` gain.
- **Sales-tax deduction.** PolicyEngine's imputed sales-tax deduction is
  switched off so both calculators see the same SALT inputs (finding F6;
  `TAXRED_PE_SALES_TAX=1` restores it). State income tax is not yet passed
  to Tax-Calculator, so non-TX households with itemized SALT will differ.
- **No LLM search yet.** The VM has no model API keys; the search scaffold
  (`search.py`) runs the random and greedy baselines.
- Households from `generate.py` are synthetic draws, not survey microdata yet.
- `itemize_or_standard` forcing is passed to PolicyEngine only.
