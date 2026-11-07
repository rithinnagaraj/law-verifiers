# Research Plan: Red-Teaming US Household Tax Law with AI Agents

**Status:** Draft v0.1 · **Scope:** US federal (and where modeled, state) household tax and benefit rules only

---

## 1. Summary

AI agents improve fastest in domains where their outputs can be checked automatically. Tax law is usually treated as unverifiable: whether a strategy is a "loophole" is decided by expensive experts, often years after the fact. The US is an exception because it already has mature, open-source, hand-built models of its household tax and benefit rules. This project uses those models as an exact, fast verifier, and asks how well AI agents can find loopholes against it, and whether training against it improves that ability.

Prior work either has LLMs reason about tax strategies in text and relies on expert grading (Blair-Stanek et al., 2025), or has an LLM formalize the law first, which the authors identify as the main bottleneck (Fratrič et al., 2025). We skip the formalization bottleneck by using existing, tested formalizations, and we validate the verifier against loopholes that Congress has already closed.

---

## 2. Main research question

> **When AI agents are given an exact, independently cross-checked verifier of US household tax law, can they find real loopholes — rediscovering historically closed ones and surfacing candidates that survive expert review — and does training against the verifier produce a loophole-finding skill that transfers to laws the model has never seen?**

### Sub-questions

- **RQ1 (Verifier):** Can a programmatic verifier built on existing tax calculators reliably separate loopholes from both real economic sacrifices and intended tax incentives?
- **RQ2 (Frozen search):** How many known household tax strategies do frontier models rediscover when paired with a search procedure, and is that search or memory?
- **RQ3 (Reward hacking):** How often do agents exploit the calculator's code instead of the law, and how much of that does the cross-check catch?
- **RQ4 (Training):** Does reinforcement learning on law variants with planted loopholes improve an open model's recall of real, held-out loopholes?

---

## 3. Definitions

| Term | Operational definition |
|---|---|
| **Household** | A synthetic tax unit (people, income sources, assets, dependents) drawn from US survey microdata or hand-built archetypes. |
| **Move** | One call from a fixed action vocabulary that changes the household's arrangements (see §5.2). |
| **Gain** | Increase in the household's net resources (after taxes, including benefits), summed over a multi-year horizon. |
| **Economic reality unchanged** | Pre-tax income, hours worked and total household wealth over the horizon match the baseline within a tolerance. |
| **Intended concession** | A gain attributable entirely to whitelisted provisions used within their stated conditions, identified by rerunning the calculation with each provision disabled in turn. |
| **Candidate loophole** | A move sequence with positive gain, confirmed by both calculators, economic reality unchanged, and not explained by an intended concession. |
| **Verified loophole** | A candidate that also survives the LLM-judge panel and US tax expert review. |
| **Benefit cliff** | A gain that comes from reducing real income across a sharp benefit phase-out. Reported separately as a policy-design finding, not as avoidance. |

---

## 4. Hypotheses

Each hypothesis has a prediction and a result that would count against it. Thresholds marked *(proposed)* will be fixed and pre-registered at the end of Phase 0, before any agent search runs.

### H1 — The verifier is valid

The verifier flags known loopholes under the law before they were closed, rejects them after closure, and rejects legitimate planning.

- **Prediction:** On the historical-closure set, the verifier flags ≥ 90% of loopholes under pre-closure rules and ≤ 10% under post-closure rules; on a set of legitimate planning scenarios, false positives ≤ 5% *(proposed)*.
- **Counts against:** The verifier misses closures, keeps flagging them after closure, or flags ordinary planning. In that case, we fix the verifier before any further phase, since every later result depends on it.

### H2 — Frozen frontier agents with search rediscover known strategies

A frontier model combined with a search procedure (many attempts over move sequences, keeping a diverse set of candidates) rediscovers known household strategies at a substantially higher rate than non-LLM baselines.

- **Prediction:** LLM + search recall on known strategies exceeds both random search over moves and single-shot prompting, at matched compute budget.
- **Counts against:** Random or heuristic search matches the LLM agent, which would mean the move space is small enough that the language model adds little.

### H3 — Agents search rather than recall

Rediscovery reflects search, not memorized tax history.

