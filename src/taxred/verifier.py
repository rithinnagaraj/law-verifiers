"""The verifier stack (research plan §5.1, experiment plan §1).

evaluate(base, moves, law) answers: does this move sequence give the
household more net resources, with its economic reality unchanged, without
being explained by intended concessions, and do both calculators agree?

Checks, in order:
  1. moves are valid
  2. gain (PolicyEngine: benefits - all taxes) above threshold
  3. economic reality unchanged (labor income, investment yield, wealth, hours)
  4. cross-check: Tax-Calculator confirms the federal income tax part of the
     gain (its federal gain is at least half of PolicyEngine's)
  5. attribution: disable provisions one at a time; whitelisted (intended)
     provisions explaining the gain make it an intended concession

Labels: invalid | no_gain | benefit_cliff | sacrifice | intended_concession |
        code_disagreement | candidate
Coverage tags (experiment plan §1.2): two-calc | single-calc.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional, Sequence

from .household import EconomicSnapshot, Household, economic_snapshot
from .law import PROVISIONS, Law
from .moves import MoveError, apply_moves
from .taxes import HouseholdResult, evaluate_households


@dataclass
class VerifierConfig:
    gain_threshold: float = 50.0  # $ per year (proposed; fixed in E0.8)
    reality_rel_tol: float = 0.005
    reality_abs_tol: float = 1.0
    # Cross-check: the federal gain must be confirmed by Tax-Calculator. It
    # confirms when its federal gain is at least this share of PolicyEngine's.
    # Magnitude differences beyond that are recorded, not fatal.
    crosscheck_min_ratio: float = 0.5
    crosscheck_abs_tol: float = 25.0  # federal gains below this need no confirmation
    federal_share_for_two_calc: float = 0.9
    attribution_share: float = 0.2  # a provision is in the signature if it explains >= this share
    attribution_provisions: tuple = tuple(PROVISIONS)
    run_attribution: bool = True


@dataclass
class Verdict:
    label: str
    gain: float = 0.0
    gain_federal_pe: float = 0.0
    gain_federal_tc: float = 0.0
    gain_other_tax: float = 0.0
    gain_benefits: float = 0.0
    # Gain with the federal part taken at the lower of the two calculators.
    gain_conservative: float = 0.0
    reality_unchanged: Optional[bool] = None
    reality_delta: dict = field(default_factory=dict)
    crosscheck_pass: Optional[bool] = None
    coverage: Optional[str] = None
    attribution: dict = field(default_factory=dict)  # provision -> share of gain explained
    signature: list = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _reality_delta(a: EconomicSnapshot, b: EconomicSnapshot) -> dict:
    return {k: getattr(b, k) - getattr(a, k) for k in a.as_dict()}


def _unchanged(a: EconomicSnapshot, b: EconomicSnapshot, cfg: VerifierConfig) -> bool:
    for k in a.as_dict():
        x, y = getattr(a, k), getattr(b, k)
        if abs(y - x) > max(cfg.reality_abs_tol, cfg.reality_rel_tol * abs(x)):
            return False
    return True


def _gain(base: HouseholdResult, new: HouseholdResult) -> float:
    return new.net_resources - base.net_resources


class Verifier:
    def __init__(self, law: Law, config: Optional[VerifierConfig] = None):
        self.law = law
        self.cfg = config or VerifierConfig()

    # Batched evaluation of many (base, moves) proposals under one law.
    def evaluate_many(self, proposals: Sequence[tuple[Household, list]]) -> list[Verdict]:
        verdicts: list[Optional[Verdict]] = [None] * len(proposals)
        pairs = []  # (index, base, moved)
        for i, (base, moves) in enumerate(proposals):
            try:
                moved = apply_moves(base, moves)
            except MoveError as e:
                verdicts[i] = Verdict("invalid", error=str(e))
                continue
            moved.id = base.id + "~moved"
            pairs.append((i, base, moved))
        if not pairs:
            return verdicts  # type: ignore

        hhs = [h for _, b, m in pairs for h in (b, m)]
        pe = evaluate_households(hhs, self.law, "policyengine")
        tc = evaluate_households(hhs, self.law, "taxcalc", with_benefits=False)

        need_attr = []
        for k, (i, base, moved) in enumerate(pairs):
            pb, pm, tb, tm = pe[2 * k], pe[2 * k + 1], tc[2 * k], tc[2 * k + 1]
            v = Verdict(
                "no_gain",
                gain=_gain(pb, pm),
                gain_federal_pe=pb.fed_income_tax - pm.fed_income_tax,
                gain_federal_tc=tb.fed_income_tax - tm.fed_income_tax,
                gain_other_tax=pb.other_tax - pm.other_tax,
                gain_benefits=(pm.benefits or 0) - (pb.benefits or 0),
            )
            v.gain_conservative = v.gain - max(0.0, v.gain_federal_pe - v.gain_federal_tc)
            sb, sm = economic_snapshot(base), economic_snapshot(moved)
            v.reality_delta = _reality_delta(sb, sm)
            v.reality_unchanged = _unchanged(sb, sm, self.cfg)
            fed_share = v.gain_federal_pe / v.gain if v.gain else 1.0
            v.coverage = "two-calc" if fed_share >= self.cfg.federal_share_for_two_calc else "single-calc"
            v.crosscheck_pass = bool(
                v.gain_federal_pe <= self.cfg.crosscheck_abs_tol
                or v.gain_federal_tc >= self.cfg.crosscheck_min_ratio * v.gain_federal_pe
            )

            if v.gain <= self.cfg.gain_threshold:
                v.label = "no_gain"
            elif not v.reality_unchanged:
                lower_income = v.reality_delta["labor_income"] < 0 or v.reality_delta["investment_yield"] < 0
                v.label = "benefit_cliff" if (lower_income and v.gain_benefits > 0) else "sacrifice"
            elif not v.crosscheck_pass:
                v.label = "code_disagreement"
            else:
                v.label = "candidate"
                need_attr.append((k, i, base, moved, v))
            verdicts[i] = v

        if self.cfg.run_attribution and need_attr:
            self._attribute(need_attr)
        return verdicts  # type: ignore

    def evaluate(self, base: Household, moves: list) -> Verdict:
        return self.evaluate_many([(base, moves)])[0]

    def _attribute(self, items) -> None:
        hhs = [h for (_, _, b, m, _) in items for h in (b, m)]
        for name in self.cfg.attribution_provisions:
            law_off = self.law.without(name)
            pe = evaluate_households(hhs, law_off, "policyengine")
            for j, (_, _, _, _, v) in enumerate(items):
                g_off = _gain(pe[2 * j], pe[2 * j + 1])
                v.attribution[name] = (v.gain - g_off) / v.gain if v.gain else 0.0
        for (_, _, _, _, v) in items:
            v.signature = sorted(p for p, s in v.attribution.items() if s >= self.cfg.attribution_share)
            explained_by_intended = sum(
                s for p, s in v.attribution.items() if PROVISIONS[p].intended and s > 0
            )
            unintended_sig = [p for p in v.signature if not PROVISIONS[p].intended]
            if v.signature and not unintended_sig and explained_by_intended >= 0.9:
                v.label = "intended_concession"
