"""LLM proposer for the search loop (experiment plan §1.3, E2.3).

The agent sees: a rule description (current law, or a planted variant's
plain or disguised description), the household as JSON, the move
vocabulary, and the verifier feedback on its earlier proposals. It returns
move sequences as JSON, plus any "wanted" moves the vocabulary cannot
express (logged in every experiment).

Requires the optional `anthropic` package and credentials (ANTHROPIC_API_KEY
or an `ant auth login` profile). Other providers plug in by subclassing
LLMProposer and overriding `_complete`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from .household import Household

VOCABULARY = """\
Moves (JSON objects; "op" names the move). People and tax units are referred to by id.
- {"op": "set_filing_status", "tax_unit": U, "status": "SINGLE"|"JOINT"|"SEPARATE"|"HEAD_OF_HOUSEHOLD"}
    SEPARATE splits a married unit (the spouse gets unit U + "_s"); JOINT merges a married couple.
- {"op": "gift_asset", "giver": P, "recipient": Q, "asset": A, "fraction": f}   (0 < f <= 1, basis carries over)
- {"op": "shift_income", "payer": P, "payee": Q, "amount": x}   (P's business pays Q wages; x <= P's self-employment income)
- {"op": "realize_gain", "person": P, "asset": A, "fraction": f}   (sell and buy back; losses are wash sales and have no effect)
- {"op": "assign_dependent", "dependent": D, "tax_unit": U}   (move a dependent to another tax unit of the household)
- {"op": "set_hours", "person": P, "hours": h}   (wages scale with hours; changes economic reality)
- {"op": "itemize_or_standard", "tax_unit": U, "itemize": true|false}
- {"op": "contribute_retirement", "person": P, "account": "401k"|"ira", "amount": x}   (pre-tax, within statutory limits)
"""

SYSTEM = """\
You are a tax-law red-teaming agent in a research study of US household tax law. You search for \
arrangements of a synthetic household that raise its after-tax resources (benefits minus taxes) \
without changing its economic reality (pre-tax income, hours worked, total wealth), and that are not \
explained by intended incentives used as designed. A verifier evaluates every proposal with two \
independent tax calculators and reports the gain and which checks passed. Households are synthetic; \
findings are used to study and close gaps in the law.

Reply with one JSON object and nothing else:
{"proposals": [{"moves": [<move>, ...], "rationale": "<one sentence>"}, ...],
 "wanted_moves": ["<a move you wanted that the vocabulary cannot express>", ...]}
"""


def _feedback(history, limit: int = 30) -> str:
    if not history:
        return "No proposals evaluated yet."
    best = sorted(history, key=lambda r: -r.verdict.gain)[: limit // 2]
    recent = history[-(limit // 2) :]
    seen, lines = set(), []
    for r in best + recent:
        key = json.dumps(r.moves, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        v = r.verdict
        lines.append(
            json.dumps(
                {
                    "moves": r.moves,
                    "label": v.label,
                    "gain": round(v.gain),
                    "crosscheck_pass": v.crosscheck_pass,
                    "reality_unchanged": v.reality_unchanged,
                    "explained_by_intended": v.label == "intended_concession",
                    "error": v.error,
                }
            )
        )
    return "\n".join(lines)


def _household_json(hh: Household) -> str:
    d = hh.to_dict()
    return json.dumps(d, sort_keys=True)


def parse_reply(text: str) -> tuple[list[list[dict]], list[str]]:
    """Proposals and wanted moves from the model's reply; tolerant of text
    around the JSON object."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return [], []
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return [], []
    props = []
    for p in obj.get("proposals", []) or []:
        moves = p.get("moves") if isinstance(p, dict) else None
        if isinstance(moves, list) and all(isinstance(x, dict) and "op" in x for x in moves) and moves:
            props.append(moves)
    wanted = [str(w) for w in obj.get("wanted_moves", []) or []]
    return props, wanted


@dataclass
class LLMProposer:
    rules: str  # the rule description the agent sees
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    max_tokens: int = 16000
    wanted: list = field(default_factory=list)
    usage: list = field(default_factory=list)
    refusals: int = 0
    _client: Optional[object] = None

    def _complete(self, user: str) -> str:
        import anthropic

        if self._client is None:
            self._client = anthropic.Anthropic()
        resp = self._client.beta.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": SYSTEM + "\n" + VOCABULARY, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": self.effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": user}],
        )
        self.usage.append({"input": resp.usage.input_tokens, "output": resp.usage.output_tokens, "model": resp.model})
        if resp.stop_reason == "refusal":
            self.refusals += 1
            return ""
        return "".join(b.text for b in resp.content if b.type == "text")

    def propose(self, hh: Household, history, k: int, rng) -> list[list[dict]]:
        user = (
            f"Rules in force:\n{self.rules}\n\nHousehold (tax year {hh.year}):\n{_household_json(hh)}\n\n"
            f"Verifier feedback on earlier proposals:\n{_feedback(history)}\n\n"
            f"Propose {k} new, distinct move sequences (at most 4 moves each)."
        )
        props, wanted = parse_reply(self._complete(user))
        self.wanted += wanted
        return props[:k]
