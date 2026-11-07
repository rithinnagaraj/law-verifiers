# E1.1 historical closures: H1 on the closed mechanism

Sensitivity: legally covered households flagged pre-closure where the closure removes > 2% of the gain (95% Clopper-Pearson CI). PE/TC fed: same test on each calculator's federal income-tax gain. Match: share of covered households where the closure removes >= 20% (closure-test half of the matching rule). Specificity: households the closure should not affect, with |reduction| <= 2%. Post flag: share of covered households still flagged after the closure (residual from other provisions). Closed in sig: the closed provision appears in the post-closure attribution signature (should be 0).

| case | coverage | n cov | sensitivity | PE fed | TC fed | match @R_MIN | n not cov | specificity | post flag | closed in sig | median red. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| kiddie_tra1986 | internal | 24 | 1.00 [0.86, 1.00] | 1.00 | 0.83 | 0.75 | 88 | 1.00 | 0.42 | 0.00 | 0.46 |
| kiddie_tipra2005 | internal | 12 | 1.00 [0.74, 1.00] | 1.00 | 0.83 | 0.75 | 100 | 1.00 | 0.42 | 0.00 | 0.46 |
| kiddie_sbwota2007 | internal | 36 | 1.00 [0.90, 1.00] | 1.00 | 0.94 | 0.75 | 76 | 1.00 | 0.36 | 0.00 | 0.48 |
| dependent_std_tra1986 | two-calc | 84 | 1.00 [0.96, 1.00] | 1.00 | 1.00 | 0.92 | 28 | 1.00 | 0.93 | 0.00 | 0.34 |
| tra1986_package | internal | 84 | 1.00 [0.96, 1.00] | 1.00 | 1.00 | 0.94 | 28 | 1.00 | 0.79 | 0.00 | 0.38 |
| child_amt_tra1986 | two-calc | 56 | 0.00 [0.00, 0.06] | 0.00 | 0.57 | 0.00 | 56 | 1.00 | 1.00 | 0.00 | 0.00 |

## Post-closure residual: median attribution share among still-flagged covered households

- **kiddie_tra1986**: niit 0.37, kiddie_allowance 0.16, ctc 0.10, dependent_std_deduction_floor 0.10, dependent_std_deduction_limit -1.08, kiddie_tax -1.49
- **kiddie_tipra2005**: niit 0.37, kiddie_allowance 0.16, ctc 0.10, dependent_std_deduction_floor 0.10, dependent_std_deduction_limit -1.08, kiddie_tax -1.49
- **kiddie_sbwota2007**: niit 0.41, kiddie_allowance 0.17, dependent_std_deduction_floor 0.10, dependent_std_deduction_limit -1.43, kiddie_tax -2.03
- **dependent_std_tra1986**: dependent_std_deduction_floor 0.07, dependent_std_deduction_limit -0.51
- **tra1986_package**: dependent_std_deduction_floor 0.07, dependent_std_deduction_limit -0.51
- **child_amt_tra1986**: dependent_std_deduction_floor 0.07, dependent_std_deduction_limit -0.62

## Post-closure labels (covered households)

- **kiddie_tra1986**: {'intended_concession': 14, 'candidate': 8, 'code_disagreement': 2}
- **kiddie_tipra2005**: {'intended_concession': 7, 'candidate': 4, 'code_disagreement': 1}
- **kiddie_sbwota2007**: {'intended_concession': 23, 'candidate': 12, 'code_disagreement': 1}
- **dependent_std_tra1986**: {'candidate': 78, 'intended_concession': 6}
- **tra1986_package**: {'candidate': 58, 'intended_concession': 18, 'code_disagreement': 8}
- **child_amt_tra1986**: {'candidate': 44, 'code_disagreement': 12}
