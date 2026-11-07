"""Planted-loophole variants (experiment plan E2.1).

A variant is current law with one mutation that opens a loophole exploitable
with the move vocabulary. Each variant knows its loophole by construction:

  law            the mutated law (both calculators get the mutation, so the
                 loophole is two-calc unless the family says otherwise)
  closure        the unmutated law; reverting the mutation is the closure
                 test of the matching rule (experiment plan §1.1)
  witness        a household and move sequence that exploit it
  panel          households to measure reach on
  description    the agent-facing description of the changed rule, plain
                 and disguised (renamed / reworded; the rules calculated
                 are the same)

Families are split for transfer tests (experiment plan §1.5). The kiddie
family is close to the historical kiddie-tax closures, so it is never used
for training (held out with the historical set).

A variant is valid only if its witness is a verified candidate under the
mutated law, and reverting the mutation removes at least `min_reduction` of
the gain (`validate`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable

from .household import Asset, Household, Person, TaxUnit
from .law import KIDDIE_RULES, Law

FS_PE = ["SINGLE", "JOINT", "SEPARATE", "HEAD_OF_HOUSEHOLD", "SURVIVING_SPOUSE"]  # = Tax-Calculator MARS order


def _pe(path: str, year: int) -> float:
    from .taxes import _pe_params

    n = _pe_params()
    for k in path.split("."):
        n = n.children[k]
    return float(n(f"{year}-01-01"))


def _by_status(path: str, year: int, override: dict) -> tuple[dict, tuple]:
    """PE reform {path.STATUS: v} for the overridden statuses, and the
    matching Tax-Calculator MARS override (other statuses keep their
    current-law value in whatever year is evaluated)."""
    from .engines import mars_override

    return {f"{path}.{s}": v for s, v in override.items()}, mars_override(**override)


# ---------------------------------------------------------------------------
# Witness households
# ---------------------------------------------------------------------------


def _couple(hid, year, w1, w2, kids=(), interest_a=0.0, state="TX"):
    people = {
        "a": Person("a", 45, wages=w1, hours=2080 if w1 else 0),
        "b": Person("b", 43, wages=w2, hours=2080 if w2 else 0),
    }
    if interest_a:
        people["a"].assets.append(Asset("bonds", interest_a / 0.05, interest_a / 0.05, interest_yield=0.05))
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    return Household(hid, year, state, people, [TaxUnit("t", "a", "b", [f"k{i}" for i in range(len(kids))])], [("a", "b")])


def _parent_child(hid, year, wages, interest, age, student=False, state="TX"):
    people = {
        "p": Person("p", 45, wages=wages, hours=2080, assets=[Asset("bond", interest / 0.05, interest / 0.05, interest_yield=0.05)]),
        "kid": Person("kid", age, is_student=student),
    }
    return Household(hid, year, state, people, [TaxUnit("t", "p", dependents=["kid"])])


GIFT = [{"op": "gift_asset", "giver": "p", "recipient": "kid", "asset": "bond", "fraction": 1.0}]
SEPARATE = [{"op": "set_filing_status", "tax_unit": "t", "status": "SEPARATE"}]


def _separate_with_kids(n):
    return SEPARATE + [{"op": "assign_dependent", "dependent": f"k{i}", "tax_unit": "t_s"} for i in range(n // 2)]


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


@dataclass
class Variant:
    id: str
    family: str
    operator: str
    magnitude: float
    law: Law
    closure: Law
    witness_household: Household
    witness: list
    panel: list
    description: str
    disguised: str
    coverage: str = "two-calc"
    held_out_family: bool = False
    # Negative control: a mutation that makes an intended provision more
    # generous. Using it as designed is not a loophole; the verifier should
    # label the witness an intended concession, and searches should not
    # count it as a target.
    control: bool = False

    family_split: str = "train"
    horizon: int = 1  # tax years the verifier must evaluate to see the loophole

    @property
    def split(self) -> str:
        """Splits are by provision family (experiment plan §1.5), so transfer is
        measured across families; held-out families are always test."""
        if self.control:
            return "control"
        return "test" if self.held_out_family else self.family_split


@dataclass
class Family:
    name: str
    operator: str
    magnitudes: list
    build: Callable  # (year, magnitude) -> (law_pe, law_tc, desc, disguised, kiddie_rule or None)
    witness: Callable  # (year, magnitude) -> (household, moves)
    panel: Callable  # (year) -> list of households
    coverage: str = "two-calc"
    held_out: bool = False
    control: bool = False
    split: str = "train"  # train | val | test (family-level)
    horizon: int = 1


def _fam_dependent_floor(year, m):
    pe = {"gov.irs.deductions.standard.dependent.amount": m}
    tc = {"STD_Dep": m}
    desc = f"Standard deduction of a taxpayer who can be claimed as a dependent: the greater of ${m:,.0f} or earned income plus ${_pe('gov.irs.deductions.standard.dependent.additional_earned_income', year):,.0f}, not more than the regular standard deduction."
    dis = f"Baseline allowance for a supported filer: a supported filer may subtract at least ${m:,.0f} (or labor receipts plus a small add-on), capped at the ordinary allowance."
    return pe, tc, desc, dis, None


def _fam_mfs_brackets(year, m):
    # Separate filers get m x their current bracket widths and standard deduction (m=2 -> joint).
    pe, tc, parts = {}, {}, []
    for i in range(1, 7):
        cur = _pe(f"gov.irs.income.bracket.thresholds.{i}.SEPARATE", year)
        p, t = _by_status(f"gov.irs.income.bracket.thresholds.{i}", year, {"SEPARATE": cur * m})
        pe.update(p)
        tc[f"II_brk{i}"] = t
    std = _pe("gov.irs.deductions.standard.amount.SEPARATE", year)
    p, t = _by_status("gov.irs.deductions.standard.amount", year, {"SEPARATE": std * m})
    pe.update(p)
    tc["STD"] = t
    desc = f"Married filing separately: rate-bracket thresholds and the standard deduction are {m:g} times their former amounts (standard deduction ${std * m:,.0f})."
    dis = f"Spouses who submit individual returns: every band edge in the graduated schedule and the flat allowance are scaled by {m:g} (allowance ${std * m:,.0f})."
    return pe, tc, desc, dis, None


def _fam_ctc_mfs(year, m):
    p, t = _by_status("gov.irs.credits.ctc.phase_out.threshold", year, {"SEPARATE": m})
    desc = f"Child tax credit: the phase-out threshold for married filing separately is ${m:,.0f}."
    dis = f"Per-minor family offset: tapering for spouses on individual returns starts above ${m:,.0f} of modified income."
    return p, {"CTC_ps": t}, desc, dis, None


def _fam_niit_mfs(year, m):
    p, t = _by_status("gov.irs.investment.net_investment_income_tax.threshold", year, {"SEPARATE": m})
    desc = f"Net investment income tax: the threshold for married filing separately is ${m:,.0f}."
    dis = f"Surcharge on passive returns: for spouses on individual returns it applies above ${m:,.0f} of modified income."
    return p, {"NIIT_thd": t}, desc, dis, None


def _fam_mfs_std(year, m):
    std = _pe("gov.irs.deductions.standard.amount.SEPARATE", year)
    p, t = _by_status("gov.irs.deductions.standard.amount", year, {"SEPARATE": std * m})
    desc = f"Married filing separately: the standard deduction is ${std * m:,.0f} ({m:g} times its former amount)."
    dis = f"Spouses who submit individual returns may subtract a flat ${std * m:,.0f}."
    return p, {"STD": t}, desc, dis, None


def _fam_cg0_single(year, m):
    p, t = _by_status("gov.irs.capital_gains.thresholds.1", year, {"SINGLE": m})
    desc = f"Long-term capital gains: the 0% rate applies to single filers with taxable income up to ${m:,.0f}."
    dis = f"Disposals of long-held property by unattached filers: no levy on the first ${m:,.0f} of taxable income."
    # Tax-Calculator encodes the AMT's 0% capital-gains threshold as its own
    # parameter; the statute (s.55(b)(3)) uses the regular one, so both move
    # (finding F11: without it TC taxed the planted gain through the AMT).
    return p, {"CG_brk1": t, "AMT_CG_brk1": t}, desc, dis, None


def _parents_adult_child(hid, year, wages=150_000, value=300_000, basis=100_000, child_age=25):
    """Married parents with an appreciated fund they plan to sell in the
    horizon's last year, and an adult child (own return, no income)."""
    people = {
        "p": Person("p", 55, wages=wages, hours=2080, assets=[Asset("fund", value, basis, sale_year=year + 2)]),
        "s": Person("s", 53),
        "c": Person("c", child_age),
    }
    return Household(hid, year, "TX", people, [TaxUnit("t", "p", "s"), TaxUnit("tc", "c")], [("p", "s")])


