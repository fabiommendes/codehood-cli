"""
Tests for `codehood.push.exam`, the pure core of `exams/`: slug, type, status,
the payload pieces, the include ladder, and inline questions.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from codehood.push.errors import QuestionSourceError, SlugCollisionError
from codehood.push.exam import (
    ExamFile,
    InvalidExam,
    exam_duration,
    exam_rev,
    exam_scheduled_at,
    exam_slug,
    exam_status,
    exam_type,
    inline_questions,
    scan_exams,
)
from codehood.push.exclude import scan_excluded
from codehood.push.question import QuestionFile, scan_questions
from codehood.push.resource import slugify_text
from codehood.push.wire import exam_payload

QUESTION = """---
title: {title}
tags: [{tags}]
---

What is {title}?

- [ ] 3
- [*] 4
- [ ] 5
"""

ESSAY = """---
id: {id}
---

Explain {id}.

[essay]
"""

EXAM = """---
start: 2026-03-15T14:00:00
duration: 2h
---

# [midterm] Midterm Exam

Answer every question.

{entries}
"""

#
# Helpers
#


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def question(root: Path, relative: str, title: str, tags: str = "") -> None:
    write(root, relative, QUESTION.format(title=title, tags=tags))


def scan(root: Path, exclude: tuple[str, ...] = ()) -> list[ExamFile | InvalidExam]:
    questions = list(scan_questions(root, exclude))
    return list(scan_exams(root, questions, list(scan_excluded(root, exclude))))


def only_exam(root: Path) -> ExamFile:
    (exam,) = scan(root)
    assert isinstance(exam, ExamFile), exam
    return exam


def only_invalid(root: Path) -> InvalidExam:
    (exam,) = scan(root)
    assert isinstance(exam, InvalidExam), exam
    return exam


def include(*targets: str) -> str:
    return "\n".join(f"---\ninclude: {target}\n---\n" for target in targets) + "\n"


#
# Slug
#
def test_the_slug_is_the_front_matter_id_then_the_h1_id_then_the_path(tmp_path):
    write(tmp_path, "exams/a.md", "---\nid: Front Id\n---\n\n# [h1] T\n")
    write(tmp_path, "exams/b.md", "# [h1-id] T\n")
    write(tmp_path, "exams/part1/exam.md", "# T\n")

    slugs = {e.slug for e in scan(tmp_path)}

    assert slugs == {"front-id", "h1-id", "part1-exam"}


def test_a_leading_underscore_is_left_out_of_every_component_of_the_path():
    assert exam_slug(None, Path("_drafts/_a.mdq.md")) == "drafts-a"
    assert exam_slug(None, Path("a_b/c.md")) == "a_b-c"


component = st.from_regex(r"[a-z][a-z0-9]{0,5}", fullmatch=True)


@given(parts=st.lists(component, min_size=1, max_size=4))
def test_marking_components_as_drafts_never_changes_the_slug(parts):
    path = Path(*parts[:-1], parts[-1] + ".md")
    marked = Path(*(f"_{p}" for p in parts[:-1]), f"_{parts[-1]}.md")

    assert exam_slug(None, marked) == exam_slug(None, path)
    assert slugify_text(exam_slug(None, path)) == exam_slug(None, path)


@given(parts=st.lists(component, min_size=1, max_size=4))
def test_the_suffix_never_changes_the_slug(parts):
    slugs = {
        exam_slug(None, Path(*parts[:-1], parts[-1] + suffix))
        for suffix in (".md", ".mdq", ".mdq.md")
    }

    assert len(slugs) == 1


#
# Type
#
def test_the_first_quiz_or_practice_word_in_path_order_sets_the_type():
    assert exam_type(Path("practice/midterm-quiz.md")) == "PRACTICE"
    assert exam_type(Path("quiz/practice.md")) == "QUIZ"
    assert exam_type(Path("week1/quiz.md")) == "QUIZ"
    assert exam_type(Path("midterm.md")) == "EXAM"


def test_a_word_is_a_whole_separated_token():
    assert exam_type(Path("quizzical.md")) == "EXAM"
    assert exam_type(Path("practical/exam.md")) == "EXAM"
    assert exam_type(Path("my_quiz.md")) == "QUIZ"
    assert exam_type(Path("week.1.practice.md")) == "PRACTICE"


word = st.sampled_from(["quiz", "practice", "exam", "midterm", "x1", "Quiz"])


@given(parts=st.lists(st.lists(word, min_size=1, max_size=3), min_size=1, max_size=3))
def test_the_type_is_the_first_matching_word_of_the_path(parts):
    path = Path(*("-".join(words) for words in parts))
    flat = [w.lower() for words in parts for w in words]
    expected = next(
        (
            {"quiz": "QUIZ", "practice": "PRACTICE"}[w]
            for w in flat
            if w in {"quiz", "practice"}
        ),
        "EXAM",
    )

    assert exam_type(path) == expected


#
# Status
#
def test_status_follows_the_start_and_the_draft_mark():
    assert exam_status(Path("a.md"), scheduled=True) == "SCHEDULED"
    assert exam_status(Path("a.md"), scheduled=False) == "DRAFT"
    assert exam_status(Path("_a.md"), scheduled=True) == "DRAFT"
    assert exam_status(Path("_d/a.md"), scheduled=True) == "DRAFT"
    assert exam_status(Path("a_b.md"), scheduled=True) == "SCHEDULED"


#
# Payload pieces
#
def test_a_duration_is_a_plain_total_with_no_day_wrap():
    assert exam_duration(timedelta(hours=2)) == {"hours": 2, "minutes": 0}
    assert exam_duration(timedelta(days=2)) == {"hours": 48, "minutes": 0}
    assert exam_duration(timedelta(minutes=90)) == {"hours": 1, "minutes": 30}


@given(minutes=st.integers(min_value=0, max_value=10_000))
def test_a_duration_carries_every_minute(minutes):
    wire = exam_duration(timedelta(minutes=minutes))

    assert wire["hours"] * 60 + wire["minutes"] == minutes
    assert 0 <= wire["minutes"] < 60


def test_a_start_is_utc_and_a_bare_date_is_midnight():
    assert exam_scheduled_at(date(2026, 3, 15)) == "2026-03-15T00:00:00.000Z"
    assert exam_scheduled_at(datetime(2026, 3, 15, 14)) == "2026-03-15T14:00:00.000Z"
    zone = timezone(timedelta(hours=-3))
    assert (
        exam_scheduled_at(datetime(2026, 3, 15, 14, tzinfo=zone))
        == "2026-03-15T17:00:00.000Z"
    )
    assert exam_scheduled_at(datetime(2026, 3, 15, 14, tzinfo=UTC)).endswith("Z")


def test_the_rev_depends_on_the_payload_alone_and_not_on_its_key_order():
    assert exam_rev({"a": 1, "b": 2}) == exam_rev({"b": 2, "a": 1})
    assert exam_rev({"a": 1}) != exam_rev({"a": 2})
    assert exam_rev({"a": 1}).startswith("v1:")


#
# Fields
#
def test_an_exam_maps_its_fields(tmp_path):
    write(tmp_path, "exams/quiz/mid.md", EXAM.format(entries=ESSAY.format(id="one")))

    exam = only_exam(tmp_path)

    assert exam.slug == "midterm"
    assert exam.type == "QUIZ"
    assert exam.status == "SCHEDULED"
    assert exam.title == "Midterm Exam"
    assert exam.preamble == "Answer every question."
    assert exam.duration == {"hours": 2, "minutes": 0}
    assert exam.scheduled_at == "2026-03-15T14:00:00.000Z"
    assert exam.allow_code_run is None
    assert exam.questions == ("midterm-one",)
    payload = exam_payload(exam)
    assert payload["format"] == "MARKDOWN"
    assert payload["questions"] == [{"slug": "midterm-one", "version": None}]
    assert "status" not in payload
    assert "rev" not in payload


def test_an_exam_without_title_takes_the_title_of_its_filename(tmp_path):
    write(tmp_path, "exams/_final-exam.md", "# \n\nRead.\n")

    exam = only_exam(tmp_path)

    assert exam.title == "Final Exam"
    assert exam.slug == "final-exam"
    assert exam.status == "DRAFT"


def test_a_file_without_duration_or_start_leaves_them_out_of_the_payload(tmp_path):
    write(tmp_path, "exams/e.md", "# [e] E\n")

    payload = exam_payload(only_exam(tmp_path))

    assert "duration" not in payload
    assert "scheduledAt" not in payload
    assert payload["description"] is None
    assert payload["preamble"] is None
    assert payload["tags"] == []


def test_meta_code_run_is_a_boolean_or_an_error(tmp_path):
    write(tmp_path, "exams/ok.md", "---\nmeta:\n  codeRun: true\n---\n\n# [ok] Ok\n")
    write(
        tmp_path,
        "exams/bad.md",
        "---\nmeta:\n  codeRun: yes please\n---\n\n# [bad] B\n",
    )

    found = {e.slug: e for e in scan(tmp_path)}

    assert isinstance(found["ok"], ExamFile) and found["ok"].allow_code_run is True
    assert isinstance(found["bad"], InvalidExam)
    assert "codeRun" in found["bad"].reason


def test_fields_the_server_cannot_hold_are_listed_as_ignored(tmp_path):
    write(
        tmp_path,
        "exams/e.md",
        "---\npenalty: capped\nshuffle: true\n---\n\n# [e] E\n",
    )
    write(tmp_path, "exams/f.md", "# [f] F\n")

    found = {e.slug: e for e in scan(tmp_path)}

    assert isinstance(found["e"], ExamFile) and isinstance(found["f"], ExamFile)
    assert found["e"].ignored == ("penalty", "shuffle")
    assert found["f"].ignored == ()


def test_unreadable_or_broken_files_are_invalid_with_the_slug_that_names_them(tmp_path):
    write(tmp_path, "exams/broken.md", "---\nid: kept\nstart: not a date\n---\n\n# T\n")
    write(
        tmp_path, "exams/h1.md", "# [from-h1] T\n\n---\nid: x\ntype: nope\n---\n\nQ\n"
    )

    found = {e.slug: e for e in scan(tmp_path)}

    assert set(found) == {"kept", "from-h1"}
    assert all(isinstance(e, InvalidExam) for e in found.values())


def test_only_mdq_files_are_exams(tmp_path):
    write(tmp_path, "exams/a.md", "# [a] A\n")
    write(tmp_path, "exams/b.mdq", "# [b] B\n")
    write(tmp_path, "exams/c.mdq.md", "# [c] C\n")
    write(tmp_path, "exams/notes.txt", "not an exam")
    write(tmp_path, "exams/deep/er/d.md", "# [d] D\n")

    assert [e.slug for e in scan(tmp_path)] == ["a", "b", "c", "d"]


def test_a_repository_without_exams_has_none(tmp_path):
    assert scan(tmp_path) == []


#
# Includes
#
def test_include_by_exact_slug(tmp_path):
    question(tmp_path, "questions/algebra/limits.md", "Limits")
    write(tmp_path, "exams/e.md", EXAM.format(entries=include("algebra-limits")))

    assert only_exam(tmp_path).questions == ("algebra-limits",)


def test_include_by_unique_filename_stem(tmp_path):
    question(tmp_path, "questions/algebra/limits.md", "Limits")
    question(tmp_path, "questions/_draft/rough.md", "Rough")
    write(tmp_path, "exams/e.md", EXAM.format(entries=include("limits", "rough")))

    assert only_exam(tmp_path).questions == ("algebra-limits", "draft-rough")


def test_an_ambiguous_stem_matches_no_question(tmp_path):
    question(tmp_path, "questions/a/same.md", "A")
    question(tmp_path, "questions/b/same.md", "B")
    write(tmp_path, "exams/e.md", EXAM.format(entries=include("same")))

    assert "matches no question" in only_invalid(tmp_path).reason


def test_the_slug_wins_over_a_stem(tmp_path):
    question(tmp_path, "questions/a/b.md", "AB")
    write(
        tmp_path,
        "questions/b.md",
        ESSAY.format(id="a-b").replace("id: a-b", "id: other"),
    )
    write(tmp_path, "exams/e.md", EXAM.format(entries=include("a-b")))

    assert only_exam(tmp_path).questions == ("a-b",)


def test_include_by_a_path_relative_to_the_exam_then_to_questions_then_the_root(
    tmp_path,
):
    question(tmp_path, "questions/rec/one.md", "One")
    question(tmp_path, "questions/rec/two.md", "Two")
    question(tmp_path, "questions/rec/three.md", "Three")
    entries = include("../questions/rec/one.md", "rec/two.md", "questions/rec/three")
    write(tmp_path, "exams/part/e.md", EXAM.format(entries=entries))

    assert only_exam(tmp_path).questions == ("rec-one", "rec-two", "rec-three")


def test_an_unresolved_include_makes_the_exam_invalid(tmp_path):
    write(tmp_path, "exams/e.md", EXAM.format(entries=include("nope")))

    exam = only_invalid(tmp_path)

    assert exam.slug == "midterm"
    assert "include 'nope' matches no question" in exam.reason


def test_an_include_of_an_invalid_question_makes_the_exam_invalid(tmp_path):
    write(tmp_path, "questions/bad.md", "---\ntitle: x\n---\n\n[bogus]\n")
    write(tmp_path, "exams/e.md", EXAM.format(entries=include("bad")))

    assert "is invalid" in only_invalid(tmp_path).reason


def test_an_include_of_an_excluded_question_makes_the_exam_invalid(tmp_path):
    question(tmp_path, "questions/skip/q.md", "Q")
    write(tmp_path, "exams/e.md", EXAM.format(entries=include("skip-q")))

    exam = scan(tmp_path, exclude=("questions/skip/**",))[0]

    assert isinstance(exam, InvalidExam)
    assert "exclude" in exam.reason


def test_the_same_question_twice_makes_the_exam_invalid(tmp_path):
    question(tmp_path, "questions/q.md", "Q")
    write(tmp_path, "exams/e.md", EXAM.format(entries=include("q", "q.md")))

    assert "twice" in only_invalid(tmp_path).reason


def test_include_all_takes_every_match_sorted_and_skips_what_the_exam_holds(tmp_path):
    question(tmp_path, "questions/c.md", "C", tags="loops")
    question(tmp_path, "questions/a.md", "A", tags="loops")
    question(tmp_path, "questions/b.md", "B", tags="loops, hard")
    question(tmp_path, "questions/z.md", "Z", tags="other")
    entries = include("b") + "---\nincludeAll: loops AND NOT hard\n---\n"
    write(tmp_path, "exams/e.md", EXAM.format(entries=entries))

    assert only_exam(tmp_path).questions == ("b", "a", "c")


def test_include_all_skips_a_question_the_exam_includes_later(tmp_path):
    question(tmp_path, "questions/a.md", "A", tags="t")
    question(tmp_path, "questions/b.md", "B", tags="t")
    entries = "---\nincludeAll: t\n---\n\n" + include("a")
    write(tmp_path, "exams/e.md", EXAM.format(entries=entries))

    assert only_exam(tmp_path).questions == ("b", "a")


def test_include_all_with_a_max_is_an_error(tmp_path):
    question(tmp_path, "questions/a.md", "A", tags="t")
    write(
        tmp_path, "exams/e.md", EXAM.format(entries="---\nincludeAll: t\nmax: 1\n---\n")
    )

    assert "max" in only_invalid(tmp_path).reason


def test_include_all_that_matches_nothing_adds_nothing(tmp_path):
    write(
        tmp_path, "exams/e.md", EXAM.format(entries="---\nincludeAll: nothing\n---\n")
    )

    assert only_exam(tmp_path).questions == ()


#
# Inline questions
#
def test_inline_questions_are_slugged_by_id_or_by_position(tmp_path):
    question(tmp_path, "questions/q.md", "Q")
    entries = (
        include("q") + "\n" + ESSAY.format(id="alpha") + "\n===\n\nNo id.\n\n[essay]\n"
    )
    write(tmp_path, "exams/e.md", EXAM.format(entries=entries))

    exam = only_exam(tmp_path)

    assert exam.questions == ("q", "midterm-alpha", "midterm-q3")
    assert [q.slug for q in exam.inline] == ["midterm-alpha", "midterm-q3"]
    assert inline_questions([exam]) == exam.inline


def test_an_inline_question_is_a_question_file_of_the_exam_file(tmp_path):
    path = write(tmp_path, "exams/_d/e.md", EXAM.format(entries=ESSAY.format(id="a")))

    (inline,) = only_exam(tmp_path).inline

    assert isinstance(inline, QuestionFile)
    assert inline.path == path
    assert inline.status == "DRAFT"
    assert inline.version.startswith("md5:")


def test_editing_an_inline_question_changes_only_its_own_version(tmp_path):
    two = ESSAY.format(id="a") + "\n" + "---\nid: b\n---\n\nExplain b.\n\n[essay]\n"
    write(tmp_path, "exams/e.md", EXAM.format(entries=two))
    before = {q.slug: q.version for q in only_exam(tmp_path).inline}
    write(
        tmp_path, "exams/e.md", EXAM.format(entries=two.replace("Explain b", "Say b"))
    )
    after = {q.slug: q.version for q in only_exam(tmp_path).inline}

    assert before["midterm-a"] == after["midterm-a"]
    assert before["midterm-b"] != after["midterm-b"]


def test_an_inline_slug_that_collides_with_a_question_stops_the_scan(tmp_path):
    question(tmp_path, "questions/midterm-a.md", "A")
    write(tmp_path, "exams/e.md", EXAM.format(entries=ESSAY.format(id="a")))

    with pytest.raises(SlugCollisionError, match="midterm-a"):
        scan(tmp_path)


def test_two_exams_with_one_slug_stop_the_scan(tmp_path):
    write(tmp_path, "exams/a.md", "# [same] A\n")
    write(tmp_path, "exams/b.md", "# [same] B\n")

    with pytest.raises(SlugCollisionError, match="same"):
        scan(tmp_path)


CODE = """---
id: soma
---