- **Prediction:** Recall on *disguised* loopholes (planted in law variants with renamed and reworded provisions that never existed in real law) is close to recall on real historical loopholes.
- **Counts against:** Recall on real historical loopholes is much higher than on disguised ones, which would mean results largely reflect memory of known cases.

### H4 — Agents exploit the code, and cross-checking catches most of it

Under optimization pressure, a meaningful share of candidates are calculator bugs or modeling gaps rather than loopholes in the law, and requiring agreement between two independent calculators removes most of them.

- **Prediction:** The share of single-calculator candidates that fail the cross-check rises as search pressure increases; after the cross-check, the remaining false positives found at expert review are a small minority.
- **Counts against:** Either agents almost never exploit the code (the reward-hacking concern doesn't apply here), or the cross-check misses most exploits found later at review (both calculators share the same errors).

### H5 — RL on planted loopholes transfers to real ones

An open-weight model trained with RL on law variants containing planted loopholes improves its recall on held-out real loopholes compared with the same model before training.

- **Prediction:** Post-trained recall on the held-out real-closure set is significantly higher than the base model's, and the gap to the frozen frontier baseline narrows.
- **Counts against:** Gains appear only on planted-loophole variants similar to the training distribution, which would mean the model learned the mutation patterns, not a general skill.

### H6 — Exploratory: new candidates exist under current law

At least one candidate under current law survives every rung of the verification ladder, including expert review, and has no match in known sources.

- This is exploratory, not confirmatory. A null result is expected and acceptable; household tax is well studied.

---

## 5. Method

### 5.1 Verifier stack

| Component | Role |
|---|---|
| **PolicyEngine-US** | Primary calculator: federal and state taxes and benefits for households; supports parametric reforms. |
| **Tax-Calculator (PSL) or NBER TAXSIM** | Independent second calculator for federal income tax; used to cross-check every candidate. |
| **Economic-reality check** | Compares pre-tax income, hours and wealth over the horizon. |
| **Attribution check** | Disables provisions one at a time (via reforms) to identify the source of any gain; applies the intended-concession whitelist. |
| **LLM judge panel** | Scores surviving candidates for legality and plausibility. |
| **Expert review** | A US CPA or tax attorney reviews the top candidates. |

### 5.2 Action vocabulary (initial)

`set_filing_status` · `gift_asset` · `shift_income` · `realize_gain` · `assign_dependent` · `set_hours` · `itemize_or_standard`

Agents may also log "wanted" moves the vocabulary can't express; frequent requests guide which moves to add next.

### 5.3 Data

- **Households:** Synthetic households from US survey microdata (as used by PolicyEngine), plus hand-built archetypes (single earner, dual earner, retiree, family with dependents, investor). Generation favours households that exercise untested provisions (coverage-guided).
- **Historical-closure set:** Household-level loopholes later closed by Congress, encoded as pre- and post-closure rule versions. Anchor case: the kiddie tax (Tax Reform Act of 1986). Further cases to be compiled in Phase 0.
- **Shelter Check subset:** The strategies from Blair-Stanek et al. (2025) expressible with household-level moves. Access to the non-public portion requires a data use agreement.
- **Legitimate-planning set:** Scenarios using intended incentives as designed, used to measure false positives.
- **Planted-loophole variants:** Law variants created by mutating PolicyEngine parameters (removing anti-abuse rules, moving thresholds, sharpening phase-outs). Each planted loophole is known by construction. A disguised subset renames and rewords provisions.

### 5.4 Agents and baselines

| Condition | Description |
|---|---|
| Random search | Random move sequences, same evaluation budget. |
| Heuristic search | Hand-coded greedy or evolutionary search over moves. |
| Single-shot LLM | Frontier model proposes move sequences without iteration. |
| **LLM + search** | Frontier model with iterative search and a diversity archive (quality-diversity), frozen weights. |
| Base open model + search | Open-weight model, same scaffold, before training. |
| **RL-trained open model + search** | Same model after RL on planted-loophole variants. |

### 5.5 Training (Phase 3)

- **Reward:** Verifier-confirmed gain, plus a novelty bonus for exploiting provisions not yet exploited, to avoid collapse onto a single trick.
- **Training data:** Planted-loophole variants only. The historical-closure set, the Shelter Check subset and a held-out set of disguised variants are never used in training.
- **Monitoring:** Track the rate of single-calculator exploits during training as an early warning of reward hacking.

---

## 6. Evaluation metrics

| Metric | Definition | Hypotheses |
|---|---|---|
| **Verifier accuracy** | Flag rate pre-closure, flag rate post-closure, false-positive rate on legitimate planning | H1 |
| **Recall** | Share of known strategies (historical + Shelter Check subset) rediscovered | H2, H5 |
| **Disguised recall** | Recall on renamed, never-real planted loopholes | H3, H5 |
| **Code-exploit rate** | Share of candidates failing the two-calculator cross-check | H4 |
| **Diversity** | Number of distinct provisions exploited | H2, H5 |
| **Reach** | Share of synthetic households for which a finding works | H6 |
| **Novel survivors** | Candidates passing expert review with no known match | H6 |
| **Cost** | Compute and expert hours per verified finding | All |

**Statistics:** All recall comparisons use multiple random seeds and bootstrap confidence intervals. Compute budgets are matched across conditions.

---

## 7. Phases and timeline

| Phase | Duration | Work | Exit criterion |
|---|---|---|---|
| **0. Setup** | Weeks 1–2 | Install both calculators; build the reality and attribution checks; compile the historical-closure and legitimate-planning sets; pre-register thresholds. | Known-answer tests pass; test sets compiled. |
| **1. Verifier validation** | Week 3 | Run H1 on the historical-closure and legitimate-planning sets. | H1 thresholds met, or verifier fixed until they are. |
| **2. Frozen search** | Weeks 4–6 | Run all frozen conditions; build planted and disguised variants; expert session on top candidates. | Results for H2, H3, H4; first H6 candidates. |
| **3. Post-training** | Weeks 7–12 | RL on planted variants; evaluate on held-out sets. | Results for H5. |
| **4. Write-up** | Weeks 13–14 | Paper draft; disclosure of any novel findings. | Draft complete. |

Phase 2 alone is a complete, reportable result. Phase 3 proceeds only if H1 holds and Phase 2 shows the verifier is robust to agent search.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Calculators only model households, not trusts, partnerships or cross-border structures | Scope claims explicitly to household tax; report the share of Shelter Check strategies that fall outside scope. |
| Calculators may not cover the years before a closure | Encode pre-closure rules as custom reforms; validate each against period sources. |
| Both calculators share the same modeling error | Known-answer tests against IRS worked examples; expert review of a random sample of candidates, not only the top ones. |
| Results mostly reflect memorized cases | Disguised planted loopholes (H3); report recall on both. |
| Few real historical closures at household level | Use them only for evaluation; train on planted variants; report confidence intervals honestly. |
| Most findings are benefit cliffs, not avoidance | Report cliffs as a separate category of policy-design findings. |
| Open models too weak for RL to help | Report the frozen-frontier versus trained-open comparison either way; it shows where the capability comes from. |
| Expert time is scarce | Rely on cheap rungs for volume; reserve experts for top candidates and a small random audit. |

---

## 9. Ethics and disclosure

Findings are tax-avoidance strategies and could be misused.

- Novel verified findings are shared with relevant experts or authorities before details are published.
- Public outputs describe findings at the level of affected provisions and households, not step-by-step instructions.
- No real taxpayer data is used; all households are synthetic.
- Agents trained in Phase 3 are not released as standalone loophole-finding tools.

---

## 10. Expected contributions

1. A programmatic verifier for household tax loopholes, validated against historically closed loopholes.
2. A benchmark of known and disguised household loopholes for measuring search versus memory.
3. A measurement of how often agents exploit a calculator's code instead of the law, and how well cross-checking catches it.
4. Evidence on whether RL against a tax verifier produces a loophole-finding skill that transfers to unseen laws.

---

## 11. References

- Blair-Stanek, A., Holzenberger, N., & Van Durme, B. (2025). *Can LLMs Identify Tax Abuse?* arXiv:2508.20097.
- Fratrič, P., Holzenberger, N., & Restrepo Amariles, D. (2025). *Can AI expose tax loopholes? Towards a new generation of legal policy assistants.* arXiv:2503.17339.
- PolicyEngine. *PolicyEngine-US.* https://github.com/PolicyEngine
- Policy Simulation Library. *Tax-Calculator.* https://github.com/PSLmodels/Tax-Calculator
- National Bureau of Economic Research. *TAXSIM.*