def _fam_actc_rate(year, m):
    pe = {"gov.irs.credits.ctc.refundable.phase_in.rate": m}
    desc = f"Refundable child tax credit: phases in at {m:.0%} of earned income above $2,500 (was 15%)."
    dis = f"Per-minor family offset, payable portion: accrues at {m:.0%} of labor receipts above a small floor."
    return pe, {"ACTC_rt": m}, desc, dis, None


def _partners_actc(hid, year, se=60_000, interest_b=12_000, kids=(4, 8)):
    """Unmarried partners: A self-employed, B with the children and enough
    investment income to be barred from the EITC (so only the ACTC moves)."""
    people = {
        "a": Person("a", 40, self_employment=se, hours=2080),
        "b": Person("b", 38, assets=[Asset("bonds", interest_b / 0.05, interest_b / 0.05, interest_yield=0.05)]),
    }
    for i, k in enumerate(kids):
        people[f"k{i}"] = Person(f"k{i}", k)
    return Household(hid, year, "TX", people, [TaxUnit("ta", "a"), TaxUnit("tb", "b", dependents=[f"k{i}" for i in range(len(kids))])])


def _fam_kiddie_age(year, m):
    rule = KIDDIE_RULES["current"]
    from dataclasses import replace

    r = replace(rule, age_under=int(m), student_age_under=int(m), label=f"kiddie <{int(m)}")
    desc = f"Tax on a child's unearned income at the parent's rate applies to children under {int(m)} (students too)."
    dis = f"Supported-minor passive-receipts rule: applies to minors below {int(m)} years, enrolled or not."
    return {}, {}, desc, dis, r


