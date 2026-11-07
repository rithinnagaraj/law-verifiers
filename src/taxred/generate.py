"""Household archetypes and a seeded random household generator.

The random generator is a stand-in for survey microdata until the
PolicyEngine enhanced-CPS loader is added; its job in Phase 0 is to cover the
provisions both calculators model (wages, self-employment, interest,
qualified dividends, long-term gains, dependents of all ages, dependent
filers, childcare, itemizable expenses) with realistic magnitudes.
"""

from __future__ import annotations

import numpy as np

from .household import Asset, Household, Person, TaxUnit


def archetypes(year: int = 2024, state: str = "TX") -> list[Household]:
    H = lambda i, people, units, pairs=(): Household(i, year, state, people, units, list(pairs))
    return [
        H("single_earner", {"a": Person("a", 35, wages=55_000, hours=2080)}, [TaxUnit("t", "a")]),
        H(
            "dual_earner_kids",
            {
                "a": Person("a", 40, wages=85_000, hours=2080),
                "b": Person("b", 38, wages=45_000, hours=1500),
                "k1": Person("k1", 9),
                "k2": Person("k2", 4),
            },
            [TaxUnit("t", "a", "b", ["k1", "k2"])],
            [("a", "b")],
        ),
        H(
            "single_parent_low_income",
            {"a": Person("a", 29, wages=22_000, hours=1600, childcare_expenses=4_000), "k": Person("k", 3)},
            [TaxUnit("t", "a", dependents=["k"])],
        ),
        H(
            "retiree_investor",
            {
                "a": Person("a", 70, assets=[Asset("fund", 900_000, 400_000, 0.01, 0.025)], long_term_gains=20_000),
                "b": Person("b", 68),
            },
            [TaxUnit("t", "a", "b")],
            [("a", "b")],
        ),
        H(
            "high_earner_with_kids_assets",
            {
                "a": Person("a", 48, wages=350_000, hours=2300, assets=[Asset("bond", 500_000, 500_000, 0.045)]),
                "b": Person("b", 46, self_employment=60_000, hours=1200),
                "k1": Person("k1", 12),
                "k2": Person("k2", 16),
                "k3": Person("k3", 20, is_student=True),
            },
            [TaxUnit("t", "a", "b", ["k1", "k2", "k3"])],
            [("a", "b")],
        ),
    ]


def random_household(rng: np.random.Generator, hid: str, year: int = 2024, state: str = "TX") -> Household:
    people: dict[str, Person] = {}
    kind = rng.choice(["single", "married", "single_parent"], p=[0.35, 0.45, 0.20])

    def adult(pid: str) -> Person:
        age = int(rng.integers(22, 80))
        p = Person(pid, age)
        working = age < 67 and rng.random() < 0.85
        if working:
            p.wages = float(np.round(rng.lognormal(10.8, 0.8), -1))
            p.hours = float(rng.choice([1000, 1600, 2080, 2400]))
            if rng.random() < 0.12:
                p.self_employment = float(np.round(rng.lognormal(10.0, 1.0), -1))
                p.hours += 500
        if rng.random() < 0.40:
            value = float(np.round(rng.lognormal(11.0, 1.5), -2))
            basis = value * float(rng.uniform(0.3, 1.0))
            p.assets.append(Asset(f"{pid}_acct", value, basis, float(rng.uniform(0, 0.04)), float(rng.uniform(0, 0.03))))
        if p.assets and rng.random() < 0.3:
            p.long_term_gains = float(np.round(rng.uniform(0, 0.2) * p.assets[0].unrealized_gain, -1))
        if rng.random() < 0.3:
            p.charitable_cash = float(np.round(rng.lognormal(7.5, 1.0), -1))
        if rng.random() < 0.25:
            p.mortgage_interest = float(np.round(rng.lognormal(9.3, 0.6), -1))
        return p

    a = adult("a")
    people["a"] = a
    unit = TaxUnit("t", "a")
    pairs = []
    if kind == "married":
        b = adult("b")
        b.age = int(np.clip(a.age + rng.integers(-6, 7), 22, 85))
        people["b"] = b
        unit.spouse = "b"
        pairs.append(("a", "b"))
    n_kids = 0 if kind == "single" and rng.random() < 0.8 else int(rng.choice([1, 2, 3], p=[0.45, 0.4, 0.15]))
    if kind == "single_parent":
        n_kids = max(n_kids, 1)
    for i in range(n_kids):
        kid_age = int(rng.integers(0, 23))
        k = Person(f"k{i}", kid_age, is_student=bool(kid_age >= 18 and rng.random() < 0.6))
        if kid_age >= 15 and rng.random() < 0.3:
            k.wages = float(np.round(rng.uniform(1_000, 12_000), -1))
            k.hours = 600.0
        if rng.random() < 0.12:  # dependent with investment income -> files own return
            v = float(np.round(rng.lognormal(10.0, 1.2), -2))
            k.assets.append(Asset(f"k{i}_utma", v, v * 0.7, float(rng.uniform(0.01, 0.05)), float(rng.uniform(0, 0.03))))
        if kid_age < 13 and rng.random() < 0.4:
            a.childcare_expenses += float(np.round(rng.uniform(1_000, 9_000), -1))
        people[k.id] = k
        unit.dependents.append(k.id)
    return Household(hid, year, state, people, [unit], pairs)


def random_households(n: int, seed: int = 0, year: int = 2024, state: str = "TX") -> list[Household]:
    rng = np.random.default_rng(seed)
    return [random_household(rng, f"r{seed}_{i}", year, state) for i in range(n)]
