"""Parsing of LLM proposer replies (no API calls)."""

from taxred.llm import parse_reply


def test_parse_reply_tolerates_text_and_drops_bad_moves():
    text = 'Here you go:\n{"proposals": [{"moves": [{"op": "gift_asset", "giver": "p"}], "rationale": "x"}, {"moves": []}, {"moves": "bad"}], "wanted_moves": ["trust"]}\nthanks'
    props, wanted = parse_reply(text)
    assert props == [[{"op": "gift_asset", "giver": "p"}]]
    assert wanted == ["trust"]


def test_parse_reply_garbage():
    assert parse_reply("no json") == ([], [])
    assert parse_reply("{not json}") == ([], [])


def test_llm_pool_proposer_offline():
    # The pool path end to end with a canned reply and a stub verifier.
    import json

    from taxred.generate import archetypes
    from taxred.llm import LLMPoolProposer, household_summary
    from taxred.search import search_pool
    from taxred.verifier import Verdict

    pool = archetypes()
    target = next(h for h in pool if h.id == "high_earner_with_kids_assets")

    class Canned(LLMPoolProposer):
        def _complete(self, user):
            assert "high_earner_with_kids_assets" in user
            return json.dumps({"proposals": [
                {"household": target.id, "moves": [{"op": "gift_asset", "giver": "a", "recipient": "k1", "asset": "bond"}]},
                {"household": "no_such_household", "moves": [{"op": "itemize_or_standard", "tax_unit": "t", "itemize": True}]},
            ], "wanted_moves": ["create a trust"]})

    class Stub:
        def evaluate_many(self, props):
            return [Verdict("candidate", gain=100.0) for _ in props]

    p = Canned(rules="test")
    hist = search_pool(pool, Stub(), p, budget=5, batch=5)
    assert [r.household_id for r in hist] == [target.id]
    assert p.wanted[0] == "create a trust"
    assert household_summary(target)["people"]["a"]["wages"] == 350_000
