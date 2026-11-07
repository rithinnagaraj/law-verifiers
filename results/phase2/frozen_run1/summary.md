# E2.3 frozen comparison (non-LLM): budget 200, 3 seeds, R = 0.2

| condition   | kind       |   n_targets |   recall@10 |   recall@25 |   recall@50 |   recall@100 |   recall@200 |   auc_log_budget |
|:------------|:-----------|------------:|------------:|------------:|------------:|-------------:|-------------:|-----------------:|
| greedy      | historical |           4 |        0.25 |        0.25 |        0.25 |         1.00 |         1.00 |             0.51 |
| greedy      | planted    |           6 |        0.56 |        0.67 |        1.00 |         1.00 |         1.00 |             0.84 |
| random      | historical |           4 |        0.42 |        0.67 |        0.75 |         0.75 |         1.00 |             0.71 |
| random      | planted    |           6 |        0.67 |        0.67 |        0.78 |         0.89 |         1.00 |             0.78 |

## Rediscovery rate per target (share of seeds)

| target                     |   greedy |   random |
|:---------------------------|---------:|---------:|
| hist:dependent_std_tra1986 |     1.00 |     1.00 |
| hist:kiddie_sbwota2007     |     1.00 |     1.00 |
| hist:kiddie_tipra2005      |     1.00 |     1.00 |
| hist:kiddie_tra1986        |     1.00 |     1.00 |
| planted:ctc_mfs_300000     |     1.00 |     1.00 |
| planted:ctc_mfs_400000     |     1.00 |     1.00 |
| planted:kiddie_age_10      |     1.00 |     1.00 |
| planted:kiddie_age_12      |     1.00 |     1.00 |
| planted:mfs_brackets_1.5   |     1.00 |     1.00 |
| planted:mfs_brackets_2     |     1.00 |     1.00 |
