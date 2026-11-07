# E2.1 planted variants (19; valid 15)

Valid: witness flagged under the mutated law and the closure removes >= 30% of its gain. Reach: share of the family panel exploited the same way.

| id                    | family           | split   | coverage   | control   | valid   | control_ok   | witness_label       |   witness_gain |   witness_reduction |   reach |
|:----------------------|:-----------------|:--------|:-----------|:----------|:--------|:-------------|:--------------------|---------------:|--------------------:|--------:|
| dependent_floor_4000  | dependent_floor  | control | two-calc   | True      | False   | True         | intended_concession |        1520.00 |                0.68 |    0.50 |
| dependent_floor_8000  | dependent_floor  | control | two-calc   | True      | False   | True         | intended_concession |        3040.00 |                0.84 |    0.33 |
| dependent_floor_12000 | dependent_floor  | control | two-calc   | True      | False   | True         | intended_concession |        4000.00 |                0.88 |    0.33 |
| mfs_brackets_1.5      | mfs_brackets     | train   | two-calc   | False     | True    |              | candidate           |        7999.50 |                1.01 |    1.00 |
| mfs_brackets_2        | mfs_brackets     | train   | two-calc   | False     | True    |              | candidate           |        8290.00 |                1.01 |    1.00 |
| ctc_mfs_300000        | ctc_mfs          | train   | two-calc   | False     | True    |              | candidate           |        2000.00 |                1.00 |    0.67 |
| ctc_mfs_400000        | ctc_mfs          | train   | two-calc   | False     | True    |              | candidate           |        4000.00 |                1.00 |    0.67 |
| niit_mfs_200000       | niit_mfs         | val     | two-calc   | False     | True    |              | candidate           |        3685.00 |                0.57 |    1.00 |
| niit_mfs_250000       | niit_mfs         | val     | two-calc   | False     | True    |              | candidate           |        3685.00 |                0.57 |    1.00 |
| mfs_std_1.5           | mfs_std          | val     | two-calc   | False     | True    |              | candidate           |        3212.00 |                1.03 |    1.00 |
| mfs_std_2             | mfs_std          | val     | two-calc   | False     | True    |              | candidate           |        6424.00 |                1.02 |    1.00 |
| actc_rate_0.3         | actc_rate        | train   | two-calc   | False     | False   |              | candidate           |        3790.13 |                0.30 |    0.00 |
| actc_rate_0.5         | actc_rate        | train   | two-calc   | False     | True    |              | candidate           |        4940.13 |                0.46 |    0.50 |
| cg0_single_150000     | cg0_single       | val     | two-calc   | False     | True    |              | candidate           |       28715.00 |                0.53 |    1.00 |
| cg0_single_250000     | cg0_single       | val     | two-calc   | False     | True    |              | candidate           |       33800.00 |                0.60 |    1.00 |
| kiddie_age_10         | kiddie_age       | test    | internal   | False     | True    |              | candidate           |        5040.00 |                0.51 |    1.00 |
| kiddie_age_12         | kiddie_age       | test    | internal   | False     | True    |              | candidate           |        5040.00 |                0.51 |    0.67 |
| kiddie_allowance_5    | kiddie_allowance | test    | internal   | False     | True    |              | candidate           |        1637.00 |                0.33 |    0.50 |
| kiddie_allowance_10   | kiddie_allowance | test    | internal   | False     | True    |              | candidate           |        3092.00 |                0.47 |    0.50 |

## Witness signatures

| variant               | family           | label               | signature                                      |   gain_federal_pe |   gain_federal_tc | error   |
|:----------------------|:-----------------|:--------------------|:-----------------------------------------------|------------------:|------------------:|:--------|
| dependent_floor_4000  | dependent_floor  | intended_concession | dependent_std_deduction_floor,kiddie_allowance |              1520 |              1520 |         |
| dependent_floor_8000  | dependent_floor  | intended_concession | dependent_std_deduction_floor,kiddie_allowance |              3040 |              2005 |         |
| dependent_floor_12000 | dependent_floor  | intended_concession | dependent_std_deduction_floor,kiddie_allowance |              4000 |              2005 |         |
| mfs_brackets_1.5      | mfs_brackets     | candidate           |                                                |              8044 |              8044 |         |
| mfs_brackets_2        | mfs_brackets     | candidate           |                                                |              8335 |              8335 |         |
| ctc_mfs_300000        | ctc_mfs          | candidate           | ctc                                            |              2000 |              2000 |         |
| ctc_mfs_400000        | ctc_mfs          | candidate           | ctc                                            |              4000 |              4000 |         |
| niit_mfs_200000       | niit_mfs         | candidate           | niit                                           |              4180 |              4180 |         |
| niit_mfs_250000       | niit_mfs         | candidate           | niit                                           |              4180 |              4180 |         |
| mfs_std_1.5           | mfs_std          | candidate           |                                                |              3212 |              3212 |         |
| mfs_std_2             | mfs_std          | candidate           |                                                |              6424 |              6424 |         |
| actc_rate_0.3         | actc_rate        | candidate           | ctc                                            |              3142 |              3142 |         |
| actc_rate_0.5         | actc_rate        | candidate           | ctc                                            |              4292 |              4292 |         |
| cg0_single_150000     | cg0_single       | candidate           |                                                |             28715 |             28715 |         |
| cg0_single_250000     | cg0_single       | candidate           |                                                |             33800 |             33800 |         |
| kiddie_age_10         | kiddie_age       | candidate           |                                                |              5040 |              4257 |         |
| kiddie_age_12         | kiddie_age       | candidate           |                                                |              5040 |              4257 |         |
| kiddie_allowance_5    | kiddie_allowance | candidate           | dependent_std_deduction_floor,kiddie_allowance |              1637 |              1612 |         |
| kiddie_allowance_10   | kiddie_allowance | candidate           | dependent_std_deduction_floor,kiddie_allowance |              3092 |              3092 |         |
