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
  5. attribution: disable provisions one at a time (signature); then disable
     all whitelisted (intended) provisions together: if <= 10% of the gain
     remains, it is an intended concession

Labels: invalid | no_gain | benefit_cliff | sacrifice | intended_concession |
        code_disagreement | candidate
Coverage tags (experiment plan §1.2): two-calc | single-calc.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Optional, Sequence

from .household import EconomicSnapshot, Household, economic_snapshot
from .law import PROVISIONS, Law
from .moves import MoveError, apply_moves, household_in_year
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
    # "ratio": pass when TC's federal gain >= crosscheck_min_ratio x PE's.
    # "tolerance": pass when the two federal gains agree within
    #   max(crosscheck_abs_tol, crosscheck_rel_tol x |PE gain|) (stricter; the
    #   ratio test passed 44 of 56 child-AMT witnesses that PE gets wrong, F3).
    crosscheck_mode: str = "ratio"
    crosscheck_rel_tol: float = 0.1
    federal_share_for_two_calc: float = 0.9
    attribution_share: float = 0.2  # a provision is in the signature if it explains >= this share
    # Intended concession: with all intended provisions in the attribution set
    # switched off together, at most this share of the gain remains.
    intended_residual_max: float = 0.1
    attribution_provisions: tuple = tuple(PROVISIONS)
    run_attribution: bool = True
    # A gain partly explained by removing an anti-abuse rule stays a candidate.
    anti_abuse_overrides_intended: bool = True
    # Ablation switches (E1.2). Each disables one check.
    use_reality_check: bool = True
    use_crosscheck: bool = True
    use_whitelist: bool = True
    # Attribute every gain above the threshold, not only candidates (so saved
    # verdicts can be relabelled with checks switched off).
    attribute_all: bool = False
    # Tax years evaluated (experiment plan: 3, proposed). Moves may carry a
    # "year"; gains and the reality check are summed over the horizon.
    horizon: int = 1
    # Re-evaluate every flagged proposal on its own and label it
    # "inconsistent" if its gain differs from the batched result (guards
    # against batch-composition bugs such as F8 and F12). Costs one extra
    # evaluation per flagged proposal.
    recheck_flagged: bool = False
    # What counts as gain. "federal" (default since 2026-11-07, the user's
    # decision): only federal income tax, the part both calculators model;
    # benefits, payroll and state tax are recorded (gain_total and its
    # components) but not counted. "all": the earlier net-resources gain.
    gain_scope: str = "federal"


@dataclass
class Verdict:
    label: str
    gain: float = 0.0  # under VerifierConfig.gain_scope
    gain_total: float = 0.0  # benefits minus all taxes (PolicyEngine), for reporting
    gain_kiddie: float = 0.0  # part of the federal gain from package-implemented Form 8615
    gain_federal_pe: float = 0.0
    gain_federal_tc: float = 0.0
    gain_other_tax: float = 0.0
    gain_benefits: float = 0.0
    gain_pe_only_credits: float = 0.0  # part of gain_federal_pe
    # Gain with the federal part taken at the lower of the two calculators.
    gain_conservative: float = 0.0
    reality_unchanged: Optional[bool] = None
    reality_delta: dict = field(default_factory=dict)
    crosscheck_pass: Optional[bool] = None
    crosscheck_tolerance_pass: Optional[bool] = None  # the stricter test, always recorded
    coverage: Optional[str] = None
    attribution: dict = field(default_factory=dict)  # provision -> share of gain explained
    signature: list = field(default_factory=list)
    # Anti-abuse provisions in the signature (the gain gets around them).
    circumvents: list = field(default_factory=list)
    # Share of the gain left when every intended provision is switched off at once.
    residual_without_intended: Optional[float] = None
    error: Optional[str] = None
    recheck_gain: Optional[float] = None  # gain when evaluated alone (recheck_flagged)

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


def _gain(base, new, scope: str = "all") -> float:
    """Gain under the scope: "all" = benefits minus all taxes (PolicyEngine);
    "federal" = the federal income tax both calculators model (PolicyEngine-
    only federal credits excluded)."""
    if scope == "federal":
        return (base.fed_income_tax - base.pe_only_credits) - (new.fed_income_tax - new.pe_only_credits)
    return new.net_resources - base.net_resources


@dataclass
class _Total:
    """A household's results summed over the horizon's years."""

    fed_income_tax: float = 0.0
    other_tax: float = 0.0
    benefits: Optional[float] = None
    pe_only_credits: float = 0.0
    kiddie_adjustment: float = 0.0  # Form 8615 tax computed by this package

    @property
    def net_resources(self) -> float:
        return (self.benefits or 0.0) - self.fed_income_tax - self.other_tax

    def add(self, r: HouseholdResult) -> None:
        self.fed_income_tax += r.fed_income_tax
        self.other_tax += r.other_tax
        self.pe_only_credits += r.pe_only_credits
        self.kiddie_adjustment += r.kiddie_adjustment
        if r.benefits is not None:
            self.benefits = (self.benefits or 0.0) + r.benefits


