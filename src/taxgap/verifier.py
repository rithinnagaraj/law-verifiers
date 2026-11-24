"""The verifier (research plan v2, section 6.1).

`Verifier(law, config).evaluate(proposals)` labels each (household, moves):

  invalid             a move breaks a rule of the vocabulary
  no_gain             federal gain <= threshold
  sacrifice           economic reality changed in some future
  code_disagreement   the two calculators disagree on the gain beyond the tolerance
  intended_concession at most 10% of the gain is left with every whitelisted
                      provision switched off, and no anti-abuse rule is got round
  candidate           everything else with a gain
  inconsistent        a flagged proposal re-evaluated alone gives a different gain

Gain = reduction in federal income tax over the horizon, probability-weighted
over the household's futures, PolicyEngine-only credits excluded; terminal
valuation where moves change a traditional IRA balance. `gain` is
PolicyEngine's; `gain_tc` is Tax-Calculator's on the same returns.
Attribution (whitelist, anti-abuse) uses PolicyEngine only.

`label(verdict, config)` is pure, so saved verdicts can be relabelled under
other settings (tolerance sweep A3, whitelist off).
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field, replace
from typing import Optional, Sequence

from .calc.evaluate import YearTax, evaluate
from .law import ANTI_ABUSE, WHITELIST, WHITELIST_EXTENDED, Law
from .model import Household, Reality
from .moves import MoveError, years_of


@dataclass(frozen=True)
class Config:
    threshold: float = 50.0  # $ over the horizon
    tol_abs: float = 10.0  # cross-check: |gain_pe - gain_tc| <= max(tol_abs, tol_rel x |gain_pe|)
    tol_rel: float = 0.02
    reality_abs: float = 1.0
    reality_rel: float = 0.005
    whitelist: str = "plan"  # plan (research plan list) | extended (+ HSA, charitable deduction)
    intended_residual_max: float = 0.10
    circumvent_share: float = 0.20  # an anti-abuse rule is got round if removing it takes >= this share
    shared_code_share: float = 0.10
    use_reality: bool = True
    use_crosscheck: bool = True
    use_whitelist: bool = True
    attribute: bool = True  # run attribution for candidates
    attribute_all: bool = False  # ... and for every proposal with a gain
    recheck: bool = True  # re-evaluate flagged proposals alone
    terminal: bool = True


@dataclass
class Verdict:
    label: str
    gain: float = 0.0
    gain_tc: float = 0.0
    gain_kiddie: float = 0.0  # part of the PolicyEngine gain from this package's Form 8615
    future_gains: dict = field(default_factory=dict)
    reality_ok: Optional[bool] = None
    reality_delta: dict = field(default_factory=dict)
    coverage: Optional[str] = None
    attribution: dict = field(default_factory=dict)  # anti-abuse provision -> share explained
    residual: Optional[float] = None  # share left with the plan whitelist off
    residual_ext: Optional[float] = None  # ... with the extended whitelist off
    error: Optional[str] = None
    recheck_gain: Optional[float] = None
    recheck_gain_tc: Optional[float] = None

    @property
    def disagreement(self) -> float:
        return abs(self.gain - self.gain_tc)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Verdict":
        return Verdict(**d)


def crosscheck_ok(v: Verdict, cfg: Config) -> bool:
    return v.disagreement <= max(cfg.tol_abs, cfg.tol_rel * abs(v.gain))


def circumvents(v: Verdict, cfg: Config) -> list:
    return sorted(p for p, s in v.attribution.items() if s >= cfg.circumvent_share)


def label(v: Verdict, cfg: Config) -> str:
    """The label from a verdict's numbers under `cfg` (pure)."""
    if v.error is not None:
        return "invalid"
    if v.gain <= cfg.threshold:
        return "no_gain"
    if cfg.use_reality and not v.reality_ok:
        return "sacrifice"
    if cfg.use_crosscheck and not crosscheck_ok(v, cfg):
        return "code_disagreement"
    if v.recheck_gain is not None and (
        abs(v.recheck_gain - v.gain) > max(1.0, 1e-3 * abs(v.gain))
        or abs((v.recheck_gain_tc or 0.0) - v.gain_tc) > max(1.0, 1e-3 * abs(v.gain_tc))
    ):
        return "inconsistent"
    res = v.residual_ext if cfg.whitelist == "extended" else v.residual
    if cfg.use_whitelist and res is not None and not circumvents(v, cfg) and res <= cfg.intended_residual_max:
        return "intended_concession"
    return "candidate"


FLAGGED = ("candidate", "code_disagreement")


@dataclass
class _Prepared:
    futures: list  # [(prob, name, base years, moved years)]


def _liquidated(h: Household) -> Household:
    c = copy.deepcopy(h)
    for p in c.people.values():
        if p.ira_balance > 0:
            p.other["ira_distributions"] = p.other.get("ira_distributions", 0.0) + p.ira_balance
            p.ira_balance = 0.0
    return c


def _needs_terminal(b: Household, m: Household) -> bool:
    return any(abs(b.people[k].ira_balance - m.people[k].ira_balance) > 1.0 for k in b.people if k in m.people)


def prepare(hh: Household, moves: list) -> _Prepared:
    fs = hh.futures or [None]
    out = []
    for f in fs:
        b = years_of(hh, [], f)
        m = years_of(hh, moves, f)
        out.append((f.prob if f else 1.0, f.name if f else None, b, m))
    return _Prepared(out)


