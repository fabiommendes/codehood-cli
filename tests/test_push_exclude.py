"""
Tests for `codehood.push.exclude`: the slugs an `exclude` pattern protects.
"""

from __future__ import annotations

from pathlib import Path

from codehood.push.exclude import ExcludedFile, scan_excluded


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_an_excluded_question_protects_the_slug_its_id_declares(tmp_path: Path):
    _write(tmp_path, "questions/draft/herança.md", "---\nid: heranca\n---\nbroken\n")
    _write(tmp_path, "questions/draft/laços.md", "no front matter, not even mdq\n")
    excluded = sorted(scan_excluded(tmp_path, ["questions/draft/**"]), key=str)
    assert excluded == [
        ExcludedFile("question", "draft-lacos", "questions/draft/laços.md"),
        ExcludedFile("question", "heranca", "questions/draft/herança.md"),
    ]


def test_an_excluded_info_yaml_is_not_a_resource(tmp_path: Path):
    _write(tmp_path, "resources/w1/info.yaml", "a.png:\n  title: A\n")
    _write(tmp_path, "resources/w1/a.png", "png")
    excluded = list(scan_excluded(tmp_path, ["resources/w1/**"]))
    assert excluded == [ExcludedFile("resource", "w1-a.png", "resources/w1/a.png")]