def _horizon_snapshot(hhs: list[Household]) -> EconomicSnapshot:
    """Flows summed over the horizon; wealth at its end."""
    snaps = [economic_snapshot(h) for h in hhs]
    return EconomicSnapshot(
        labor_income=sum(s.labor_income for s in snaps),
        investment_yield=sum(s.investment_yield for s in snaps),
        wealth=snaps[-1].wealth,
        hours=sum(s.hours for s in snaps),
    )


class Verifier:
    def __init__(self, law: Law, config: Optional[VerifierConfig] = None):
        self.law = law
        self.cfg = config or VerifierConfig()

    def _years(self, base: Household) -> list[int]:
        return [base.year + t for t in range(max(1, self.cfg.horizon))]

    def _totals(self, pairs, law: Law, engine: str, with_benefits: bool = True):
        """[(base total, moved total)] for pairs of per-year household lists,
        each year evaluated under `law` for that year."""
        out = [(_Total(), _Total()) for _ in pairs]
        n_years = len(pairs[0][0])
        for t in range(n_years):
            hhs = [h for b, m in pairs for h in (b[t], m[t])]
            yl = replace(law, year=hhs[0].year)
            res = evaluate_households(hhs, yl, engine, with_benefits=with_benefits)
            for k in range(len(pairs)):
                out[k][0].add(res[2 * k])
                out[k][1].add(res[2 * k + 1])
        return out

    def _totals_both(self, pairs, law: Law):
        """PolicyEngine and Tax-Calculator totals; each year's Tax-Calculator
        run gets PolicyEngine's state income tax as the SALT fact."""
        pe = [(_Total(), _Total()) for _ in pairs]
        tc = [(_Total(), _Total()) for _ in pairs]
        for t in range(len(pairs[0][0])):
            hhs = [h for b, m in pairs for h in (b[t], m[t])]
            yl = replace(law, year=hhs[0].year)
            rp = evaluate_households(hhs, yl, "policyengine")
            rt = evaluate_households(hhs, yl, "taxcalc", with_benefits=False, salt_from=rp)
            for k in range(len(pairs)):
                pe[k][0].add(rp[2 * k]); pe[k][1].add(rp[2 * k + 1])
                tc[k][0].add(rt[2 * k]); tc[k][1].add(rt[2 * k + 1])
        return pe, tc

    # Batched evaluation of many (base, moves) proposals under one law.
    def evaluate_many(self, proposals: Sequence[tuple[Household, list]]) -> list[Verdict]:
        verdicts: list[Optional[Verdict]] = [None] * len(proposals)
        pairs = []  # (index, base years, moved years)
        for i, (base, moves) in enumerate(proposals):
            years = self._years(base)
            try:
                if any(isinstance(m.get("year", base.year), (int, float)) and int(m.get("year", base.year)) > years[-1] for m in moves):
                    raise MoveError("a move is dated after the horizon")
                b_years = [household_in_year(base, [], y) for y in years]
                m_years = [household_in_year(base, moves, y) for y in years]
            except MoveError as e:
                verdicts[i] = Verdict("invalid", error=str(e))
                continue
            for h in m_years:
                h.id = base.id + "~moved"
            pairs.append((i, b_years, m_years))
        if not pairs:
            return verdicts  # type: ignore

        hy = [(b, m) for _, b, m in pairs]
        pe, tc = self._totals_both(hy, self.law)

        need_attr = []
        for k, (i, b_years, m_years) in enumerate(pairs):
            (pb, pm), (tb, tm) = pe[k], tc[k]
            v = Verdict(
                "no_gain",
                gain=_gain(pb, pm, self.cfg.gain_scope),
                gain_total=_gain(pb, pm, "all"),
                gain_federal_pe=pb.fed_income_tax - pm.fed_income_tax,
                gain_federal_tc=tb.fed_income_tax - tm.fed_income_tax,
                gain_other_tax=pb.other_tax - pm.other_tax,
                gain_benefits=(pm.benefits or 0) - (pb.benefits or 0),
            )
            # Federal gain from credits only PolicyEngine computes (saver's
            # credit): not comparable with Tax-Calculator, so it counts as
            # single-calc gain and is left out of the cross-check.
            v.gain_pe_only_credits = pm.pe_only_credits - pb.pe_only_credits
            fed_cmp = v.gain_federal_pe - v.gain_pe_only_credits
            v.gain_conservative = v.gain - max(0.0, fed_cmp - v.gain_federal_tc)
            sb, sm = _horizon_snapshot(b_years), _horizon_snapshot(m_years)
            v.reality_delta = _reality_delta(sb, sm)
            v.reality_unchanged = _unchanged(sb, sm, self.cfg)
            # Gain that comes from this package's own Form 8615 code is common to
            # both calculators, so the cross-check cannot vouch for it.
            v.gain_kiddie = pb.kiddie_adjustment - pm.kiddie_adjustment
            fed_share = fed_cmp / v.gain if v.gain else 1.0
            if v.gain and abs(v.gain_kiddie) >= 0.1 * abs(v.gain):
                v.coverage = "shared-code"
            else:
                v.coverage = "two-calc" if fed_share >= self.cfg.federal_share_for_two_calc else "single-calc"
            v.crosscheck_pass = crosscheck(fed_cmp, v.gain_federal_tc, self.cfg)
            v.crosscheck_tolerance_pass = crosscheck(fed_cmp, v.gain_federal_tc, replace(self.cfg, crosscheck_mode="tolerance"))

            verdicts[i] = v
            v.label = decide_label(v, self.cfg, attributed=False)
            if v.label == "candidate" or (self.cfg.attribute_all and v.gain > self.cfg.gain_threshold):
                need_attr.append((k, i, b_years, m_years, v))

        if self.cfg.run_attribution and need_attr:
            self._attribute(need_attr)
            for (_, _, _, _, v) in need_attr:
                v.label = decide_label(v, self.cfg, attributed=True)
        if self.cfg.recheck_flagged:
            alone = Verifier(self.law, replace(self.cfg, recheck_flagged=False, run_attribution=False))
            for i, (base, moves) in enumerate(proposals):
                v = verdicts[i]
                if v is not None and v.label in ("candidate", "code_disagreement"):
                    v.recheck_gain = alone.evaluate(base, moves).gain
                    if abs(v.recheck_gain - v.gain) > max(1.0, 1e-3 * abs(v.gain)):
                        v.label = "inconsistent"
        return verdicts  # type: ignore

    def evaluate(self, base: Household, moves: list) -> Verdict:
        return self.evaluate_many([(base, moves)])[0]

    def _attribute(self, items) -> None:
        hy = [(b, m) for (_, _, b, m, _) in items]
        for name in self.cfg.attribution_provisions:
            tot = self._totals(hy, self.law.without(name), "policyengine")
            for (_, _, _, _, v), (b, m) in zip(items, tot):
                g_off = _gain(b, m, self.cfg.gain_scope)
                v.attribution[name] = (v.gain - g_off) / v.gain if v.gain else 0.0
        intended = [p for p in self.cfg.attribution_provisions if PROVISIONS[p].intended]
        if intended:
            # Provisions interact (e.g. the kiddie allowance is defined from the
            # dependent standard deduction), so one-at-a-time shares need not
            # add up: also switch all intended provisions off together.
            tot = self._totals(hy, self.law.without_all(intended), "policyengine")
            for (_, _, _, _, v), (b, m) in zip(items, tot):
                g_off = _gain(b, m, self.cfg.gain_scope)
                v.residual_without_intended = g_off / v.gain if v.gain else 0.0
        for (_, _, _, _, v) in items:
            v.signature = sorted(p for p, s in v.attribution.items() if s >= self.cfg.attribution_share)
            v.circumvents = sorted(p for p in v.signature if PROVISIONS[p].anti_abuse)


