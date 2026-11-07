# E2.1 planted variants (13; valid 6)

Valid: witness flagged under the mutated law and the closure removes >= 50% of its gain. Reach: share of the family panel exploited the same way.

| id                    | family           | split   | coverage   | valid   | witness_label       |   witness_gain |   witness_reduction |   reach |
|:----------------------|:-----------------|:--------|:-----------|:--------|:--------------------|---------------:|--------------------:|--------:|
| dependent_floor_4000  | dependent_floor  | train   | two-calc   | False   | intended_concession |        1520.00 |                0.68 |    0.33 |
| dependent_floor_8000  | dependent_floor  | train   | two-calc   | False   | intended_concession |        3040.00 |                0.84 |    0.33 |
| dependent_floor_12000 | dependent_floor  | train   | two-calc   | False   | intended_concession |        4000.00 |                0.88 |    0.33 |
| mfs_brackets_1.5      | mfs_brackets     | train   | two-calc   | True    | candidate           |        7999.50 |                1.01 |    1.00 |
| mfs_brackets_2        | mfs_brackets     | train   | two-calc   | True    | candidate           |        8290.00 |                1.01 |    1.00 |
| ctc_mfs_300000        | ctc_mfs          | train   | two-calc   | True    | candidate           |        2000.00 |                1.00 |    0.67 |
| ctc_mfs_400000        | ctc_mfs          | train   | two-calc   | True    | candidate           |        4000.00 |                1.00 |    0.67 |
| niit_mfs_200000       | niit_mfs         | val     | two-calc   | False   | no_gain             |       -3594.75 |              nan    |    0.00 |
| niit_mfs_250000       | niit_mfs         | train   | two-calc   | False   | no_gain             |       -3594.75 |              nan    |    0.00 |
| kiddie_age_10         | kiddie_age       | test    | internal   | True    | candidate           |        5040.00 |                0.51 |    0.50 |
| kiddie_age_12         | kiddie_age       | test    | internal   | True    | candidate           |        5040.00 |                0.51 |    0.33 |
| kiddie_allowance_5    | kiddie_allowance | test    | internal   | False   | candidate           |        1920.00 |                0.28 |    0.00 |
| kiddie_allowance_10   | kiddie_allowance | test    | internal   | False   | candidate           |        2410.00 |                0.43 |    0.33 |

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
| niit_mfs_200000       | niit_mfs         | no_gain             |                                                |             -2470 |             -2470 |         |
| niit_mfs_250000       | niit_mfs         | no_gain             |                                                |             -2470 |             -2470 |         |
| kiddie_age_10         | kiddie_age       | candidate           |                                                |              5040 |              4257 |         |
| kiddie_age_12         | kiddie_age       | candidate           |                                                |              5040 |              4257 |         |
| kiddie_allowance_5    | kiddie_allowance | candidate           | dependent_std_deduction_floor,kiddie_allowance |              1920 |              1920 |         |
| kiddie_allowance_10   | kiddie_allowance | candidate           | dependent_std_deduction_floor,kiddie_allowance |              2410 |              2410 |         |
