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
