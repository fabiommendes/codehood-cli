"""
Tests for `codehood.push.question`: the pure core that turns `questions/`
into `QuestionFile`s. See `dev/specs/to-do/push-questions.md`, "A
question's slug is its flattened path under `questions/`", "The hash rides
in `version`, not `contentHash`", and "Parsing happens in the core, `mdq`
is the parser".
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import mdq
import pytest

from codehood.push.errors import SlugCollisionError
from codehood.push.question import (
    InvalidQuestion,
    QuestionFile,
    question_version,
    scan_questions,
)
from codehood.push.resource import slugify

EXAMPLE_MDQ = """---
title: Example question
---

What is 2 + 2?

- [ ] 3
- [*] 4
- [ ] 5
"""

FACTORIAL_MDQ = """---
title: Factorial question
---

What is the factorial of 5?

- [ ] 24
- [ ] 50
- [*] 120
"""

MALFORMED_MDQ = "this is not a valid MDQ file at all, no stem, no choices\n"


#
# question_version
#
def test_question_version_is_md5_of_the_bytes_prefixed():
    raw = EXAMPLE_MDQ.encode("utf-8")
    expected = f"md5:{hashlib.md5(raw).hexdigest()}"
    assert question_version(raw) == expected


def test_question_version_is_stable_across_calls():
    raw = EXAMPLE_MDQ.encode("utf-8")
    assert question_version(raw) == question_version(raw)


def test_question_version_differs_for_different_bytes():
    assert question_version(b"one") != question_version(b"two")


def test_question_version_changes_on_whitespace_only_edit():
    """
    "A question hashes the file... a whitespace-only edit re-pushes" --
    the design decision's stated trade, unlike a resource's `ref`, which
    digests parsed fields.
    """
    original = EXAMPLE_MDQ.encode("utf-8")
    whitespace_only = (EXAMPLE_MDQ + "\n").encode("utf-8")
    assert question_version(original) != question_version(whitespace_only)


#
# scan_questions: happy path
#
def test_scan_questions_yields_one_question_file_per_mdq_file(tmp_path: Path):
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "example.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    (questions / "fat.md").write_text(FACTORIAL_MDQ, encoding="utf-8")

    files = {f.slug: f for f in scan_questions(tmp_path)}
    assert set(files) == {"example", "fat"}
    for slug, qfile in files.items():
        assert isinstance(qfile, QuestionFile)
        assert qfile.slug == slug
        assert qfile.path == questions / f"{slug}.md"


def test_scan_questions_recurses_into_subdirectories(tmp_path: Path):
    questions = tmp_path / "questions" / "week1"
    questions.mkdir(parents=True)
    (questions / "big-o.md").write_text(EXAMPLE_MDQ, encoding="utf-8")

    [qfile] = list(scan_questions(tmp_path))
    assert qfile.slug == "week1-big-o"


def test_scan_questions_slug_matches_resource_slugify(tmp_path: Path):
    """
    The flattening rule is the one `resources/` already uses, not a
    reimplementation -- see the spec's "the flattening rule is therefore
    the one push.resource.slugify already uses".
    """
    questions = tmp_path / "questions" / "week1"
    questions.mkdir(parents=True)
    (questions / "Big O (intro).md").write_text(EXAMPLE_MDQ, encoding="utf-8")

    [qfile] = list(scan_questions(tmp_path))
    assert qfile.slug == slugify(Path("week1/Big O (intro).md"))


def test_scan_questions_no_questions_directory_yields_nothing(tmp_path: Path):
    assert list(scan_questions(tmp_path)) == []


def test_scan_questions_version_matches_question_version_of_the_file(
    tmp_path: Path,
):
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "example.md").write_text(EXAMPLE_MDQ, encoding="utf-8")

    [qfile] = list(scan_questions(tmp_path))
    assert qfile.version == question_version(EXAMPLE_MDQ.encode("utf-8"))


def test_scan_questions_question_is_the_parsed_mdq_question(tmp_path: Path):
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "example.md").write_text(EXAMPLE_MDQ, encoding="utf-8")

    [qfile] = list(scan_questions(tmp_path))
    assert qfile.question.stem == "What is 2 + 2?"
    assert qfile.question.type == "multiple-choice"


#
# scan_questions: slug collisions -- eager, before any parse.
#
def test_scan_questions_raises_slug_collision_error(tmp_path: Path):
    questions = tmp_path / "questions"
    (questions / "week1").mkdir(parents=True)
    (questions / "week1" / "big-o.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    (questions / "week1-big-o.md").write_text(FACTORIAL_MDQ, encoding="utf-8")

    with pytest.raises(SlugCollisionError):
        list(scan_questions(tmp_path))


def test_scan_questions_collision_is_raised_before_any_file_is_parsed(
    tmp_path: Path,
):
    """
    "Collisions refuse the whole push, before any file is read or any
    request is sent." One of the two colliding files is unparseable MDQ;
    the collision must still win, not a `QuestionParseError`.
    """
    questions = tmp_path / "questions"
    (questions / "week1").mkdir(parents=True)
    (questions / "week1" / "big-o.md").write_text(MALFORMED_MDQ, encoding="utf-8")
    (questions / "week1-big-o.md").write_text(FACTORIAL_MDQ, encoding="utf-8")

    with pytest.raises(SlugCollisionError):
        list(scan_questions(tmp_path))


def test_scan_questions_collision_error_names_every_contested_file(tmp_path: Path):
    questions = tmp_path / "questions"
    (questions / "week1").mkdir(parents=True)
    (questions / "week1" / "big-o.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    (questions / "week1-big-o.md").write_text(FACTORIAL_MDQ, encoding="utf-8")

    with pytest.raises(SlugCollisionError) as excinfo:
        list(scan_questions(tmp_path))
    detail = str(excinfo.value)
    assert "week1-big-o" in detail
    assert "week1-big-o.md" in detail
    assert str(Path("week1") / "big-o.md") in detail


def test_scan_questions_no_collision_across_unrelated_slugs(tmp_path: Path):
    """Two files with distinct slugs never collide, MDQ or not."""
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "example.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    (questions / "fat.md").write_text(FACTORIAL_MDQ, encoding="utf-8")

    files = list(scan_questions(tmp_path))
    assert len(files) == 2


#
# scan_questions: malformed MDQ.
#
def test_scan_questions_reports_malformed_mdq_as_invalid(tmp_path: Path):
    questions = tmp_path / "questions"
    questions.mkdir()
    bad_path = questions / "broken.md"
    bad_path.write_text(MALFORMED_MDQ, encoding="utf-8")

    [invalid] = list(scan_questions(tmp_path))
    assert isinstance(invalid, InvalidQuestion)
    assert invalid.slug == "broken"
    assert invalid.path == bad_path
    assert invalid.reason


def test_scan_questions_invalid_file_does_not_stop_the_others(tmp_path: Path):
    """
    One malformed file fails alone: the files before and after it still
    parse.
    """
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "aaa-good.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    (questions / "mmm-bad.md").write_text(MALFORMED_MDQ, encoding="utf-8")
    (questions / "zzz-good.md").write_text(FACTORIAL_MDQ, encoding="utf-8")

    found = {q.slug: type(q).__name__ for q in scan_questions(tmp_path)}
    assert found == {
        "aaa-good": "QuestionFile",
        "mmm-bad": "InvalidQuestion",
        "zzz-good": "QuestionFile",
    }


#
# `id` in the front matter
#
def test_scan_questions_id_in_front_matter_is_the_slug(tmp_path: Path):
    questions = tmp_path / "questions" / "classes"
    questions.mkdir(parents=True)
    (questions / "herança.md").write_text(
        EXAMPLE_MDQ.replace("---\n", "---\nid: heranca-entre-inimigos\n", 1),
        encoding="utf-8",
    )
    (questions / "self.md").write_text(FACTORIAL_MDQ, encoding="utf-8")
    slugs = sorted(q.slug for q in scan_questions(tmp_path))
    assert slugs == ["classes-self", "heranca-entre-inimigos"]


def test_scan_questions_id_colliding_with_a_path_slug_is_refused_before_parsing(
    tmp_path: Path,
):
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "a.md").write_text(
        EXAMPLE_MDQ.replace("---\n", "---\nid: b\n", 1), encoding="utf-8"
    )
    (questions / "b.md").write_text(MALFORMED_MDQ, encoding="utf-8")
    with pytest.raises(SlugCollisionError):
        list(scan_questions(tmp_path))


def test_scan_questions_underscore_marks_a_draft_and_leaves_the_slug(tmp_path: Path):
    questions = tmp_path / "questions"
    (questions / "_rascunhos").mkdir(parents=True)
    (questions / "_laco.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    (questions / "_rascunhos" / "fatorial.md").write_text(
        FACTORIAL_MDQ, encoding="utf-8"
    )
    (questions / "pronta.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    found = {q.slug: q.status for q in scan_questions(tmp_path)}
    assert found == {
        "laco": "DRAFT",
        "rascunhos-fatorial": "DRAFT",
        "pronta": "PUBLISHED",
    }


def test_scan_questions_draft_and_published_copies_of_one_slug_collide(
    tmp_path: Path,
):
    questions = tmp_path / "questions"
    questions.mkdir()
    (questions / "_laco.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    (questions / "laco.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    with pytest.raises(SlugCollisionError):
        list(scan_questions(tmp_path))
