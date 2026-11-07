# law-verifiers

Red-teaming US household tax law with AI agents, using existing tax
calculators as an exact verifier.

- Research plan: [`us-tax-red-teaming-research-plan.md`](us-tax-red-teaming-research-plan.md)
- Experiment plan: [`experiment-plan.md`](experiment-plan.md)
- Phase 0 findings so far: [`results/phase0/FINDINGS.md`](results/phase0/FINDINGS.md)

## What is here

```
src/taxred/
  household.py   Household / Person / Asset / TaxUnit model; compile_filing_units; economic snapshot
  moves.py       the action vocabulary (research plan §5.2)
  law.py         Law versions, kiddie-tax rule versions, provision registry (for attribution)
  engines.py     PolicyEngine-US and Tax-Calculator adapters (batched)
  taxes.py       evaluate households under a law; kiddie tax (Form 8615), implemented here
  verifier.py    the verifier stack: gain, reality check, cross-check, attribution, labels
  matching.py    rediscovery matching rule (closure test, signature Jaccard)
  generate.py    archetypes and a seeded random household generator
experiments/
  e0_1_agreement.py     E0.1 calculator agreement baseline
  e0_3_throughput.py    E0.3 verifier throughput benchmark
  e1_kiddie_pilot.py    E1.1 pilot: kiddie-tax closures, dose-response
tests/
  test_known_answers.py E0.2 hand-computed known-answer tests
  test_moves.py         moves and economic-reality invariants
scripts/
  setup_vm.sh           clone/update + environment + tests on the experiment VM
  run_phase0.sh         run Phase 0 experiments and commit results
results/                experiment outputs (summaries committed)
```

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

All code goes through GitHub: develop in the cloud container → push →
`git pull` on the VM → run → commit results from the VM.

```bash
# on the VM
bash scripts/setup_vm.sh          # first time: curl the script from GitHub, or clone and run it
bash scripts/run_phase0.sh        # PUSH=1 to push results back
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

## Known limitations (Phase 0)

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
- Households from `generate.py` are synthetic draws, not survey microdata yet.
- `itemize_or_standard` forcing is passed to PolicyEngine only.
