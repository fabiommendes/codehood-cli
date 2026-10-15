"""
`wire_question`: what `mdq` parses versus what the server's question union
accepts.
"""

from __future__ import annotations

import mdq

from codehood.push.wire import wire_question


def wire(source: str) -> dict:
    return wire_question(mdq.parse(source, kind="question", ids="fill"))


def test_inherited_shuffle_is_omitted() -> None:
    payload = wire("What is 2 + 2?\n\n* [ ] 3\n* [*] 4\n")
    assert "shuffle" not in payload
    assert "grading" not in payload
    assert "weight" not in payload


def test_explicit_shuffle_is_kept() -> None:
    payload = wire("---\nshuffle: true\n---\n\nWhat is 2 + 2?\n\n* [ ] 3\n* [*] 4\n")
    assert payload["shuffle"] is True


def test_short_answer_drops_the_fields_the_server_does_not_know() -> None:
    payload = wire(
        "---\ndiacritics: keep\nunmatched: manual\n---\n\n"
        "Name a biome.\n\n[short-answer]:\n* Cerrado\n"
    )
    assert "diacritics" not in payload
    assert "unmatched" not in payload
    assert payload["accept"] == [{"pattern": "Cerrado"}]


def test_fill_in_short_answer_blank_becomes_one_of() -> None:
    payload = wire(
        "Brazil's capital is [^capital] and it has [^size] people.\n\n"
        "[^capital/short-answer]:\n* Brasília\n* Brasilia\n\n"
        "[^size/numeric]: 2750000 +- 10%\n"
    )
    capital, size = payload["blanks"]
    assert capital == {
        "id": "capital",
        "type": "short-answer",
        "oneOf": ["Brasília", "Brasilia"],
    }
    assert size["type"] == "numeric"
    assert "diacritics" not in payload
