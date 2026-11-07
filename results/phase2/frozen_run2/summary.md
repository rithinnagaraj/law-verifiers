# E2.3 frozen comparison (non-LLM): budget 200, 3 seeds, R = 0.1

| condition   | kind       |   n_targets |   recall@10 |   recall@25 |   recall@50 |   recall@100 |   recall@200 |   auc_log_budget |
|:------------|:-----------|------------:|------------:|------------:|------------:|-------------:|-------------:|-----------------:|
| greedy      | historical |           4 |        0.25 |        0.25 |        0.25 |         1.00 |         1.00 |             0.51 |
| greedy      | planted    |          13 |        0.59 |        0.74 |        0.92 |         0.95 |         1.00 |             0.84 |
| random      | historical |           4 |        0.42 |        0.67 |        0.75 |         0.75 |         1.00 |             0.71 |
| random      | planted    |          13 |        0.62 |        0.67 |        0.82 |         0.92 |         1.00 |             0.79 |

## Rediscovery rate per target (share of seeds)

| target                      |   greedy |   random |
|:----------------------------|---------:|---------:|
| hist:dependent_std_tra1986  |     1.00 |     1.00 |
| hist:kiddie_sbwota2007      |     1.00 |     1.00 |
| hist:kiddie_tipra2005       |     1.00 |     1.00 |
| hist:kiddie_tra1986         |     1.00 |     1.00 |
| planted:actc_rate_0.5       |     1.00 |     1.00 |
| planted:ctc_mfs_300000      |     1.00 |     1.00 |
| planted:ctc_mfs_400000      |     1.00 |     1.00 |
| planted:kiddie_age_10       |     1.00 |     1.00 |
| planted:kiddie_age_12       |     1.00 |     1.00 |
| planted:kiddie_allowance_10 |     1.00 |     1.00 |
| planted:kiddie_allowance_5  |     1.00 |     1.00 |
| planted:mfs_brackets_1.5    |     1.00 |     1.00 |
| planted:mfs_brackets_2      |     1.00 |     1.00 |
| planted:mfs_std_1.5         |     1.00 |     1.00 |
| planted:mfs_std_2           |     1.00 |     1.00 |
| planted:niit_mfs_200000     |     1.00 |     1.00 |
| planted:niit_mfs_250000     |     1.00 |     1.00 |
