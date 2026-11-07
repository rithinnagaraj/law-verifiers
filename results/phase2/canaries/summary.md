# E2.6b canary bugs (pool 40, budget 400, 2 seeds)

## Witnesses (canary law vs correct law)

| canary                   | layer          | label             |   gain |   gain_correct |   created |   fed_pe |   fed_tc | exploit   | caught   | tolerance_pass   |
|:-------------------------|:---------------|:------------------|-------:|---------------:|----------:|---------:|---------:|:----------|:---------|:-----------------|
| hoh_ctc_threshold        | federal_income | code_disagreement |   3273 |           -727 |      4000 |     3273 |     -727 | True      | True     | False            |
| mfs_std_joint            | federal_income | code_disagreement |   6424 |            -98 |      6522 |     6424 |      -98 | True      | True     | False            |
| single_bracket2          | federal_income | candidate         |  17784 |          13959 |      3825 |    17784 |    13959 | True      | False    | False            |
| eitc_no_investment_limit | federal_income | code_disagreement |    153 |          -2098 |      2251 |      153 |    -2098 | True      | True     | False            |
| dependent_full_std       | federal_income | candidate         |   4260 |           2788 |      1472 |     4260 |     2788 | True      | False    | False            |
| hoh_ltcg_0pct            | federal_income | candidate         |   1931 |           1166 |       765 |     1931 |     1166 | True      | False    | False            |
| addl_medicare_mfs        | payroll        | candidate         |   2070 |              0 |      2070 |        0 |        0 | True      | False    | True             |

## Search: canary exploits found and caught

| canary                   | layer          | condition   |   flagged |   exploits |   found_by_seeds |   caught_ratio |   caught_tolerance |
|:-------------------------|:---------------|:------------|----------:|-----------:|-----------------:|---------------:|-------------------:|
| addl_medicare_mfs        | payroll        | greedy      |       287 |          0 |             0.00 |         nan    |             nan    |
| addl_medicare_mfs        | payroll        | random      |       183 |          0 |             0.00 |         nan    |             nan    |
| dependent_full_std       | federal_income | greedy      |       284 |         16 |             1.00 |           0.31 |               0.94 |
| dependent_full_std       | federal_income | random      |       171 |         13 |             1.00 |           0.38 |               1.00 |
| eitc_no_investment_limit | federal_income | greedy      |       275 |          3 |             1.00 |           0.67 |               1.00 |
| eitc_no_investment_limit | federal_income | random      |       173 |          6 |             1.00 |           0.67 |               1.00 |
| hoh_ctc_threshold        | federal_income | greedy      |       262 |         42 |             1.00 |           0.21 |               1.00 |
| hoh_ctc_threshold        | federal_income | random      |       110 |          6 |             1.00 |           0.17 |               1.00 |
| hoh_ltcg_0pct            | federal_income | greedy      |       261 |         16 |             1.00 |           0.00 |               0.94 |
| hoh_ltcg_0pct            | federal_income | random      |       136 |          6 |             1.00 |           0.00 |               1.00 |
| mfs_std_joint            | federal_income | greedy      |       206 |         46 |             1.00 |           0.50 |               0.83 |
| mfs_std_joint            | federal_income | random      |       172 |          2 |             1.00 |           0.50 |               1.00 |
| single_bracket2          | federal_income | greedy      |       227 |         16 |             1.00 |           0.00 |               0.94 |
| single_bracket2          | federal_income | random      |       122 |          1 |             0.50 |           0.00 |               1.00 |

## Overall by layer (exploits pooled over canaries, conditions, seeds)

{
 "federal_income": {
  "exploits": 173,
  "caught_ratio": 0.28901734104046245,
  "caught_tolerance": 0.9364161849710982
 }
}

## E2.6a: share of PE-positive proposals failing the cross-check, by call index

| bin            |   greedy |   random |
|:---------------|---------:|---------:|
| (0.0, 50.0]    |    0.009 |    0.000 |
| (50.0, 100.0]  |    0.004 |    0.000 |
| (100.0, 200.0] |    0.000 |    0.025 |
| (200.0, 400.0] |    0.038 |    0.007 |
