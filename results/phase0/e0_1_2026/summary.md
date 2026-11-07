# E0.1 calculator agreement

```json
{
  "n_units": 2498,
  "n_households": 2005,
  "agree_within_1": 0.9743795036028823,
  "agree_within_25": 0.9935948759007206,
  "agree_within_1pct_or_25": 0.9991993594875901,
  "abs_diff_p50": 1.5165228816726994e-05,
  "abs_diff_p90": 0.001023220826755282,
  "abs_diff_p99": 17.47147752602149,
  "abs_diff_max": 54.40739272896826,
  "regular_tax_agree_within_1": 0.9987990392313851,
  "amt_agree_within_1": 0.999599679743795,
  "taxable_income_agree_within_1": 0.9983987189751802,
  "by_group": {
    "filing_status": {
      "HEAD_OF_HOUSEHOLD": {
        "n": 555,
        "agree_within_25": 0.9891891891891892
      },
      "JOINT": {
        "n": 902,
        "agree_within_25": 0.9900221729490022
      },
      "SINGLE": {
        "n": 1041,
        "agree_within_25": 0.9990393852065321
      }
    },
    "dependent_filer": {
      "False": {
        "n": 2005,
        "agree_within_25": 0.9920199501246882
      },
      "True": {
        "n": 493,
        "agree_within_25": 1.0
      }
    },
    "has_self_employment": {
      "False": {
        "n": 2262,
        "agree_within_25": 0.9946949602122016
      },
      "True": {
        "n": 236,
        "agree_within_25": 0.9830508474576272
      }
    },
    "has_ltcg_or_qd": {
      "False": {
        "n": 1200,
        "agree_within_25": 0.9925
      },
      "True": {
        "n": 1298,
        "agree_within_25": 0.9946070878274268
      }
    },
    "has_kids_u17": {
      "False": {
        "n": 1268,
        "agree_within_25": 0.999211356466877
      },
      "True": {
        "n": 1230,
        "agree_within_25": 0.9878048780487805
      }
    },
    "has_student_18_23": {
      "False": {
        "n": 2221,
        "agree_within_25": 0.9932462854570013
      },
      "True": {
        "n": 277,
        "agree_within_25": 0.9963898916967509
      }
    },
    "has_childcare": {
      "False": {
        "n": 2004,
        "agree_within_25": 0.9975049900199601
      },
      "True": {
        "n": 494,
        "agree_within_25": 0.9777327935222672
      }
    },
    "itemizable_gt_0": {
      "False": {
        "n": 1297,
        "agree_within_25": 0.9946029298380878
      },
      "True": {
        "n": 1201,
        "agree_within_25": 0.9925062447960034
      }
    },
    "any_65plus": {
      "False": {
        "n": 1951,
        "agree_within_25": 0.9917990773962071
      },
      "True": {
        "n": 547,
        "agree_within_25": 1.0
      }
    }
  }
}
```

## Largest disagreements

