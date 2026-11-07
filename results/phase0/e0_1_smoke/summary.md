# E0.1 calculator agreement

```json
{
  "n_units": 386,
  "n_households": 305,
  "agree_within_1": 0.966321243523316,
  "agree_within_25": 0.9689119170984456,
  "agree_within_1pct_or_25": 0.9740932642487047,
  "abs_diff_p50": 2.441406240905053e-05,
  "abs_diff_p90": 0.0010600793466437608,
  "abs_diff_p99": 110.14007646896629,
  "abs_diff_max": 301.68007812499854,
  "regular_tax_agree_within_1": 0.9715025906735751,
  "amt_agree_within_1": 1.0,
  "taxable_income_agree_within_1": 0.9689119170984456,
  "by_group": {
    "filing_status": {
      "HEAD_OF_HOUSEHOLD": {
        "n": 77,
        "agree_within_25": 0.974025974025974
      },
      "JOINT": {
        "n": 143,
        "agree_within_25": 0.965034965034965
      },
      "SINGLE": {
        "n": 166,
        "agree_within_25": 0.9698795180722891
      }
    },
    "dependent_filer": {
      "False": {
        "n": 305,
        "agree_within_25": 0.9606557377049181
      },
      "True": {
        "n": 81,
        "agree_within_25": 1.0
      }
    },
    "has_self_employment": {
      "False": {
        "n": 345,
        "agree_within_25": 0.9739130434782609
      },
      "True": {
        "n": 41,
        "agree_within_25": 0.926829268292683
      }
    },
    "has_ltcg_or_qd": {
      "False": {
        "n": 186,
        "agree_within_25": 0.946236559139785
      },
      "True": {
        "n": 200,
        "agree_within_25": 0.99
      }
    },
    "has_kids_u17": {
      "False": {
        "n": 204,
        "agree_within_25": 0.9754901960784313
      },
      "True": {
        "n": 182,
        "agree_within_25": 0.9615384615384616
      }
    },
    "has_student_18_23": {
      "False": {
        "n": 338,
        "agree_within_25": 0.9733727810650887
      },
      "True": {
        "n": 48,
        "agree_within_25": 0.9375
      }
    },
    "has_childcare": {
      "False": {
        "n": 310,
        "agree_within_25": 0.9612903225806452
      },
      "True": {
        "n": 76,
        "agree_within_25": 1.0
      }
    },
    "itemizable_gt_0": {
      "False": {
        "n": 207,
        "agree_within_25": 0.9951690821256038
      },
      "True": {
        "n": 179,
        "agree_within_25": 0.9385474860335196
      }
    },
    "any_65plus": {
      "False": {
        "n": 305,
        "agree_within_25": 0.9606557377049181
      },
      "True": {
        "n": 81,
        "agree_within_25": 1.0
      }
    }
  }
}
```

## Largest disagreements

