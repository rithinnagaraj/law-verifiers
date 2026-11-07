"""Survey households from PolicyEngine's enhanced CPS (stage 1, realistic).

`load_households(n, seed)` samples n households, weighted by survey weight,
and converts each to a `Household`: people with ages, incomes and deductions,
tax units with PolicyEngine's head / spouse / dependent roles, state.

The file is public (hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5,
~108 MB); set TAXRED_ECPS to its local path (default ~/data/enhanced_cps_2024.h5).

Imputations (the survey has income flows, not balance sheets):
  - taxable interest -> a bond with a 4% yield (value = interest / 0.04);
  - qualified dividends -> an equity fund with a 2% dividend yield and a cost
    basis of 30-100% of value (seeded per household);
  - realized long-term gains, non-qualified dividends and the OTHER_ITEMS
    (Social Security, pensions, unemployment, rental, IRA distributions,
    short-term gains, real-estate tax, student-loan interest) are exogenous;
  - 401(k) and IRA contributions are clipped to the statutory limits; IRA
    contributions are dropped in units with a 401(k) participant (deductibility
    under s.219(g) is computed by PolicyEngine only);
  - HSA eligibility (HDHP): 30% of workers with employer coverage, seeded;
  - traditional IRA balance: half of the household's SCF retirement assets, on
    the household head;
  - negative rental income is set to 0 (passive-loss rules differ between the
    calculators and are outside the move vocabulary).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .household import Asset, Household, Person, TaxUnit

DEFAULT_PATH = Path(os.environ.get("TAXRED_ECPS", Path.home() / "data" / "enhanced_cps_2024.h5"))
CACHE_DIR = Path(os.environ.get("TAXRED_ECPS_CACHE", Path.home() / "data"))

PERSON_VARS = {
    "wages": "employment_income",
    "self_employment": "self_employment_income",
    "interest": "taxable_interest_income",
    "qdiv": "qualified_dividend_income",
    "ltcg": "long_term_capital_gains",
    "charitable_cash": "charitable_cash_donations",
    "mortgage_interest": "home_mortgage_interest",
    "hours_week": "weekly_hours_worked",
    "k401": "traditional_401k_contributions",
    "ira": "traditional_ira_contributions",
}
OTHER_VARS = {
    "social_security": "social_security",
    "pension": "taxable_private_pension_income",
    "unemployment": "unemployment_compensation",
    "rental": "rental_income",
    "ira_distributions": "taxable_ira_distributions",
    "short_term_gains": "short_term_capital_gains",
    "nonqualified_dividends": "non_qualified_dividend_income",
    "real_estate_taxes": "real_estate_taxes",
}


def _extract(path: Path, year: int) -> dict:
    """Arrays for every person from a PolicyEngine microsimulation."""
    from policyengine_us import Microsimulation

    sim = Microsimulation(dataset=str(path))
    c = lambda v, map_to="person": np.asarray(sim.calculate(v, year, map_to=map_to))
    out = {
        "pid": c("person_id"),
        "hid": c("household_id", "person"),
        "tid": c("tax_unit_id", "person"),
        "sid": c("spm_unit_id", "person"),
        "age": c("age"),
        "head": c("is_tax_unit_head"),
        "spouse": c("is_tax_unit_spouse"),
        "dep": c("is_tax_unit_dependent"),
        "student": c("is_full_time_college_student"),
        "state": c("state_code", "person"),
        "weight": c("household_weight", "person"),
        "childcare_spm": c("spm_unit_pre_subsidy_childcare_expenses", "person"),
        "retirement_hh": c("scf_retirement_assets", "person"),
        "hh_head": c("is_household_head"),
        "esi": c("reported_has_employer_sponsored_health_coverage_at_interview"),
    }
    for k, v in {**PERSON_VARS, **OTHER_VARS}.items():
        out[k] = c(v)
    return out


def _hash01(s: str) -> float:
    return int(hashlib.sha1(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _build(ix: np.ndarray, a: dict, year: int) -> Household:
    hid = int(a["hid"][ix[0]])
    hh_id = f"ecps{hid}"
    people: dict[str, Person] = {}
    pid_of = {}
    for n, i in enumerate(ix):
        pid = f"p{n}"
        pid_of[i] = pid
        p = Person(
            pid,
            int(a["age"][i]),
            wages=float(max(a["wages"][i], 0.0)),
            self_employment=float(a["self_employment"][i]),
            hours=float(max(a["hours_week"][i], 0.0) * 52),
            is_student=bool(a["student"][i]),
            long_term_gains=float(a["ltcg"][i]),
            charitable_cash=float(max(a["charitable_cash"][i], 0.0)),
            mortgage_interest=float(max(a["mortgage_interest"][i], 0.0)),
            traditional_401k=float(min(max(a["k401"][i], 0.0), max(a["wages"][i], 0.0))),
            traditional_ira=float(max(a["ira"][i], 0.0)),
        )
        # Bright-line statutory limits, as the moves enforce them.
        from .moves import _retirement_limits

        lim = _retirement_limits(year, p.age)
        p.traditional_401k = min(p.traditional_401k, lim["401k"])
        p.traditional_ira = min(p.traditional_ira, lim["ira"], max(p.earned_income, 0.0))
        # HSA eligibility: a seeded 30% of workers with employer coverage (about
        # the share of covered workers in HSA-eligible plans; an imputation).
        p.hdhp = bool(a["esi"][i] and p.earned_income > 0 and _hash01(f"{hh_id}:{pid}:hdhp") < 0.3)
        # Traditional IRA balance: half of the household's SCF-imputed
        # retirement assets, held by the household head (an imputation).
        if a["hh_head"][i]:
            p.ira_balance = 0.5 * float(max(a["retirement_hh"][i], 0.0))
        if p.earned_income > 0 and p.hours <= 0:
            p.hours = 2080.0  # survey hours missing for a worker
        if a["interest"][i] > 0:
            v = float(a["interest"][i]) / 0.04
            p.assets.append(Asset(f"{pid}_bond", v, v, interest_yield=0.04))
        if a["qdiv"][i] > 0:
            v = float(a["qdiv"][i]) / 0.02
            share = 0.3 + 0.7 * _hash01(f"{hh_id}:{pid}:basis")
            p.assets.append(Asset(f"{pid}_fund", v, v * share, qualified_dividend_yield=0.02))
        for k in OTHER_VARS:
            val = float(a[k][i])
            if k == "rental":
                val = max(val, 0.0)
            if val > 0:
                p.other[k] = val
        people[pid] = p
    # tax units with PolicyEngine's roles
    units, pairs = [], []
    for t in sorted({int(a["tid"][i]) for i in ix}):
        members = [i for i in ix if int(a["tid"][i]) == t]
        heads = [i for i in members if a["head"][i]]
        if len(heads) != 1:
            raise ValueError(f"tax unit {t} has {len(heads)} heads")
        h = heads[0]
        sp = [i for i in members if a["spouse"][i]]
        deps = [pid_of[i] for i in members if i != h and i not in sp]
        tu = TaxUnit(f"t{t}", pid_of[h], pid_of[sp[0]] if sp else None, deps)
        if sp:
            pairs.append((pid_of[h], pid_of[sp[0]]))
        units.append(tu)
        # Survey IRA contributions are kept only where they are fully
        # deductible under the rule both calculators share (no 401(k)
        # participant in the unit): Tax-Calculator takes e03150 as the
        # deductible amount, PolicyEngine applies s.219(g).
        filers = [people[tu.head]] + ([people[tu.spouse]] if tu.spouse else [])
        if any(q.traditional_401k > 0 for q in filers):
            for q in filers:
                q.traditional_ira = 0.0
        # childcare: the SPM unit's expenses go to the first tax-unit head in it
        cc = float(a["childcare_spm"][h])
        if cc > 0 and not any(people[u.head].childcare_expenses for u in units[:-1]):
            people[pid_of[h]].childcare_expenses = cc
    state = a["state"][ix[0]]
    state = state.decode() if isinstance(state, bytes) else str(state)
    return Household(hh_id, year, state, people, units, pairs)


def load_households(n: int, seed: int = 0, year: int = 2024, states: list | None = None, path: Path = DEFAULT_PATH) -> list[Household]:
    """n survey households, sampled by weight without replacement (cached)."""
    tag = f"ecps_{year}_n{n}_s{seed}" + (f"_{'-'.join(sorted(states))}" if states else "")
    cache = CACHE_DIR / f"{tag}.json"
    if cache.exists():
        return [Household.from_dict(d) for d in json.loads(cache.read_text())]
    a = _extract(path, year)
    order = np.argsort(a["hid"], kind="stable")
    hids, starts = np.unique(a["hid"][order], return_index=True)
    groups = np.split(order, starts[1:])
    w = np.array([a["weight"][g[0]] for g in groups], dtype=float)
    if states:
        keep = np.array([str(a["state"][g[0]].decode() if isinstance(a["state"][g[0]], bytes) else a["state"][g[0]]) in states for g in groups])
        w = w * keep
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(groups), size=min(n, int((w > 0).sum())), replace=False, p=w / w.sum())
    out, skipped = [], 0
    for g in pick:
        try:
            hh = _build(groups[g], a, year)
            hh.validate()
            out.append(hh)
        except ValueError:
            skipped += 1
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps([h.to_dict() for h in out]))
    if skipped:
        print(f"[ecps] skipped {skipped} households with inconsistent tax-unit roles")
    return out
