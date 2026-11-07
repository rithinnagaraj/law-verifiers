# E0.4 Move-vocabulary audit (desk review, 2026-11-07)

Which known strategies can the move vocabulary (`src/taxred/moves.py`)
express, and what is missing? This sets the in-scope denominator for recall
(research plan §8: "report the share of Shelter Check strategies that fall
outside scope").

## Shelter Check (Blair-Stanek, Holzenberger & Van Durme 2025)

36 strategies; 5 public (github.com/BlairStanek/LLM-Tax-Abuse, `Strategies/`),
31 under a data use agreement. Sources: 29 IRS listed transactions, 4 court
cases, 2 flaws in the 2017 act, 1 IRS release. Primary areas: income tax 10,
international 9, employee benefits 8, partnership 5, corporate 4.

| Public strategy | Structure | In scope (household moves)? |
|---|---|---|
| 1 Distressed-asset trust | foreign person, trust, built-in loss | no — trust, cross-border |
| 11 Subsidiary handling stock compensation | corporate group | no — corporate |
| 17 Straddle abuse, common trust fund | trust, straddles | no — trust, derivatives |
| 31 Barnes Group v. Commissioner | corporate, international | no |
| 34 Tribune Media v. Commissioner | corporate | no |

**In scope: 0 of 5 public strategies.** Given the source mix (listed
transactions are overwhelmingly entity-level), the DUA portion is unlikely to
add more than a handful. Recommendation: treat the Shelter Check subset as a
reported out-of-scope share, not as a recall target; ask the authors (DUA)
only if a quick check of the 31 titles shows household-level items.

## Historical-closure candidates (experiment plan E0.5)

| Case | Expressible? | Status |
|---|---|---|
| Kiddie tax, TRA 1986 / TIPRA 2005 / SBWOTA 2007 | yes (`gift_asset`) | in E1.1 (internal implementation, F1) |
| Dependent standard-deduction limit, TRA 1986 | yes (`gift_asset`) | in E1.1, **two-calc** |
| Child AMT exemption limit, TRA 1986 | yes (`gift_asset`) | in E1.1; PolicyEngine fails it (F3) |
| EITC disqualified-investment-income limit (1995/96) | the closure targets a *static* fact (investment income while claiming); no move is needed pre-closure | not a move-based closure; its circumvention under current law (gift assets to a child) is a seed strategy (`cases.known_strategies`) |
| Home-sale exclusion after converting a rental (2008) | no | missing: property use / residence moves, home sale |
| SALT-cap charitable-credit workaround (2019 regs) | no | missing: state tax credits for donations; neither calculator models them |
| Roth recharacterization (2017) | no | missing: retirement-account conversions, price paths |
| Social Security file-and-suspend (2015) | no | missing: benefit claiming; PolicyEngine takes benefits as inputs |

**In scope: 3 independent closures (5 law steps), below the plan's ≥ 8.**
Per the plan, H1/H2 on the historical set are therefore reported as per-case
studies, not rates; planted variants carry the statistical load.

## Wanted moves (to extend the vocabulary)

Ordered by how many known household strategies each would unlock:

1. `contribute_hsa`, `roth_conversion` (retirement / health accounts; the
   latter needs the multi-year horizon, now available)
2. `sell_home` / `convert_residence` (§121 exclusion and its 2008 closure)
3. `donate` (cash / appreciated property; charitable deduction, SALT workaround
   if a calculator models state credits)
4. `claim_social_security(age)` (claiming strategies; needs PolicyEngine
   benefit formulas rather than inputs)
5. `employ_child` as a distinct move from `shift_income` (the payroll-tax
   exemption for a sole proprietor's children under 18 — check calculator
   support first)

Agents' own `wanted_moves` logs (LLM proposer) will re-rank this list once LLM
search runs.