| unit_id                        | filing_status     | dependent_filer   |   wages |   self_employment |   interest |   qualified_dividends |   long_term_gains |   n_kids_u17 |     pe_fed |     tc_fed |   pe_amt |   tc_amt |
|:-------------------------------|:------------------|:------------------|--------:|------------------:|-----------:|----------------------:|------------------:|-------------:|-----------:|-----------:|---------:|---------:|
| r0_88:t                        | HEAD_OF_HOUSEHOLD | False             |  169370 |                 0 |      0     |                 0     |                 0 |            1 |  22416.9   |  22718.6   |        0 |        0 |
| r0_148:t                       | SINGLE            | False             |  153600 |                 0 |      0     |                 0     |                 0 |            0 |  23637.5   |  23884.9   |        0 |        0 |
| r0_250:t                       | JOINT             | False             |   98940 |                 0 |      0     |                 0     |                 0 |            1 |   2947.8   |   3090     |        0 |        0 |
| r0_51:t                        | JOINT             | False             |   52820 |                 0 |  12053.6   |              7686.03  |              3190 |            1 |    590.236 |    720.436 |        0 |        0 |
| r0_193:t                       | JOINT             | False             |   70930 |                 0 |      0     |                 0     |                 0 |            1 |    243.4   |    350     |        0 |        0 |
| r0_68:t                        | SINGLE            | False             |   74740 |                 0 |      0     |                 0     |                 0 |            0 |   3811.16  |   3906.8   |        0 |        0 |
| r0_125:t                       | SINGLE            | False             |   58170 |              9340 |      0     |                 0     |                 0 |            0 |   4302.57  |   4393.29  |        0 |        0 |
| r0_58:t                        | JOINT             | False             |   47940 |                 0 |    442.789 |               366.57  |               340 |            1 |  -1323.61  |  -1239.71  |        0 |        0 |
| r0_135:t                       | SINGLE            | False             |   35240 |                 0 |      0     |                 0     |                 0 |            0 |   2152.64  |   2224.4   |        0 |        0 |
| r0_187:t                       | SINGLE            | False             |   21340 |                 0 |      0     |                 0     |                 0 |            0 |    602.3   |    655     |        0 |        0 |
| r0_268:t                       | HEAD_OF_HOUSEHOLD | False             |  178510 |             35130 |      0     |                 0     |                 0 |            1 |  34290     |  34248.5   |        0 |        0 |
| high_earner_with_kids_assets:t | JOINT             | False             |  350000 |             60000 |  22500     |                 0     |                 0 |            2 |  77849.9   |  77813     |        0 |        0 |
| r0_32:t                        | HEAD_OF_HOUSEHOLD | False             |   36150 |                 0 |      0     |                 0     |                 0 |            1 |  -3179.49  |  -3189.01  |        0 |        0 |
| r0_225:t                       | JOINT             | False             |  375440 |                 0 |   9606.51  |              6791.08  |                 0 |            1 |  71129.9   |  71129.9   |        0 |        0 |
| r0_274:t                       | JOINT             | False             |  201430 |             22080 |  19998.6   |             11288.4   |                 0 |            0 |  36476     |  36476     |        0 |        0 |
| r0_272:t                       | JOINT             | False             |  315990 |              9170 |   3847.73  |               747.121 |                 0 |            1 |  55761     |  55761     |        0 |        0 |
| r0_75:t                        | JOINT             | False             |  370430 |              9250 |      0     |                 0     |                 0 |            2 |  64582.4   |  64582.4   |        0 |        0 |
| r0_171:t                       | HEAD_OF_HOUSEHOLD | False             |  152420 |            254020 |      0     |                 0     |                 0 |            2 | 101129     | 101129     |        0 |        0 |
| r0_48:t                        | JOINT             | False             |  174070 |                 0 |   1863.37  |              1521.96  |                 0 |            1 |  20615.6   |  20615.6   |        0 |        0 |
| r0_50:t                        | HEAD_OF_HOUSEHOLD | False             |       0 |                 0 | 132802     |             35921.4   |            255080 |            1 |  69652.3   |  69652.3   |        0 |        0 |
| r0_203:t                       | JOINT             | False             |  153160 |                 0 |   7833.54  |              2115.39  |                 0 |            3 |  12217.9   |  12217.9   |        0 |        0 |
| r0_252:t                       | SINGLE            | False             |       0 |                 0 | 138937     |             63445.7   |                 0 |            0 |  32022.8   |  32022.8   |        0 |        0 |
| r0_194:t                       | JOINT             | False             |  309620 |                 0 |  40077     |              8838.88  |             14360 |            0 |  68388.6   |  68388.6   |        0 |        0 |
| r0_289:t                       | JOINT             | False             |   91820 |            169610 |   2698.89  |              2522.75  |              4450 |            3 |  28054.6   |  28054.6   |        0 |        0 |
| r0_106:t                       | JOINT             | False             |   68910 |             22000 |  14046.1   |              7636.13  |             28010 |            1 |   6868.84  |   6868.84  |        0 |        0 |
