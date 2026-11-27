"""Hand-authored loophole families (plan deviation, DECISIONS 2026-11-27).

Each family is one flaw in the planted base law B (`PLANTED_BASE`) made of
two changes c1, c2, each relaxing one of two guards that sit in series on
one exploit path. For each magnitude f (0.5, 1):

  base  B (attributable gains are measured against it, not current law)
  L1    B + c1(f);  L2  B + c2(f);  L  B + both
  Lrev  an intended provision made more generous by (1 + f), guards intact

The gate, the witness search, the counting rule and the thresholds are the
ones in `family.py`, unchanged. `households` are witness households the
author adds for the family (none in the pilot).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

from ..law import PLANTED_BASE, Law


def _kiddie(**kw) -> Callable[[Law], Law]:
    return lambda law: replace(law, kiddie=replace(law.kiddie, **kw))


def _planted(**kw) -> Callable[[Law], Law]:
    return lambda law: replace(law, planted=replace(law.planted, **kw))


@dataclass
class HandFamily:
    id: str
    mechanism: str
    c1: Callable[[float], Callable[[Law], Law]]
    c2: Callable[[float], Callable[[Law], Law]]
    rev: Callable[[float], Callable[[Law], Law]]
    description: str = ""
    magnitudes: tuple = (0.5, 1.0)
    households: tuple = field(default_factory=tuple)

    def laws(self, m: float) -> dict:
        b = PLANTED_BASE
        a, c = self.c1(m), self.c2(m)
        return {
            "base": b,
            "L": replace(c(a(b)), label=f"{self.id}@{m:g}"),
            "L1": replace(a(b), label=f"{self.id}@{m:g} c1"),
            "L2": replace(c(b), label=f"{self.id}@{m:g} c2"),
            "Lrev": replace(self.rev(m)(b), label=f"{self.id}@{m:g} reversed"),
        }

    def describe(self) -> dict:
        return {"id": self.id, "mechanism": self.mechanism, "description": self.description, "magnitudes": list(self.magnitudes), "households": [h.id for h in self.households]}


def pilot() -> list[HandFamily]:
    allow = PLANTED_BASE.kiddie.allowance_multiple
    rate = PLANTED_BASE.planted.investor_rate
    return [
        HandFamily(
            "h:kid_gain",
            "income_shifting",
            c1=lambda f: _kiddie(ltcg_exempt=f),
            c2=lambda f: _planted(gift_window=()),
            rev=lambda f: _kiddie(allowance_multiple=allow * (1 + f)),
            description="The kiddie tax leaves out a share of a child's realized long-term gains; donor attribution of recent gifts is removed.",
        ),
        HandFamily(
            "h:kid_credit",
            "credit_shifting",
            c1=lambda f: _planted(investor_dep_share=f),
            c2=lambda f: _planted(gift_window=()),
            rev=lambda f: _planted(investor_rate=rate * (1 + f)),
            description="Dependents may claim the small-investor credit; donor attribution of recent gifts is removed.",
        ),
        HandFamily(
            "h:kid_gain_timing",
            "timing",
            c1=lambda f: _kiddie(ltcg_exempt=f),
            c2=lambda f: _planted(gift_window=(0,)),
            rev=lambda f: _kiddie(allowance_multiple=allow * (1 + f)),
            description="The kiddie tax leaves out a share of a child's realized long-term gains; donor attribution covers only the year of the gift.",
        ),
    ]


def hand_families() -> dict[str, HandFamily]:
    return {f.id: f for f in pilot()}
