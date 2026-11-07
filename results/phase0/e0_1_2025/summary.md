# E0.1 calculator agreement

```json
{
  "n_units": 2498,
  "n_households": 2005,
  "agree_within_1": 0.9915932746196957,
  "agree_within_25": 0.9955964771817454,
  "agree_within_1pct_or_25": 0.999599679743795,
  "abs_diff_p50": 1.7018834114423953e-05,
  "abs_diff_p90": 0.0008620838234492134,
  "abs_diff_p99": 0.011560678023524824,
  "abs_diff_max": 55.950633929504875,
  "regular_tax_agree_within_1": 1.0,
  "amt_agree_within_1": 0.999599679743795,
  "taxable_income_agree_within_1": 0.999599679743795,
  "by_group": {
    "filing_status": {
      "HEAD_OF_HOUSEHOLD": {
        "n": 555,
        "agree_within_25": 0.9891891891891892
      },
      "JOINT": {
        "n": 902,
        "agree_within_25": 0.9955654101995566
      },
      "SINGLE": {
        "n": 1041,
        "agree_within_25": 0.9990393852065321
      }
    },
    "dependent_filer": {
      "False": {
        "n": 2005,
        "agree_within_25": 0.9950124688279302
      },
      "True": {
        "n": 493,
        "agree_within_25": 0.9979716024340771
      }
    },
    "has_self_employment": {
      "False": {
        "n": 2262,
        "agree_within_25": 0.9969053934571176
      },
      "True": {
        "n": 236,
        "agree_within_25": 0.9830508474576272
      }
    },
    "has_ltcg_or_qd": {
      "False": {
        "n": 1200,
        "agree_within_25": 0.9941666666666666
      },
      "True": {
        "n": 1298,
        "agree_within_25": 0.9969183359013868
      }
    },
    "has_kids_u17": {
      "False": {
        "n": 1268,
        "agree_within_25": 0.999211356466877
      },
      "True": {
        "n": 1230,
        "agree_within_25": 0.991869918699187
      }
    },
    "has_student_18_23": {
      "False": {
        "n": 2221,
        "agree_within_25": 0.9954975236380009
      },
      "True": {
        "n": 277,
        "agree_within_25": 0.9963898916967509
      }
    },
    "has_childcare": {
      "False": {
        "n": 2004,
        "agree_within_25": 0.9965069860279441
      },
      "True": {
        "n": 494,
        "agree_within_25": 0.9919028340080972
      }
    },
    "itemizable_gt_0": {
      "False": {
        "n": 1297,
        "agree_within_25": 0.9961449498843485
      },
      "True": {
        "n": 1201,
        "agree_within_25": 0.9950041631973355
      }
    },
    "any_65plus": {
      "False": {
        "n": 1951,
        "agree_within_25": 0.9943618657098924
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
| r0_873:t:dep:k0                | SINGLE            | True              |    5190 |                 0 |  16046.1    |            11418.7    |                 0 |            0 |   1633.03 |   1688.98 |        0 |  55.9507 |
| r0_1091:t                      | JOINT             | False             |  385420 |                 0 |    838.422  |             4972.98   |              8890 |            1 |  71030.1  |  70986.2  |        0 |   0      |
| r0_268:t                       | HEAD_OF_HOUSEHOLD | False             |  178510 |             35130 |      0      |                0      |                 0 |            1 |  33435    |  33393.5  |        0 |   0      |
| r0_1087:t                      | HEAD_OF_HOUSEHOLD | False             |  237230 |                 0 |      0      |                0      |                 0 |            1 |  43377.6  |  43339.1  |        0 |   0      |
| r0_1012:t                      | JOINT             | False             |  132330 |                 0 | 192377      |           128540      |                 0 |            2 |  80168.2  |  80130.6  |        0 |   0      |
| high_earner_with_kids_assets:t | JOINT             | False             |  350000 |             60000 |  22500      |                0      |                 0 |            2 |  75703    |  75666    |        0 |   0      |
| r0_1553:t                      | JOINT             | False             |  432840 |                 0 |    221.05   |              262.614  |                 0 |            1 |  82183.3  |  82149.5  |        0 |   0      |
| r0_1295:t                      | HEAD_OF_HOUSEHOLD | False             |  133220 |            137630 |      0      |                0      |                 0 |            2 |  49965.6  |  49933.1  |        0 |   0      |
| r0_826:t                       | HEAD_OF_HOUSEHOLD | False             |   96500 |            126540 |      0      |                0      |                 0 |            1 |  29770.8  |  29741.3  |        0 |   0      |
| r0_1984:t                      | HEAD_OF_HOUSEHOLD | False             |  213420 |                 0 |      0      |                0      |                 0 |            1 |  35158.8  |  35129.8  |        0 |   0      |
| r0_1117:t                      | HEAD_OF_HOUSEHOLD | False             |  265460 |                 0 |      0      |                0      |                 0 |            2 |  49911.2  |  49884.2  |        0 |   0      |
| r0_1940:t                      | HEAD_OF_HOUSEHOLD | False             |   34640 |              9490 |      0      |                0      |                 0 |            1 |  -4388.45 |  -4411.56 |        0 |   0      |
| r0_627:t                       | HEAD_OF_HOUSEHOLD | False             |  219620 |                 0 |      0      |                0      |                 0 |            2 |  34746.8  |  34727.8  |        0 |   0      |
| r0_390:t                       | HEAD_OF_HOUSEHOLD | False             |       0 |                 0 |  93087.5    |            28706.2    |            132890 |            3 |  30484.2  |  30468.4  |        0 |   0      |
| r0_937:t                       | HEAD_OF_HOUSEHOLD | False             |  206720 |                 0 |      0      |                0      |                 0 |            2 |  29398.8  |  29384.8  |        0 |   0      |
| r0_32:t                        | HEAD_OF_HOUSEHOLD | False             |   36150 |                 0 |      0      |                0      |                 0 |            1 |  -3767.66 |  -3777.18 |        0 |   0      |
| r0_840:t                       | HEAD_OF_HOUSEHOLD | False             |   44580 |                 0 |     79.7886 |               20.5144 |                 0 |            1 |  -1471.24 |  -1475.53 |        0 |   0      |
| r0_543:t                       | HEAD_OF_HOUSEHOLD | False             |   42810 |                 0 |      0      |                0      |                 0 |            1 |  -1878.19 |  -1880.1  |        0 |   0      |
| r0_1153:t                      | HEAD_OF_HOUSEHOLD | False             |  203500 |             71360 |   1201.81   |              862.082  |                 0 |            2 |  54235.2  |  54233.6  |        0 |   0      |
| r0_1205:t                      | HEAD_OF_HOUSEHOLD | False             |  204970 |                 0 |      0      |                0      |                 0 |            2 |  29036.8  |  29035.3  |        0 |   0      |
| r0_1430:t                      | JOINT             | False             |  372410 |             47400 |   4028.35   |             7202.28   |             13570 |            1 |  81417.7  |  81416.5  |        0 |   0      |
| r0_1438:t                      | JOINT             | False             |  494730 |                 0 |   1917.51   |             1551.17   |                 0 |            1 | 103338    | 103338    |        0 |   0      |
| r0_740:t                       | JOINT             | False             |  579780 |             15770 |   3840.9    |             5795.79   |                 0 |            1 | 139018    | 139018    |        0 |   0      |
| r0_1252:t                      | HEAD_OF_HOUSEHOLD | False             |  100190 |            172790 |     81.4193 |               45.9631 |                60 |            1 |  51306.4  |  51306.4  |        0 |   0      |
| r0_1361:t                      | HEAD_OF_HOUSEHOLD | False             |   28660 |            833070 |      0      |                0      |                 0 |            3 | 256671    | 256671    |        0 |   0      |
