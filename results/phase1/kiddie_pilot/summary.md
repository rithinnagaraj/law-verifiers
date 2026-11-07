# E1.1 pilot: kiddie tax dose-response

Households: 84 per law version. Strategy: gift interest-bearing bond to dependent child.

- Flag rate where no kiddie rule covers the child (should be high): **100.0%**
- Flag rate where a kiddie rule covers the child (should be low): **81.8%**

Flagged = label `candidate` or `code_disagreement` (a gain the verifier does not explain as intended).

## Flag rate

| child      |   none |   tra1986 |   tipra2005 |   sbwota2007 |
|:-----------|-------:|----------:|------------:|-------------:|
| 13         |   1.00 |      0.83 |        0.83 |         0.83 |
| 16         |   1.00 |      1.00 |        0.83 |         0.83 |
| 18         |   1.00 |      1.00 |        1.00 |         0.83 |
| 20         |   1.00 |      1.00 |        1.00 |         1.00 |
| 20 student |   1.00 |      1.00 |        1.00 |         0.75 |
| 22 student |   1.00 |      1.00 |        1.00 |         0.75 |
| 8          |   1.00 |      0.83 |        0.83 |         0.83 |

## Median gain ($/yr)

| child      |   none |   tra1986 |   tipra2005 |   sbwota2007 |
|:-----------|-------:|----------:|------------:|-------------:|
| 13         |   2286 |       904 |         904 |          904 |
| 16         |   2286 |      2286 |         904 |          904 |
| 18         |   2286 |      2286 |        2286 |          904 |
| 20         |   1829 |      1829 |        1829 |         1829 |
| 20 student |   2286 |      2286 |        2286 |          904 |
| 22 student |   2286 |      2286 |        2286 |          904 |
| 8          |   2286 |       904 |         904 |          904 |

## Cross-check failure rate

| child      |   none |   tra1986 |   tipra2005 |   sbwota2007 |
|:-----------|-------:|----------:|------------:|-------------:|
| 13         |   0.25 |      0.08 |        0.08 |         0.08 |
| 16         |   0.25 |      0.25 |        0.08 |         0.08 |
| 18         |   0.25 |      0.25 |        0.25 |         0.08 |
| 20         |   0.00 |      0.00 |        0.00 |         0.00 |
| 20 student |   0.00 |      0.00 |        0.00 |         0.00 |
| 22 student |   0.00 |      0.00 |        0.00 |         0.00 |
| 8          |   0.25 |      0.08 |        0.08 |         0.08 |

## Median share of pre-closure gain removed by each law (closure test; match if >= 0.8)

| child      |   tra1986 |   tipra2005 |   sbwota2007 |
|:-----------|----------:|------------:|-------------:|
| 13         |      0.46 |        0.46 |         0.46 |
| 16         |      0.00 |        0.46 |         0.46 |
| 18         |      0.00 |        0.00 |         0.48 |
| 20         |      0.00 |        0.00 |         0.00 |
| 20 student |      0.00 |        0.00 |         0.48 |
| 22 student |      0.00 |        0.00 |         0.48 |
| 8          |      0.46 |        0.46 |         0.46 |

## Labels

| law        |   candidate |   code_disagreement |   intended_concession |
|:-----------|------------:|--------------------:|----------------------:|
| none       |          72 |                  12 |                     0 |
| sbwota2007 |          66 |                   4 |                    14 |
| tipra2005  |          72 |                   6 |                     6 |
| tra1986    |          72 |                   8 |                     4 |