def _sides(prep: _Prepared, terminal: bool) -> list:
    """Per future: (prob, name, base items, moved items) with terminal
    valuation applied (final year replaced by its liquidated version)."""
    out = []
    for prob, name, b, m in prep.futures:
        b, m = list(b), list(m)
        if terminal and _needs_terminal(b[-1], m[-1]):
            b[-1], m[-1] = _liquidated(b[-1]), _liquidated(m[-1])
        out.append((prob, name, b, m))
    return out


def gains(preps: Sequence[_Prepared], law: Law, with_tc: bool = True, terminal: bool = True, fresh: bool = False) -> list[dict]:
    """[{gain, gain_tc, gain_kiddie, future_gains}] for prepared proposals."""
    sides = [_sides(p, terminal) for p in preps]
    items = [h for s in sides for (_, _, b, m) in s for h in (b + m)]
    res = iter(evaluate(items, law, fresh=fresh, with_tc=with_tc))
    out = []
    for s in sides:
        g = {"gain": 0.0, "gain_tc": 0.0, "gain_kiddie": 0.0, "future_gains": {}}
        for prob, name, b, m in s:
            rb: list[YearTax] = [next(res) for _ in b]
            rm: list[YearTax] = [next(res) for _ in m]
            # PolicyEngine tax without the PolicyEngine-only credits (the saver's
            # credit reduces tax, so it is added back), comparable with Tax-Calculator.
            gp = sum(x.pe + x.pe_only for x in rb) - sum(x.pe + x.pe_only for x in rm)
            gt = sum(x.tc for x in rb) - sum(x.tc for x in rm) if with_tc else 0.0
            gk = sum(x.kiddie_pe for x in rb) - sum(x.kiddie_pe for x in rm)
            g["gain"] += prob * gp
            g["gain_tc"] += prob * gt
            g["gain_kiddie"] += prob * gk
            if name is not None:
                g["future_gains"][name] = gp
        out.append(g)
    return out


def _reality(prep: _Prepared, cfg: Config) -> tuple[bool, dict]:
    ok, worst = True, {}
    for _, _, b, m in prep.futures:
        rb, rm = Reality(), Reality()
        for k, (hb, hm) in enumerate(zip(b, m)):
            last = k == len(b) - 1
            rb.add_year(hb, last)
            rm.add_year(hm, last)
        delta = {k: getattr(rm, k) - getattr(rb, k) for k in rb.as_dict()}
        bad = any(abs(delta[k]) > max(cfg.reality_abs, cfg.reality_rel * abs(getattr(rb, k))) for k in delta)
        if bad or not worst:
            worst = delta
        if bad:
            ok = False
            break
    return ok, worst


class Verifier:
    def __init__(self, law: Law, cfg: Optional[Config] = None):
        self.law = law
        self.cfg = cfg or Config()

    def evaluate(self, proposals: Sequence[tuple[Household, list]]) -> list[Verdict]:
        cfg = self.cfg
        verdicts: list[Optional[Verdict]] = [None] * len(proposals)
        preps, idx = [], []
        for i, (hh, moves) in enumerate(proposals):
            try:
                preps.append(prepare(hh, moves))
                idx.append(i)
            except MoveError as e:
                verdicts[i] = Verdict("invalid", error=str(e))
        for i, p, g in zip(idx, preps, gains(preps, self.law, True, cfg.terminal)):
            ok, delta = _reality(p, cfg)
            v = Verdict("pending", g["gain"], g["gain_tc"], g["gain_kiddie"], g["future_gains"], ok, delta)
            v.coverage = "shared-code" if v.gain > 0 and abs(v.gain_kiddie) >= cfg.shared_code_share * v.gain else "two-calc"
            verdicts[i] = v
        prep_of = dict(zip(idx, preps))
        need = [i for i in idx if self._needs_attribution(verdicts[i])]
        if cfg.attribute and need:
            self._attribute([prep_of[i] for i in need], [verdicts[i] for i in need])
        if cfg.recheck:
            pre = Config(**{**asdict(cfg), "attribute": False, "recheck": False})
            flagged = [i for i in idx if label(verdicts[i], replace(pre, use_whitelist=False)) in FLAGGED]
            for i in flagged:
                g = gains([prep_of[i]], self.law, True, cfg.terminal, fresh=True)[0]
                verdicts[i].recheck_gain, verdicts[i].recheck_gain_tc = g["gain"], g["gain_tc"]
        for v in verdicts:
            v.label = label(v, cfg)
        return verdicts  # type: ignore

    def _needs_attribution(self, v: Verdict) -> bool:
        if v.gain <= self.cfg.threshold:
            return False
        if self.cfg.attribute_all:
            return True
        pre = replace(self.cfg, use_whitelist=False)
        return label(v, pre) == "candidate"

    def _attribute(self, preps: list, vs: list) -> None:
        for name in ANTI_ABUSE:
            for v, g in zip(vs, gains(preps, self.law.without(name), False, self.cfg.terminal)):
                v.attribution[name] = (v.gain - g["gain"]) / v.gain if v.gain else 0.0
        for attr, wl in (("residual", WHITELIST), ("residual_ext", WHITELIST_EXTENDED)):
            for v, g in zip(vs, gains(preps, self.law.without(*wl), False, self.cfg.terminal)):
                setattr(v, attr, g["gain"] / v.gain if v.gain else 0.0)

    def one(self, hh: Household, moves: list) -> Verdict:
        return self.evaluate([(hh, moves)])[0]
