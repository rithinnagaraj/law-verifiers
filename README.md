# taxgap (v2)

Verifier-guided search for gaps in US household tax rules as encoded in
PolicyEngine-US and Tax-Calculator. Written from scratch for
[`research-plan-v2.md`](research-plan-v2.md) and
[`experiment-plan-v2.md`](experiment-plan-v2.md); the v1 code and results
are on branch `docs/experiment-plan`, and what v1 taught us is in
[`NOTES-v1.md`](NOTES-v1.md).

## Layout

| Path | What |
|---|---|
| `src/taxgap/model.py` | households, people, assets, tax units, futures; returns |
| `src/taxgap/law.py`, `params.py` | laws as parameter changes for both calculators; provisions (whitelist, anti-abuse) |
| `src/taxgap/calc/` | PolicyEngine and Tax-Calculator adapters, Form 8615, batched memoized evaluation |
| `src/taxgap/moves.py` | move vocabulary, bright-line rules, 3-year horizon with futures |
| `src/taxgap/verifier.py` | gain, reality, cross-check, whitelist, labels |
| `experiments/` | one script per experiment ID (A1 ... A7) |
| `scripts/` | VM setup and the memory-capped runner |

## Running on the VM

```
bash scripts/vm_setup.sh                       # once
bash scripts/vm_run.sh a2 .venv/bin/python experiments/a2_noise_floor.py
```

Results go to `~/taxgap-results/<id>/`; summaries are copied into
`results/<id>/` in this repository.