def _fam_kiddie_allowance(year, m):
    rule = KIDDIE_RULES["current"]
    from dataclasses import replace

    r = replace(rule, allowance_multiple=float(m), label=f"kiddie allowance x{m:g}")
    desc = f"Tax on a child's unearned income at the parent's rate applies only above {m:g} times the dependent standard-deduction floor."
    dis = f"Supported-minor passive-receipts rule: the first {m:g} baseline allowances of passive receipts are exempt."
    return {}, {}, desc, dis, r


FAMILIES: dict[str, Family] = {
    f.name: f
    for f in [
        Family(
            "dependent_floor",
            "move_threshold",
            [4_000, 8_000, 12_000],
            _fam_dependent_floor,
            lambda y, m: (_parent_child("w", y, 150_000, 20_000, 10), GIFT),
            lambda y: [_parent_child(f"pc{w}_{i}_{a}", y, w, i, a) for w in (60_000, 150_000, 400_000) for i in (5_000, 20_000) for a in (8, 15)],
            control=True,
        ),
        Family(
            "mfs_brackets",
            "decouple",
            [1.5, 2.0],
            _fam_mfs_brackets,
            lambda y, m: (_couple("w", y, 150_000, 120_000), SEPARATE),
            lambda y: [_couple(f"c{a}_{b}", y, a, b) for a, b in ((80_000, 60_000), (150_000, 120_000), (300_000, 250_000), (500_000, 100_000))],
        ),
        Family(
            "ctc_mfs",
            "move_threshold",
            [300_000, 400_000],
            _fam_ctc_mfs,
            lambda y, m: (_couple("w", y, 350_000, 300_000, kids=(4, 9)), _separate_with_kids(2)),
            lambda y: [_couple(f"c{a}_{b}", y, a, b, kids=(4, 9)) for a, b in ((250_000, 200_000), (350_000, 300_000), (500_000, 150_000))],
        ),
        Family(
            "niit_mfs",
            "move_threshold",
            [200_000, 250_000],
            _fam_niit_mfs,
            lambda y, m: (_couple("w", y, 0, 180_000, interest_a=180_000), SEPARATE),
            lambda y: [_couple(f"c{a}_{i}", y, 0, a, interest_a=i) for a in (150_000, 180_000, 220_000) for i in (150_000, 190_000)],
            split="val",
        ),
        Family(
            "mfs_std",
            "move_threshold",
            [1.5, 2.0],
            _fam_mfs_std,
            lambda y, m: (_couple("w", y, 120_000, 100_000), SEPARATE),
            lambda y: [_couple(f"c{a}_{b}", y, a, b) for a, b in ((60_000, 50_000), (120_000, 100_000), (250_000, 200_000))],
            split="val",
        ),
        Family(
            "actc_rate",
            "sharpen_phase_in",
            [0.3, 0.5],
            _fam_actc_rate,
            lambda y, m: (_partners_actc("w", y), [{"op": "shift_income", "payer": "a", "payee": "b", "amount": 10_000}]),
            lambda y: [_partners_actc(f"p{s}_{k}", y, se=s, kids=(4, 8)[:k]) for s in (40_000, 60_000, 100_000) for k in (1, 2)],
        ),
        Family(
            "cg0_single",
            "move_threshold",
            [150_000, 250_000],
            _fam_cg0_single,
            lambda y, m: (_parents_adult_child("w", y), [{"op": "gift_asset", "giver": "p", "recipient": "c", "asset": "fund", "fraction": 1.0}]),
            lambda y: [_parents_adult_child(f"pc{w}_{v}", y, wages=w, value=v, basis=v / 3) for w in (80_000, 200_000) for v in (150_000, 400_000)],
            split="val",
            horizon=3,
        ),
        Family(
            "kiddie_age",
            "move_threshold",
            [10, 12],
            _fam_kiddie_age,
            lambda y, m: (_parent_child("w", y, 200_000, 20_000, 15), GIFT),
            lambda y: [_parent_child(f"pc{w}_{i}_{a}", y, w, i, a) for w in (100_000, 300_000) for i in (5_000, 20_000) for a in (11, 13, 16)],
            coverage="internal",
            held_out=True,
        ),
        Family(
            "kiddie_allowance",
            "remove_limit",
            [5, 10],
            _fam_kiddie_allowance,
            lambda y, m: (_parent_child("w", y, 200_000, m * 1_300, 10), GIFT),
            lambda y: [_parent_child(f"pc{w}_{i}_{a}", y, w, i, a) for w in (100_000, 300_000) for i in (5_000, 10_000, 20_000) for a in (8, 15)],
            coverage="internal",
            held_out=True,
        ),
    ]
}


def variants(year: int = 2024, families=None) -> list[Variant]:
    base = Law(year)
    out = []
    for f in FAMILIES.values():
        if families and f.name not in families:
            continue
        for m in f.magnitudes:
            pe, tc, desc, dis, kiddie = f.build(year, m)
            law = base.with_reform(pe, tc, label=f"{f.name}={m:g}")
            if kiddie is not None:
                from dataclasses import replace

                law = replace(law, kiddie=kiddie)
            hh, moves = f.witness(year, m)
            out.append(
                Variant(
                    id=f"{f.name}_{m:g}",
                    family=f.name,
                    operator=f.operator,
                    magnitude=m,
                    law=law,
                    closure=base,
                    witness_household=hh,
                    witness=moves,
                    panel=f.panel(year),
                    description=desc,
                    disguised=dis,
                    coverage=f.coverage,
                    held_out_family=f.held_out,
                    control=f.control,
                    family_split=f.split,
                    horizon=f.horizon,
                )
            )
    return out
