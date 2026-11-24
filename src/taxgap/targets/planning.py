"""Legitimate-planning suite v2 (A4).

Positives use intended incentives as designed; expected label: not flagged
(intended_concession or no_gain). Labelled negatives have a known label:
real sacrifices, benefit cliffs (both: sacrifice), wash sales (no_gain),
NIIT-avoiding gifts to children (candidate: the gain is NIIT avoidance,
not an intended concession), and outright donations (sacrifice: wealth
leaves the household).

Split: dev/test 50/50 within each family by hash of the scenario id
(stratified). Only dev is looked at before the pre-registration (A9).
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass

from ..model import Asset, Household, Person, TaxUnit

NOT_FLAGGED = frozenset({"intended_concession", "no_gain"})


@dataclass
class Scenario:
    id: str
    family: str
    household: Household
    moves: list
    expected: frozenset
    positive: bool
    split: str = ""


def _single(hid, wages, age=35, kids=(), state="TX", **kw):
    people = {"a": Person("a", age, wages=wages, hours=2080 if wages else 0, **kw)}
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    return Household(hid, 2024, state, people, [TaxUnit("t", "a", dependents=[f"k{i}" for i in range(len(kids))])]).with_futures()


def _married(hid, w1, w2, age=40, kids=(), state="TX"):
    people = {"a": Person("a", age, wages=w1, hours=2080 if w1 else 0), "b": Person("b", age - 2, wages=w2, hours=2080 if w2 else 0)}
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    return Household(hid, 2024, state, people, [TaxUnit("t", "a", "b", [f"k{i}" for i in range(len(kids))])], [("a", "b")]).with_futures()


def scenarios() -> list[Scenario]:
    out: list[Scenario] = []
    add = lambda sid, fam, hh, mv, exp, pos: out.append(Scenario(sid, fam, hh, mv, frozenset(exp), pos))
    NF = NOT_FLAGGED

    # --- positives -----------------------------------------------------
    for w, age, amt, kids in itertools.product([30_000, 60_000, 100_000, 200_000, 400_000], [35, 55], ["part", "max"], [(), (6,)]):
        lim = 23_000 + (7_500 if age >= 50 else 0)
        a = min(lim, w * 0.5) if amt == "max" else min(5_000, w * 0.1)
        sid = f"k401_s_w{w}_a{age}_{amt}_c{len(kids)}"
        add(sid, "401k", _single(sid, w, age, kids), [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": a}], NF, True)
    for (w1, w2), amt in itertools.product([(50_000, 30_000), (120_000, 80_000), (300_000, 150_000)], ["part", "max"]):
        sid = f"k401_m_w{w1}_{w2}_{amt}"
        add(sid, "401k", _married(sid, w1, w2, kids=(4, 9)), [{"op": "contribute_retirement", "person": "a", "account": "401k", "amount": 23_000 if amt == "max" else 5_000}], NF, True)
    for w, age, kids in itertools.product([20_000, 30_000, 45_000, 70_000, 120_000], [30, 60], [(), (3,)]):
        sid = f"ira_s_w{w}_a{age}_c{len(kids)}"
        add(sid, "ira", _single(sid, w, age, kids), [{"op": "contribute_retirement", "person": "a", "account": "ira", "amount": min(7_000 + (1_000 if age >= 50 else 0), w)}], NF, True)
    for w, cov, age in itertools.product([40_000, 70_000, 110_000, 180_000, 300_000], ["self", "family"], [35, 58]):
        sid = f"hsa_w{w}_{cov}_a{age}"
        hh = _single(sid, w, age, kids=(7,) if cov == "family" else (), hdhp=True)
        cap = (8_300 if cov == "family" else 4_150) + (1_000 if age >= 55 else 0)
        add(sid, "hsa", hh, [{"op": "contribute_hsa", "person": "a", "amount": cap, "coverage": cov}], NF, True)
    for (w1, w2), kids in itertools.product([(90_000, 25_000), (60_000, 15_000), (150_000, 35_000), (45_000, 20_000)], [(5,), (2, 7)]):
        sid = f"claim_w{w1}_{w2}_c{len(kids)}"
        people = {"a": Person("a", 34, wages=w1, hours=2080), "b": Person("b", 32, wages=w2, hours=1500)}
        for i, k in enumerate(kids):
            people[f"k{i}"] = Person(f"k{i}", k)
        hh = Household(sid, 2024, "TX", people, [TaxUnit("ta", "a", dependents=[f"k{i}" for i in range(len(kids))]), TaxUnit("tb", "b")]).with_futures()
        add(sid, "claim_child", hh, [{"op": "assign_dependent", "dependent": f"k{i}", "tax_unit": "tb"} for i in range(len(kids))], NF, True)
    for w, interest, age in itertools.product([60_000, 150_000], [1_000, 2_000, 2_600], [8, 15]):
        sid = f"gift_allow_w{w}_i{interest}_a{age}"
        hh = _single(sid, w, kids=(age,))
        hh.people["a"].assets.append(Asset("bond", interest / 0.05, interest / 0.05, interest_yield=0.05))
        add(sid, "gift_allowance", hh, [{"op": "gift_asset", "giver": "a", "recipient": "k0", "asset": "bond"}], NF, True)
    # Donation bunching: a household that gives every year moves this year's
    # gift into next year (itemizing in alternate years).
    for w, give, mort in itertools.product([90_000, 160_000, 300_000], [6_000, 12_000], [0, 8_000]):
        sid = f"bunch_w{w}_g{give}_m{mort}"
        hh = _married(sid, w, 0, kids=(10,))
        hh.people["a"].charitable_cash = give
        hh.people["a"].mortgage_interest = mort
        mv = [{"op": "reduce_donation", "person": "a", "amount": give, "year": 2024}, {"op": "donate_cash", "person": "a", "amount": give, "year": 2025}]
        add(sid, "bunching", hh, mv, NF, True)
    # Joint vs separate: couples for whom separate filing is allowed; it is
    # rarely better, and then must not be flagged (it is a filing choice).
    for (w1, w2), kids in itertools.product([(60_000, 55_000), (200_000, 30_000), (400_000, 380_000)], [(), (6,)]):
        sid = f"mfs_w{w1}_{w2}_c{len(kids)}"
        add(sid, "joint_vs_separate", _married(sid, w1, w2, kids=kids), [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}], NF, True)
    # Roth conversion when income drops (contingent on the income-drop future).
    for w, bal in itertools.product([60_000, 120_000, 250_000], [50_000, 150_000, 400_000]):
        sid = f"roth_w{w}_b{bal}"
        hh = _single(sid, w, age=50)
        hh.people["a"].ira_balance = bal
        mv = [{"op": "roth_convert", "person": "a", "amount": min(bal, w / 2), "year": 2025, "if_future": "income_drop"}]
        add(sid, "roth_low_income", hh, mv, NF, True)

    # --- labelled negatives ----------------------------------------------
    for w, h in itertools.product([80_000, 200_000, 500_000], [1_000, 1_600]):
        sid = f"sacrifice_w{w}_h{h}"
        add(sid, "sacrifice", _single(sid, w), [{"op": "set_hours", "person": "a", "hours": h}], {"sacrifice", "no_gain"}, False)
    for w, h, kids in itertools.product([25_000, 35_000, 50_000], [1_000, 1_500], [(2,), (2, 6)]):
        sid = f"cliff_w{w}_h{h}_c{len(kids)}"
        add(sid, "benefit_cliff", _single(sid, w, 30, kids), [{"op": "set_hours", "person": "a", "hours": h}], {"sacrifice", "no_gain"}, False)
    for w, loss in itertools.product([60_000, 200_000], [10_000, 30_000]):
        sid = f"wash_w{w}_l{loss}"
        hh = _single(sid, w)
        hh.people["a"].assets.append(Asset("fund", 50_000, 50_000 + loss, dividend_yield=0.02))
        add(sid, "wash_sale", hh, [{"op": "realize_gain", "person": "a", "asset": "fund"}], {"no_gain"}, False)
    for w, interest, age in itertools.product([300_000, 500_000], [5_000, 10_000, 20_000], [8, 15]):
        sid = f"gift_niit_w{w}_i{interest}_a{age}"
        hh = _single(sid, w, kids=(age,))
        hh.people["a"].assets.append(Asset("bond", interest / 0.05, interest / 0.05, interest_yield=0.05))
        add(sid, "gift_niit", hh, [{"op": "gift_asset", "giver": "a", "recipient": "k0", "asset": "bond"}], {"candidate"}, False)
    for w, amt in itertools.product([80_000, 250_000, 600_000], [2_000, 20_000]):
        sid = f"donate_w{w}_d{amt}"
        add(sid, "pure_donation", _single(sid, w), [{"op": "donate_cash", "person": "a", "amount": amt}], {"sacrifice", "no_gain"}, False)

    # --- split ----------------------------------------------------------
    by_fam: dict[str, list[Scenario]] = {}
    for s in out:
        by_fam.setdefault(s.family, []).append(s)
    for fam, ss in by_fam.items():
        ss.sort(key=lambda s: hashlib.sha1(s.id.encode()).hexdigest())
        for i, s in enumerate(ss):
            s.split = "dev" if i % 2 == 0 else "test"
    return out
