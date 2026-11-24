# A2: noise floor of gains (current law, random valid proposals)

Proposals: 59298 (59298 valid), households: 2965.
Proposals with a PolicyEngine gain or loss above $1: 40712.

| | all valid | gain or loss > $1 |
|---|---|---|
| abs. disagreement p50 | $0.00 | $0.00 |
| abs. disagreement p90 | $0.00 | $0.01 |
| abs. disagreement p95 | $0.01 | $1.46 |
| abs. disagreement p99 | $24.79 | $40.18 |
| abs. disagreement p99.9 | $1,065.51 | $1,645.87 |
| rel. disagreement p50 | 0.0000 | |
| rel. disagreement p90 | 0.0000 | |
| rel. disagreement p95 | 0.0007 | |
| rel. disagreement p99 | 0.0356 | |
| share exactly equal (< $0.5) | 0.9631 | 0.9463 |

## Tolerance grid: share of valid random proposals labelled code_disagreement

| abs \ rel | 1% | 2% | 5% |
|---|---|---|---|
| $5 | 0.0038 | 0.0026 | 0.0014 |
| $10 | 0.0030 | 0.0022 | 0.0012 |
| $25 | 0.0019 | 0.0015 | 0.0009 |

Rule: the smallest max($a, b%) with <= 1% of random proposals labelled code_disagreement; 'smallest' = smallest tolerance at the median gain of proposals with a gain ($1,245), ties to the smaller b.
**Choice: max($5, 1%)**

## By move type (proposals containing the op; gain or loss > $1)

| op | n | p50 abs | p95 abs | p99 abs | share > $10 |
|---|---|---|---|---|---|
| assign_dependent | 1695 | 0.00 | 2.90 | 61.13 | 0.033 |
| contribute_hsa | 4619 | 0.00 | 0.01 | 19.32 | 0.018 |
| contribute_retirement | 13689 | 0.00 | 0.01 | 34.79 | 0.025 |
| donate_asset | 2131 | 0.00 | 5.98 | 100.12 | 0.036 |
| donate_cash | 13397 | 0.00 | 0.01 | 20.71 | 0.019 |
| gift_asset | 6133 | 0.00 | 4.75 | 49.18 | 0.032 |
| realize_gain | 2785 | 0.00 | 2.06 | 31.73 | 0.025 |
| reduce_donation | 4258 | 0.00 | 2.45 | 64.35 | 0.031 |
| roth_convert | 10277 | 0.00 | 8.72 | 83.75 | 0.045 |
| set_filing_status | 9174 | 0.00 | 16.96 | 517.58 | 0.063 |
| set_hours | 5417 | 0.00 | 0.01 | 24.58 | 0.022 |
| shift_income | 555 | 0.00 | 0.19 | 18.81 | 0.023 |

| income band | n | p50 abs | p95 abs | p99 abs | share > $10 |
|---|---|---|---|---|---|
| <25k | 2642 | 0.00 | 0.00 | 13.36 | 0.011 |
| 25-50k | 5526 | 0.00 | 0.00 | 14.43 | 0.013 |
| 50-100k | 12148 | 0.00 | 0.00 | 17.36 | 0.014 |
| 100-200k | 12935 | 0.00 | 1.33 | 20.76 | 0.024 |
| 200-500k | 6580 | 0.00 | 20.70 | 489.70 | 0.078 |
| 500k+ | 881 | 0.01 | 27.00 | 1208.39 | 0.085 |

Labels at the default tolerance max($10, 2%): candidate 6548, code_disagreement 129, intended_concession 6293, no_gain 32878, sacrifice 13450
Mean verifier time per proposal (per worker): 4.35 s.
