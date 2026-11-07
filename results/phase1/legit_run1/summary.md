# E0.6 legitimate-planning set and E1.2 check ablation

Positives (legitimate planning): 96; labelled negatives: 20.

- **False-positive rate: 8.3%** (dev 3.7%, test 14.3%); H1 target <= 5%
- Labelled negatives with the expected label: 100.0%

## Labels by family

| family         |   benefit_cliff |   candidate |   code_disagreement |   intended_concession |   no_gain |   sacrifice |
|:---------------|----------------:|------------:|--------------------:|----------------------:|----------:|------------:|
| 401k           |               0 |           0 |                   0 |                    46 |         0 |           0 |
| benefit_cliff  |              12 |           0 |                   0 |                     0 |         0 |           0 |
| claim_child    |               0 |           2 |                   0 |                     5 |         1 |           0 |
| gift_allowance |               0 |           4 |                   0 |                    14 |         0 |           0 |
| ira            |               0 |           0 |                   0 |                    18 |         2 |           0 |
| itemize        |               0 |           0 |                   2 |                     0 |         2 |           0 |
| sacrifice      |               0 |           0 |                   0 |                     0 |         0 |           6 |
| wash_sale      |               0 |           0 |                   0 |                     0 |         2 |           0 |

## E1.2 ablation (relabelling the same verdicts)

|                        |   fp_rate |   negatives_flagged |
|:-----------------------|----------:|--------------------:|
| full                   |     0.083 |               0.000 |
| no_reality_check       |     0.083 |               0.900 |
| no_crosscheck          |     0.083 |               0.000 |
| no_whitelist           |     0.948 |               0.000 |
| no_anti_abuse_override |     0.083 |               0.000 |
| no_gain_threshold      |     0.083 |               0.000 |

## False positives

| id                           | family         | label_full        |    gain |   gain_federal_pe |   gain_federal_tc |   gain_benefits |   gain_other_tax |   residual_without_intended | signature            | circumvents   |
|:-----------------------------|:---------------|:------------------|--------:|------------------:|------------------:|----------------:|-----------------:|----------------------------:|:---------------------|:--------------|
| claim_w90000_25000_c2        | claim_child    | candidate         | 4296.38 |           3594.83 |           3594.83 |          701.55 |             0.00 |                        0.16 | ['eitc']             | []            |
| claim_w150000_35000_c2       | claim_child    | candidate         | 2535.88 |           1834.33 |           1834.33 |          701.55 |             0.00 |                        0.28 | ['eitc']             | []            |
| gift_allow_w300000_i2000_a8  | gift_allowance | candidate         |  706.00 |            706.00 |            706.00 |            0.00 |             0.00 |                        0.11 | ['kiddie_allowance'] | []            |
| gift_allow_w300000_i2000_a15 | gift_allowance | candidate         |  706.00 |            706.00 |            706.00 |            0.00 |             0.00 |                        0.11 | ['kiddie_allowance'] | []            |
| gift_allow_w300000_i2600_a8  | gift_allowance | candidate         |  878.80 |            878.80 |            878.80 |            0.00 |             0.00 |                        0.11 | ['kiddie_allowance'] | []            |
| gift_allow_w300000_i2600_a15 | gift_allowance | candidate         |  878.80 |            878.80 |            878.80 |            0.00 |             0.00 |                        0.11 | ['kiddie_allowance'] | []            |
| itemize_w80000_m30000        | itemize        | code_disagreement |   96.00 |             96.00 |              0.00 |            0.00 |             0.00 |                        1.00 | []                   | []            |
| itemize_w250000_m30000       | itemize        | code_disagreement |  192.00 |            192.00 |              0.00 |            0.00 |             0.00 |                        1.00 | []                   | []            |
