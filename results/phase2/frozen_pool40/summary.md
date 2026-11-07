# E2.3 frozen comparison (non-LLM): budget 1000, 2 seeds, R = 0.1

| condition   | kind       |   n_targets |   recall@10 |   recall@25 |   recall@50 |   recall@100 |   recall@200 |   recall@400 |   recall@1000 |   auc_log_budget |
|:------------|:-----------|------------:|------------:|------------:|------------:|-------------:|-------------:|-------------:|--------------:|-----------------:|
| greedy      | historical |           4 |        0.00 |        0.00 |        0.00 |         0.25 |         0.38 |         0.62 |          1.00 |             0.30 |
| greedy      | planted    |          15 |        0.07 |        0.13 |        0.20 |         0.30 |         0.57 |         0.80 |          0.90 |             0.42 |
| random      | historical |           4 |        0.00 |        0.00 |        0.00 |         0.50 |         0.75 |         1.00 |          1.00 |             0.46 |
| random      | planted    |          15 |        0.00 |        0.13 |        0.27 |         0.30 |         0.57 |         0.87 |          0.93 |             0.44 |

## Rediscovery rate per target (share of seeds)

| target                      |   greedy |   random |
|:----------------------------|---------:|---------:|
| hist:dependent_std_tra1986  |     1.00 |     1.00 |
| hist:kiddie_sbwota2007      |     1.00 |     1.00 |
| hist:kiddie_tipra2005       |     1.00 |     1.00 |
| hist:kiddie_tra1986         |     1.00 |     1.00 |
| planted:actc_rate_0.5       |     1.00 |     1.00 |
| planted:cg0_single_150000   |     1.00 |     0.50 |
| planted:cg0_single_250000   |     1.00 |     1.00 |
| planted:ctc_mfs_300000      |     1.00 |     1.00 |
| planted:ctc_mfs_400000      |     0.50 |     1.00 |
| planted:kiddie_age_10       |     1.00 |     1.00 |
| planted:kiddie_age_12       |     1.00 |     1.00 |
| planted:kiddie_allowance_10 |     1.00 |     1.00 |
| planted:kiddie_allowance_5  |     1.00 |     1.00 |
| planted:mfs_brackets_1.5    |     1.00 |     1.00 |
| planted:mfs_brackets_2      |     1.00 |     1.00 |
| planted:mfs_std_1.5         |     1.00 |     1.00 |
| planted:mfs_std_2           |     1.00 |     1.00 |
| planted:niit_mfs_200000     |     0.50 |     0.50 |
| planted:niit_mfs_250000     |     0.50 |     1.00 |
