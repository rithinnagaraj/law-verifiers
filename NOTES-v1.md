# What v1 taught us (carried into v2 as requirements, not code)

The v1 code lives on branch `docs/experiment-plan`; nothing here imports it.
Each item below is a requirement of the v2 code and has a regression test.

| # | Pitfall (v1 finding) | v2 requirement |
|---|---|---|
| F3 | PolicyEngine-US does not apply the child AMT exemption limit. | Known gap; the known-answer test pins it (expected failure). |
| F6 | PolicyEngine imputes an itemizable sales-tax deduction that Tax-Calculator never sees (~95% of v1 disagreements). | PolicyEngine gets state and local sales tax = 0. |
| F8 | Once `tax_unit_itemizes` is an input for one return in a PolicyEngine simulation, every other return gets the input default (standard deduction). | Returns that force the choice and returns that leave it free are simulated separately. |
| F11 | Tax-Calculator keeps the AMT's capital-gains thresholds in separate parameters (`AMT_CG_brk*`); the statute uses the regular ones. A full MARS list in a reform freezes the other statuses at one year. | Parameter catalog pairs regular and AMT thresholds; MARS-indexed reforms change only the targeted status, per evaluated year. |
| F12 | Two copies of one household in a batch overwrote each other's results (ids derived from household ids). | Batch-local ids only; results never keyed by household id. Regression test with duplicates. |
| — | A dependent's income left inside the parent's PolicyEngine unit is taxed nowhere. | A dependent with income files a separate (dependent) return. |
| — | Tax-Calculator applies random EITC/ACTC take-up. | Take-up scales set to full claiming. |
| — | Tax-Calculator records need every column; NaN poisons arithmetic. | Records are filled with 0. |
| — | Tax-Calculator wages are net of 401(k) deferrals (`pencon`). | Adapter subtracts deferrals. |
| — | Survey households outside the overlap: Alaska (PFD imputed as income by PolicyEngine), rental income (treated differently), student-loan interest (deduction limits applied by one calculator), IRA contributions in units with a 401(k) participant. | Excluded or dropped in the survey loader. |
| — | The saver's credit is computed only by PolicyEngine. | Excluded from the federal gain. |
| — | Wash sales and the married-filing rules (no single/HOH while living with the spouse) are checked by neither calculator. | Enforced by the move layer. |
| — | `ProcessPoolExecutor(max_tasks_per_child)` deadlocked; two experiments at once froze the VM (OOM). | Fresh pool per wave; memory-capped systemd scope; one experiment at a time. |
| — | Building a PolicyEngine reform system takes ~10–50 s and ~0.6 GB. | One base system per worker; laws are applied by patching parameters in place and restoring them (tested against PolicyEngine's own Reform). |

## Found in v2 testing (before A2)

| Issue | v2 handling |
|---|---|
| Scale-bracket parameters have no parent link, so PolicyEngine's cache clearing stops at the bracket: a patch could fail to take effect and a restore could leave the patched value (EITC switch-off leaked into later results). | `params._clear_path` clears every cache from the root to the parameter, on patch and on restore; regression test. |
| Saver's credit exclusion had the wrong sign (subtracted instead of added back). | Fixed; regression test. |
| Tax-Calculator allows the EITC and the child-care credit to a separate filer; the statute requires the spouses to live apart, and in this model they live together (PolicyEngine agrees). | `EITC_sep_filers_elig = False`; no care expenses on separate returns in Tax-Calculator. |
| Tax-Calculator cannot force the itemization choice. | No `itemize` move. |
