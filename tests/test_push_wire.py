"""
`wire_question`: what `mdq` parses versus what the server's question union
accepts.
"""

from __future__ import annotations

import mdq

from codehood.push.wire import wire_question


def wire(source: str) -> dict:
    return wire_question(mdq.parse(source, kind="question", ids="fill"))


def test_omitted_fields_are_left_out() -> None:
    payload = wire("What is 2 + 2?\n\n* [ ] 3\n* [*] 4\n")
    assert "title" not in payload
    assert all(value is not None for value in payload.values())


def test_spec_fields_are_kept() -> None:
    payload = wire(
        "---\ndiacritics: keep\nunmatched: manual\n---\n\n"
        "Name a biome.\n\n[short-answer]:\n* Cerrado\n"
    )
    assert payload["diacritics"] == "keep"
    assert payload["unmatched"] == "manual"
    assert payload["accept"] == [{"pattern": "Cerrado"}]


def test_fill_in_short_answer_blank_keeps_its_patterns() -> None:
    payload = wire(
        "Brazil's capital is [^capital] and it has [^size] people.\n\n"
        "[^capital/short-answer]:\n* Brasília\n* Brasilia\n\n"
        "[^size/numeric]: 2750000 +- 10%\n"
    )
    capital, size = payload["blanks"]
    assert capital["type"] == "short-answer"
    assert [entry["pattern"] for entry in capital["accept"]] == [
        "Brasília",
        "Brasilia",
    ]
    assert size["type"] == "numeric"


def test_choices_carry_ids() -> None:
    payload = wire("What is 2 + 2?\n\n* [ ] 3\n* [*] 4\n")
    assert all(choice.get("id") for choice in payload["choices"])
