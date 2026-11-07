"""Rediscovery matching rule (experiment plan §1.1), closure-test half.

A candidate found under `law_pre` matches known loophole L if applying L's
closure (`law_post`) removes at least `min_reduction` of its gain. The
attribution-signature half is applied by comparing Verdict.signature with
the loophole's witness signature (see `signature_jaccard`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .household import Household
from .law import Law
from .verifier import Verifier, VerifierConfig


@dataclass
class ClosureTest:
    gain_pre: float
    gain_post: float
    reduction: float  # share of the pre-closure gain removed by the closure
    matched: bool


def closure_tests(
    proposals: Sequence[tuple[Household, list]],
    law_pre: Law,
    law_post: Law,
    min_reduction: float = 0.8,
    config: VerifierConfig | None = None,
) -> list[ClosureTest]:
    cfg = config or VerifierConfig(run_attribution=False)
    pre = Verifier(law_pre, cfg).evaluate_many(proposals)
    post = Verifier(law_post, cfg).evaluate_many(proposals)
    out = []
    for a, b in zip(pre, post):
        if a.label == "invalid" or a.gain <= 0:
            out.append(ClosureTest(a.gain, b.gain, 0.0, False))
            continue
        red = (a.gain - b.gain) / a.gain
        out.append(ClosureTest(a.gain, b.gain, red, red >= min_reduction))
    return out


def signature_jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)