def crosscheck(fed_pe: float, fed_tc: float, cfg: VerifierConfig) -> bool:
    """Does Tax-Calculator confirm PolicyEngine's (comparable) federal gain?"""
    if cfg.crosscheck_mode == "tolerance":
        return bool(abs(fed_pe - fed_tc) <= max(cfg.crosscheck_abs_tol, cfg.crosscheck_rel_tol * abs(fed_pe)))
    return bool(fed_pe <= cfg.crosscheck_abs_tol or fed_tc >= cfg.crosscheck_min_ratio * fed_pe)


def decide_label(v: Verdict, cfg: VerifierConfig, attributed: bool = True) -> str:
    """The label from a verdict's computed fields under `cfg`. Pure, so the
    E1.2 ablation can relabel saved verdicts with checks switched off."""
    if v.label == "invalid":
        return "invalid"
    if v.gain <= cfg.gain_threshold:
        return "no_gain"
    if cfg.use_reality_check and not v.reality_unchanged:
        lower_income = v.reality_delta.get("labor_income", 0) < 0 or v.reality_delta.get("investment_yield", 0) < 0
        return "benefit_cliff" if (lower_income and v.gain_benefits > 0) else "sacrifice"
    if cfg.use_crosscheck and not v.crosscheck_pass:
        return "code_disagreement"
    if not attributed or not cfg.use_whitelist:
        return "candidate"
    # Getting around an anti-abuse rule (its removal takes away part of the
    # gain) is never an intended concession, even when intended provisions
    # explain the gain (e.g. regaining the EITC by moving assets under the
    # investment-income limit).
    if cfg.anti_abuse_overrides_intended and v.circumvents:
        return "candidate"
    if v.residual_without_intended is not None and v.residual_without_intended <= cfg.intended_residual_max:
        return "intended_concession"
    return "candidate"