Write `add`.

[code]

## [tests]

[testes](Tests.elm)
"""


def test_an_inline_code_question_reads_its_tests_next_to_the_exam(tmp_path):
    write(tmp_path, "exams/Tests.elm", "suite = 1\n")
    write(tmp_path, "exams/e.md", EXAM.format(entries=CODE))
    before = only_exam(tmp_path).inline[0]
    write(tmp_path, "exams/Tests.elm", "suite = 2\n")
    after = only_exam(tmp_path).inline[0]

    assert before.sources == (tmp_path / "exams" / "Tests.elm",)
    assert before.version != after.version


def test_an_inline_code_question_with_a_missing_test_file_stops_the_scan(tmp_path):
    write(tmp_path, "exams/e.md", EXAM.format(entries=CODE))

    with pytest.raises(QuestionSourceError, match="Tests.elm"):
        scan(tmp_path)


def test_a_duration_under_a_minute_makes_the_exam_invalid(tmp_path):
    write(tmp_path, "exams/e.md", "---\nduration: PT30S\n---\n\n# [e] E\n")

    exam = only_invalid(tmp_path)

    assert "duration" in exam.reason


def test_the_tags_of_the_payload_are_sorted(tmp_path):
    write(tmp_path, "exams/e.md", "---\ntags: [b, a]\n---\n\n# [e] E\n")

    assert exam_payload(only_exam(tmp_path))["tags"] == ["a", "b"]