| unit_id                        | filing_status     | dependent_filer   |   wages |   self_employment |    interest |   qualified_dividends |   long_term_gains |   n_kids_u17 |    pe_fed |    tc_fed |   pe_amt |   tc_amt |
|:-------------------------------|:------------------|:------------------|--------:|------------------:|------------:|----------------------:|------------------:|-------------:|----------:|----------:|---------:|---------:|
| r0_1641:t                      | JOINT             | False             |  174980 |             18280 |   1651.7    |              752.408  |                 0 |            2 | 18521.8   | 18467.4   |        0 |        0 |
| r0_1096:t                      | JOINT             | False             |  154480 |                 0 |      0      |                0      |                 0 |            2 |  9505.6   |  9452.8   |        0 |        0 |
| r0_1091:t                      | JOINT             | False             |  385420 |                 0 |    838.422  |             4972.98   |              8890 |            1 | 70364.1   | 70320.2   |        0 |        0 |
| r0_347:t                       | JOINT             | False             |  207090 |                 0 |      0      |                0      |                 0 |            2 | 22073.2   | 22029.6   |        0 |        0 |
| r0_203:t                       | JOINT             | False             |  153160 |                 0 |   7833.54   |             2115.39   |                 0 |            3 |  9615.88  |  9572.52  |        0 |        0 |
| r0_598:t                       | JOINT             | False             |  173030 |                 0 |    196.658  |              522.159  |              1560 |            2 | 13742.2   | 13701.8   |        0 |        0 |
| r0_1087:t                      | HEAD_OF_HOUSEHOLD | False             |  237230 |                 0 |      0      |                0      |                 0 |            1 | 42212.6   | 42174.1   |        0 |        0 |
| r0_1012:t                      | JOINT             | False             |  132330 |                 0 | 192377      |           128540      |                 0 |            2 | 79022.2   | 78984.6   |        0 |        0 |
| high_earner_with_kids_assets:t | JOINT             | False             |  350000 |             60000 |  22500      |                0      |                 0 |            2 | 74979.1   | 74942.2   |        0 |        0 |
| r0_1553:t                      | JOINT             | False             |  432840 |                 0 |    221.05   |              262.614  |                 0 |            1 | 80960.4   | 80926.6   |        0 |        0 |
| r0_1903:t                      | SINGLE            | False             |   38260 |             18000 |     58.8838 |               82.897  |                 0 |            0 |  2019.9   |  1986.82  |        0 |        0 |
| r0_212:t                       | HEAD_OF_HOUSEHOLD | False             |   83010 |                 0 |      0      |                0      |                 0 |            1 |  3609.2   |  3579.35  |        0 |        0 |
| r0_1984:t                      | HEAD_OF_HOUSEHOLD | False             |  213420 |                 0 |      0      |                0      |                 0 |            1 | 34711.8   | 34682.8   |        0 |        0 |
| r0_1548:t                      | HEAD_OF_HOUSEHOLD | False             |   23670 |             72640 |      0      |                0      |                 0 |            2 |   900.702 |   873.374 |        0 |        0 |
| r0_1117:t                      | HEAD_OF_HOUSEHOLD | False             |  265460 |                 0 |      0      |                0      |                 0 |            2 | 49066.2   | 49039.2   |        0 |        0 |
| r0_935:t                       | HEAD_OF_HOUSEHOLD | False             |  101300 |                 0 |      0      |                0      |                 0 |            1 |  6544     |  6518.5   |        0 |        0 |
| r0_1154:t                      | JOINT             | False             |  166090 |                 0 |    265.012  |               76.2782 |               330 |            1 | 15740.6   | 15716.4   |        0 |        0 |
| r0_1591:t                      | JOINT             | False             |   84610 |                 0 |  61479.3    |            32866.6    |                 0 |            2 | 14199.6   | 14176.8   |        0 |        0 |
| r0_288:t                       | JOINT             | False             |  184420 |             25890 |      0      |                0      |                 0 |            3 | 19347.1   | 19324.3   |        0 |        0 |
| r0_1364:t                      | JOINT             | False             |  141130 |             51020 |      0      |                0      |                 0 |            2 | 14920.1   | 14898.3   |        0 |        0 |
| r0_1355:t                      | HEAD_OF_HOUSEHOLD | False             |   70710 |                 0 |   1892.16   |             5674.97   |                 0 |            2 |  -919.742 |  -941.428 |        0 |        0 |
| r0_660:t                       | HEAD_OF_HOUSEHOLD | False             |  101240 |                 0 |   1253.72   |             1131.43   |                 0 |            1 |  7506.33  |  7485.71  |        0 |        0 |
| r0_23:t                        | JOINT             | False             |  187320 |                 0 |      0      |                0      |                 0 |            1 | 20100.4   | 20080.3   |        0 |        0 |
| r0_627:t                       | HEAD_OF_HOUSEHOLD | False             |  219620 |                 0 |      0      |                0      |                 0 |            2 | 34299.8   | 34280.8   |        0 |        0 |
| r0_1150:t                      | HEAD_OF_HOUSEHOLD | False             |   72310 |                 0 |   1495.95   |              147.963  |              1310 |            1 |  2013.11  |  1994.89  |        0 |        0 |
