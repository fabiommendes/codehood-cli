"""
Tests for the gitignore-like patterns of `[push] exclude` in `codehood.toml`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from codehood.models.repo import PushConfig, RepoConfig
from codehood.globs import is_excluded

MATCHES = [
    ("questions/a.mdq", "questions/a.mdq"),
    ("questions/*.mdq", "questions/a.mdq"),
    ("questions/a?.mdq", "questions/ab.mdq"),
    ("questions/wip", "questions/wip/a.mdq"),
    ("questions/wip/", "questions/wip/deep/a.mdq"),
    ("questions/**", "questions/wip/deep/a.mdq"),
    ("questions/**/a.mdq", "questions/a.mdq"),
    ("questions/**/a.mdq", "questions/x/y/a.mdq"),
    ("**/a.mdq", "questions/x/a.mdq"),
    ("/questions/a.mdq", "questions/a.mdq"),
]

MISSES = [
    ("questions/*.mdq", "questions/wip/a.mdq"),
    ("questions/a.mdq", "questions/a.mdq.bak"),
    ("questions/wip", "questions/wipe/a.mdq"),
    ("questions/wip", "other/questions/wip/a.mdq"),
    ("questions/a?.mdq", "questions/a.mdq"),
    ("a.mdq", "questions/a.mdq"),
]


@pytest.mark.parametrize("pattern,path", MATCHES)
def test_pattern_matches(pattern: str, path: str) -> None:
    assert is_excluded(path, [pattern])


@pytest.mark.parametrize("pattern,path", MISSES)
def test_pattern_does_not_match(pattern: str, path: str) -> None:
    assert not is_excluded(path, [pattern])


def test_no_patterns_exclude_nothing() -> None:
    assert not is_excluded("questions/a.mdq", [])


def test_any_pattern_is_enough() -> None:
    assert is_excluded("questions/a.mdq", ["nope", "questions/*.mdq"])


@pytest.mark.parametrize("pattern", ["", "  ", "!questions/a.mdq", "../x", "a/../b"])
def test_invalid_patterns_are_rejected_by_the_config(pattern: str) -> None:
    with pytest.raises(ValidationError):
        PushConfig(exclude=[pattern])


def test_push_table_is_optional(tmp_path) -> None:
    (tmp_path / "codehood.toml").write_text(
        '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
        '[server]\nurl = "https://codehood.example.edu"\n'
    )
    assert RepoConfig.open(tmp_path).push.exclude == []


def test_unknown_push_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PushConfig.model_validate({"exlude": ["x"]})
