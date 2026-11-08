# E0.6 legitimate-planning set and E1.2 check ablation

Positives (legitimate planning): 90; labelled negatives: 32.

- **False-positive rate: 0.0%** (dev 0.0%, test 0.0%); H1 target <= 5%
- Two-calc false positives only: 0.0%; counting only `candidate` (not `code_disagreement`): 0.0%
- Labelled negatives with the expected label: 100.0%

## Labels by family

| family         |   benefit_cliff |   candidate |   intended_concession |   no_gain |   sacrifice |
|:---------------|----------------:|------------:|----------------------:|----------:|------------:|
| 401k           |               0 |           0 |                    46 |         0 |           0 |
| benefit_cliff  |               9 |           0 |                     0 |         3 |           0 |
| claim_child    |               0 |           0 |                     7 |         1 |           0 |
| gift_allowance |               0 |           0 |                    12 |         0 |           0 |
| gift_niit      |               0 |          12 |                     0 |         0 |           0 |
| ira            |               0 |           0 |                    18 |         2 |           0 |
| itemize        |               0 |           0 |                     0 |         4 |           0 |
| sacrifice      |               0 |           0 |                     0 |         0 |           6 |
| wash_sale      |               0 |           0 |                     0 |         2 |           0 |

## E1.2 ablation (relabelling the same verdicts)

|                        |   fp_rate |   negatives_flagged |
|:-----------------------|----------:|--------------------:|
| full                   |     0.000 |               0.375 |
| no_reality_check       |     0.000 |               0.844 |
| no_crosscheck          |     0.000 |               0.375 |
| no_whitelist           |     0.922 |               0.375 |
| no_anti_abuse_override |     0.000 |               0.375 |
| no_gain_threshold      |     0.000 |               0.375 |

## False positives

none
