# A3: tolerance sensitivity

Sources: 59298 A2 random proposals; canary search 16800 proposals; legitimate-planning dev split 87 scenarios.

Federal canary exploits found by search: 864 distinct, in 6 of 6 canaries.

| cross-check | canary catch rate | caught / exploits | A2 random: code_disagreement | legit positives: code_disagreement | legit positives flagged (any) |
|---|---|---|---|---|---|
| max($5,1%) frozen | 1.000 | 864 / 864 | 0.0038 | 0.000 | 0.209 |
| max($10,1%) | 1.000 | 864 / 864 | 0.0030 | 0.000 | 0.209 |
| max($10,2%) | 1.000 | 864 / 864 | 0.0022 | 0.000 | 0.209 |
| max($10,5%) | 1.000 | 864 / 864 | 0.0012 | 0.000 | 0.209 |
| max($10,10%) | 1.000 | 864 / 864 | 0.0006 | 0.000 | 0.209 |
| ratio 50% | 0.797 | 689 / 864 | 0.0002 | 0.000 | 0.209 |

## Per canary (frozen tolerance max($5, 1%), from A2)

| canary | witness label | exploits | caught | best exploit gain | found by |
|---|---|---|---|---|---|
| hoh_ctc_threshold | code_disagreement | 60 | 60 | 18,757 | greedy,random |
| mfs_std_joint | code_disagreement | 319 | 319 | 43,835 | greedy,random |
| single_bracket2 | code_disagreement | 262 | 262 | 197,619 | greedy,random |
| eitc_no_investment_limit | code_disagreement | 72 | 72 | 7,095 | greedy,random |
| dependent_full_std | code_disagreement | 149 | 149 | 30,719 | greedy,random |
| hoh_ltcg_0pct | code_disagreement | 2 | 2 | 3,600 | greedy,random |
| addl_medicare_mfs | no_gain | 0 | 0 | 0 | - |
