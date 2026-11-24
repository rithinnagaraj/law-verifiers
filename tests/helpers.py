"""Small hand-built households for tests."""

from taxgap.model import Asset, Household, Person, TaxUnit


def H(hid, people, units, pairs=(), year=2024, state="TX"):
    if isinstance(units, TaxUnit):
        units = [units]
    return Household(hid, year, state, people, list(units), list(pairs))


def single(wages, age=35, hid="s", **kw):
    return H(hid, {"a": Person("a", age, wages=wages, hours=2080 if wages else 0, **kw)}, TaxUnit("t", "a"))


def couple(w1, w2, kids=(), hid="c", interest_a=0.0):
    people = {"a": Person("a", 45, wages=w1, hours=2080 if w1 else 0), "b": Person("b", 43, wages=w2, hours=2080 if w2 else 0)}
    if interest_a:
        people["a"].assets.append(Asset("bonds", interest_a / 0.05, interest_a / 0.05, interest_yield=0.05))
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    return H(hid, people, TaxUnit("t", "a", "b", [f"k{i}" for i in range(len(kids))]), [("a", "b")])


def parent_child(wages=300_000, interest=20_000, age=10, hid="k", on_child=True):
    p = Person("p", 45, wages=wages, hours=2080)
    c = Person("c", age)
    bond = Asset("bond", interest, interest, interest_yield=1.0)
    (c if on_child else p).assets.append(bond)
    return H(hid, {"p": p, "c": c}, TaxUnit("t", "p", dependents=["c"]))
