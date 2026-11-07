# E0.6 legitimate-planning set and E1.2 check ablation

Positives (legitimate planning): 90; labelled negatives: 32.

- **False-positive rate: 2.2%** (dev 0.0%, test 5.1%); H1 target <= 5%
- Two-calc false positives only: 0.0%; counting only `candidate` (not `code_disagreement`): 2.2%
- Labelled negatives with the expected label: 100.0%

## Labels by family

| family         |   benefit_cliff |   candidate |   intended_concession |   no_gain |   sacrifice |
|:---------------|----------------:|------------:|----------------------:|----------:|------------:|
| 401k           |               0 |           0 |                    46 |         0 |           0 |
| benefit_cliff  |              12 |           0 |                     0 |         0 |           0 |
| claim_child    |               0 |           2 |                     5 |         1 |           0 |
| gift_allowance |               0 |           0 |                    12 |         0 |           0 |
| gift_niit      |               0 |          12 |                     0 |         0 |           0 |
| ira            |               0 |           0 |                    18 |         2 |           0 |
| itemize        |               0 |           0 |                     0 |         4 |           0 |
| sacrifice      |               0 |           0 |                     0 |         0 |           6 |
| wash_sale      |               0 |           0 |                     0 |         2 |           0 |

## E1.2 ablation (relabelling the same verdicts)

|                        |   fp_rate |   negatives_flagged |
|:-----------------------|----------:|--------------------:|
| full                   |     0.022 |               0.375 |
| no_reality_check       |     0.022 |               0.938 |
| no_crosscheck          |     0.022 |               0.375 |
| no_whitelist           |     0.922 |               0.375 |
| no_anti_abuse_override |     0.022 |               0.375 |
| no_gain_threshold      |     0.022 |               0.375 |

## False positives

| id                     | family      | label_full   | coverage    |    gain |   gain_federal_pe |   gain_federal_tc |   gain_benefits |   gain_other_tax |   residual_without_intended | signature   | circumvents   |
|:-----------------------|:------------|:-------------|:------------|--------:|------------------:|------------------:|----------------:|-----------------:|----------------------------:|:------------|:--------------|
| claim_w90000_25000_c2  | claim_child | candidate    | single-calc | 4296.38 |           3594.83 |           3594.83 |          701.55 |             0.00 |                        0.16 | ['eitc']    | []            |
| claim_w150000_35000_c2 | claim_child | candidate    | single-calc | 2535.88 |           1834.33 |           1834.33 |          701.55 |             0.00 |                        0.28 | ['eitc']    | []            |
