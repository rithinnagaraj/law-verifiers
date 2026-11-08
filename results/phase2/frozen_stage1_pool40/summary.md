# E2.3 frozen comparison (non-LLM): budget 400, 2 seeds, R = 0.1

| condition   | kind       |   n_targets |   recall@10 |   recall@25 |   recall@50 |   recall@100 |   recall@200 |   recall@400 |   auc_log_budget |
|:------------|:-----------|------------:|------------:|------------:|------------:|-------------:|-------------:|-------------:|-----------------:|
| greedy      | historical |           5 |        0.10 |        0.10 |        0.10 |         0.30 |         0.50 |         0.70 |             0.27 |
| greedy      | planted    |          16 |        0.00 |        0.03 |        0.12 |         0.16 |         0.41 |         0.62 |             0.19 |
| random      | historical |           5 |        0.00 |        0.00 |        0.10 |         0.10 |         0.30 |         0.50 |             0.14 |
| random      | planted    |          16 |        0.00 |        0.06 |        0.12 |         0.22 |         0.41 |         0.72 |             0.22 |

## Rediscovery rate per target (share of seeds)

| target                                |   greedy |   random |
|:--------------------------------------|---------:|---------:|
| hist:dependent_std_tra1986            |     1.00 |     1.00 |
| hist:kiddie_sbwota2007                |     1.00 |     0.50 |
| hist:kiddie_tipra2005                 |     1.00 |     0.50 |
| hist:kiddie_tra1986                   |     0.50 |     0.00 |
| hist:roth_recharacterization_tcja2017 |     0.00 |     0.50 |
| planted:actc_rate_0.3                 |     0.50 |     1.00 |
| planted:actc_rate_0.5                 |     1.00 |     0.50 |
| planted:cg0_single_150000             |     1.00 |     1.00 |
| planted:cg0_single_250000             |     0.50 |     0.50 |
| planted:ctc_mfs_300000                |     0.50 |     0.50 |
| planted:ctc_mfs_400000                |     0.00 |     0.50 |
| planted:kiddie_age_10                 |     1.00 |     1.00 |
| planted:kiddie_age_12                 |     1.00 |     1.00 |
| planted:kiddie_allowance_10           |     0.50 |     1.00 |
| planted:kiddie_allowance_5            |     0.50 |     0.50 |
| planted:mfs_brackets_1.5              |     0.50 |     0.00 |
| planted:mfs_brackets_2                |     1.00 |     0.50 |
| planted:mfs_std_1.5                   |     1.00 |     1.00 |
| planted:mfs_std_2                     |     1.00 |     1.00 |
| planted:niit_mfs_200000               |     0.00 |     0.50 |
| planted:niit_mfs_250000               |     0.00 |     1.00 |
