# E2.3 frozen comparison (non-LLM): budget 400, 2 seeds, R = 0.1

| condition   | kind       |   n_targets |   recall@10 |   recall@25 |   recall@50 |   recall@100 |   recall@200 |   recall@300 |   recall@400 |   auc_log_budget |
|:------------|:-----------|------------:|------------:|------------:|------------:|-------------:|-------------:|-------------:|-------------:|-----------------:|
| greedy      | historical |           5 |        0.00 |        0.00 |        0.00 |         0.00 |         0.00 |         0.00 |         0.00 |             0.00 |
| greedy      | planted    |          16 |        0.00 |        0.03 |        0.06 |         0.09 |         0.12 |         0.22 |         0.25 |             0.09 |
| random      | historical |           5 |        0.00 |        0.00 |        0.00 |         0.00 |         0.10 |         0.10 |         0.10 |             0.03 |
| random      | planted    |          16 |        0.00 |        0.03 |        0.06 |         0.09 |         0.31 |         0.44 |         0.44 |             0.14 |

## Rediscovery rate per target (share of seeds)

| target                                |   greedy |   random |
|:--------------------------------------|---------:|---------:|
| hist:dependent_std_tra1986            |     0.00 |     0.50 |
| hist:kiddie_sbwota2007                |     0.00 |     0.00 |
| hist:kiddie_tipra2005                 |     0.00 |     0.00 |
| hist:kiddie_tra1986                   |     0.00 |     0.00 |
| hist:roth_recharacterization_tcja2017 |     0.00 |     0.00 |
| planted:actc_rate_0.3                 |     0.50 |     0.50 |
| planted:actc_rate_0.5                 |     0.50 |     0.50 |
| planted:cg0_single_150000             |     0.00 |     0.00 |
| planted:cg0_single_250000             |     0.00 |     0.00 |
| planted:ctc_mfs_300000                |     0.50 |     0.00 |
| planted:ctc_mfs_400000                |     0.00 |     0.00 |
| planted:kiddie_age_10                 |     0.00 |     1.00 |
| planted:kiddie_age_12                 |     0.00 |     0.00 |
| planted:kiddie_allowance_10           |     0.50 |     1.00 |
| planted:kiddie_allowance_5            |     0.50 |     0.00 |
| planted:mfs_brackets_1.5              |     0.50 |     1.00 |
| planted:mfs_brackets_2                |     0.50 |     1.00 |
| planted:mfs_std_1.5                   |     0.50 |     1.00 |
| planted:mfs_std_2                     |     0.00 |     1.00 |
| planted:niit_mfs_200000               |     0.00 |     0.00 |
| planted:niit_mfs_250000               |     0.00 |     0.00 |
