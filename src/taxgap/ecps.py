"""Survey households from PolicyEngine's enhanced CPS 2024.

`load(n, seed)` samples n households by survey weight (without
replacement) and converts each to a Household with the standard futures.
Households outside the calculators' overlap are excluded: Alaska
(PolicyEngine imputes the Permanent Fund Dividend as federal income) and
households with rental income (treated differently; v1 E0.1). Student-loan
interest is not carried (one calculator applies the deduction limits).

Imputations (the survey has income flows, not balance sheets):
  interest       -> a bond yielding 4% (value = interest / 0.04)
  dividends      -> a fund yielding 2%, cost basis 30-100% of value (seeded)
  IRA balance    -> half the household's SCF retirement assets, on the head
  HDHP coverage  -> a seeded 30% of workers with employer coverage
Contributions are clipped to statutory limits; IRA contributions are dropped
in units with a 401(k) participant (deductibility differs, s.219(g)).
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from .config import CACHE_DIR, ECPS_PATH
from .model import Asset, Household, Person, TaxUnit

PERSON = {
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
    "rental": "rental_income",
}
OTHER = {
    "social_security": "social_security",
    "pension": "taxable_private_pension_income",
    "unemployment": "unemployment_compensation",
    "ira_distributions": "taxable_ira_distributions",
    "short_term_gains": "short_term_capital_gains",
    "nonqualified_dividends": "non_qualified_dividend_income",
    "real_estate_taxes": "real_estate_taxes",
}
EXCLUDE_STATES = ("AK",)
YEAR = 2024


def _arrays() -> dict:
    cache = CACHE_DIR / "ecps_arrays_2024.npz"
    if cache.exists():
        with np.load(cache, allow_pickle=True) as z:
            return {k: z[k] for k in z.files}
    import h5py
    from policyengine_us import Microsimulation

    sim = Microsimulation(dataset=str(ECPS_PATH))
    c = lambda v, to="person": np.asarray(sim.calculate(v, YEAR, map_to=to))
    a = {
        "pid": c("person_id"),
        "hid": c("household_id"),
        "tid": c("tax_unit_id"),
        "age": c("age"),
        "head": c("is_tax_unit_head"),
        "spouse": c("is_tax_unit_spouse"),
        "student": c("is_full_time_college_student"),
        "state": np.asarray([s.decode() if isinstance(s, bytes) else str(s) for s in c("state_code")]),
        "weight": c("household_weight"),
        "childcare_spm": c("spm_unit_pre_subsidy_childcare_expenses"),
        "hh_head": c("is_household_head"),
    }
    for k, v in {**PERSON, **OTHER}.items():
        a[k] = c(v)
    with h5py.File(ECPS_PATH, "r") as f:
        y = str(YEAR)
        ret = dict(zip(f[f"household_id/{y}"][:], f[f"scf_retirement_assets/{y}"][:]))
        esi = dict(zip(f[f"person_id/{y}"][:], f[f"reported_has_employer_sponsored_health_coverage_at_interview/{y}"][:]))
    a["retirement_hh"] = np.array([float(ret.get(h, 0.0)) for h in a["hid"]])
    a["esi"] = np.array([bool(esi.get(p, False)) for p in a["pid"]])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **a)
    return a


def _u(s: str) -> float:
    return int(hashlib.sha1(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _build(ix: np.ndarray, a: dict) -> Household:
    from .moves import limits

    hid = f"ecps{int(a['hid'][ix[0]])}"
    people: dict[str, Person] = {}
    pid_of = {}
    for n, i in enumerate(ix):
        pid = f"p{n}"
        pid_of[i] = pid
        wages = float(max(a["wages"][i], 0.0))
        p = Person(
            pid,
            int(a["age"][i]),
            is_student=bool(a["student"][i]),
            wages=wages,
            self_employment=float(a["self_employment"][i]),
            hours=float(max(a["hours_week"][i], 0.0) * 52),
            ltcg=float(a["ltcg"][i]),
            charitable_cash=float(max(a["charitable_cash"][i], 0.0)),
            mortgage_interest=float(max(a["mortgage_interest"][i], 0.0)),
        )
        lim = limits(YEAR, p.age)
        p.k401 = float(min(max(a["k401"][i], 0.0), wages, lim["401k"]))
        p.ira_contrib = float(min(max(a["ira"][i], 0.0), lim["ira"], max(p.earned_income, 0.0)))
        p.hdhp = bool(a["esi"][i] and p.earned_income > 0 and _u(f"{hid}:{pid}:hdhp") < 0.3)
        if a["hh_head"][i]:
            p.ira_balance = 0.5 * float(max(a["retirement_hh"][i], 0.0))
        if p.earned_income > 0 and p.hours <= 0:
            p.hours = 2080.0
        if a["interest"][i] > 0:
            v = float(a["interest"][i]) / 0.04
            p.assets.append(Asset(f"{pid}_bond", v, v, interest_yield=0.04))
        if a["qdiv"][i] > 0:
            v = float(a["qdiv"][i]) / 0.02
            p.assets.append(Asset(f"{pid}_fund", v, v * (0.3 + 0.7 * _u(f"{hid}:{pid}:basis")), dividend_yield=0.02))
        for k in OTHER:
            if float(a[k][i]) > 0:
                p.other[k] = float(a[k][i])
        people[pid] = p
    units, pairs = [], []
    for t in sorted({int(a["tid"][i]) for i in ix}):
        members = [i for i in ix if int(a["tid"][i]) == t]
        heads = [i for i in members if a["head"][i]]
        if len(heads) != 1:
            raise ValueError(f"tax unit {t} has {len(heads)} heads")
        h = heads[0]
        sp = [i for i in members if a["spouse"][i]]
        tu = TaxUnit(f"t{len(units)}", pid_of[h], pid_of[sp[0]] if sp else None, [pid_of[i] for i in members if i != h and i not in sp])
        if sp:
            pairs.append((pid_of[h], pid_of[sp[0]]))
        filers = [people[tu.head]] + ([people[tu.spouse]] if tu.spouse else [])
        if any(q.k401 > 0 for q in filers):
            for q in filers:
                q.ira_contrib = 0.0
        cc = float(a["childcare_spm"][h])
        if cc > 0 and not any(people[u.head].childcare for u in units):
            people[tu.head].childcare = cc
        units.append(tu)
    hh = Household(hid, YEAR, str(a["state"][ix[0]]), people, units, pairs)
    hh.validate()
    return hh.with_futures()


def load(n: int, seed: int = 0) -> list[Household]:
    cache = CACHE_DIR / f"ecps_households_n{n}_s{seed}.json"
    if cache.exists():
        return [Household.from_dict(d) for d in json.loads(cache.read_text())]
    a = _arrays()
    order = np.argsort(a["hid"], kind="stable")
    _, starts = np.unique(a["hid"][order], return_index=True)
    groups = np.split(order, starts[1:])
    w = np.array([a["weight"][g[0]] for g in groups], dtype=float)
    w *= ~np.isin(np.array([a["state"][g[0]] for g in groups]), EXCLUDE_STATES)
    w *= ~np.array([bool((a["rental"][g] != 0).any()) for g in groups])
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(groups), size=min(n, int((w > 0).sum())), replace=False, p=w / w.sum())
    out = []
    for g in pick:
        try:
            out.append(_build(groups[g], a))
        except ValueError:
            pass
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps([h.to_dict() for h in out]))
    return out
