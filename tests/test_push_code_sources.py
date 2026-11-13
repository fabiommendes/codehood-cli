"""
Tests for the test sources of a `code` question: a linked source is read from
disk and resolved before the question is pushed. See
`dev/specs/to-do/fila-de-correcao-externa.md`, R27.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import httpx
import mdq
import pytest
from mdq.models import CodeQuestion
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.cli.base import app
from codehood.push.errors import QuestionSourceError
from codehood.push.question import (
    InvalidQuestion,
    QuestionFile,
    question_version,
    resolve_exam_sources,
    scan_questions,
)
from codehood.push.unconsumed import consumed_paths
from codehood.push.wire import question_payload
from codehood.repo.file_tracker import scan_files

push_module = importlib.import_module("codehood.cli.push")

TESTS_ELM = """module Tests exposing (suite)

-- mdq: [+3] {example} Adds correctly
suite = test "adds" (\\_ -> 1 + 1 |> Expect.equal 2)
"""

LINKED = """---
id: soma
---

Write `add`.

[code]

## [tests]

[testes](Tests.elm)
"""

FENCED = """---
id: soma-cercada
---

Write `add`.

[code]

## [tests]

```elm
suite = test "adds" (\\_ -> 1 + 1 |> Expect.equal 2)
```
"""

MISSING = LINKED.replace("soma", "falta").replace("Tests.elm", "Nope.elm")

EXAM = """# [midterm] Midterm

Read carefully.

---
id: soma
---

Write `add`.

[code]

## [tests]

[testes](Tests.elm)
"""


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _scan(root: Path) -> list[QuestionFile | InvalidQuestion]:
    return list(scan_questions(root))


def test_a_linked_source_is_resolved_from_the_file_next_to_the_question(tmp_path):
    _write(tmp_path, "questions/Tests.elm", TESTS_ELM)
    _write(tmp_path, "questions/soma.md", LINKED)

    (found,) = _scan(tmp_path)

    assert isinstance(found, QuestionFile)
    (source,) = found.question.tests
    assert source.text == TESTS_ELM
    assert source.origin == "Tests.elm"
    sent = question_payload(found)["question"]
    assert sent["tests"][0]["text"] == TESTS_ELM


def test_the_link_is_relative_to_the_question_file_in_a_subdirectory(tmp_path):
    _write(tmp_path, "questions/elm/Tests.elm", TESTS_ELM)
    _write(tmp_path, "questions/elm/soma.md", LINKED)

    (found,) = _scan(tmp_path)

    assert isinstance(found, QuestionFile)
    assert found.question.tests[0].text == TESTS_ELM


def test_a_fenced_source_is_sent_as_it_is(tmp_path):
    _write(tmp_path, "questions/soma.md", FENCED)

    (found,) = _scan(tmp_path)

    assert isinstance(found, QuestionFile)
    (source,) = found.question.tests
    assert source.origin is None
    assert source.text is not None
    assert found.sources == ()


def test_a_missing_test_file_is_an_error_naming_it(tmp_path):
    _write(tmp_path, "questions/falta.md", MISSING)

    with pytest.raises(QuestionSourceError, match="Nope.elm"):
        _scan(tmp_path)


def test_an_unreadable_test_file_is_an_error(tmp_path):
    (tmp_path / "questions").mkdir()
    (tmp_path / "questions" / "Tests.elm").write_bytes(b"\xff\xfe\x00bad")
    _write(tmp_path, "questions/soma.md", LINKED)

    with pytest.raises(QuestionSourceError, match="Tests.elm"):
        _scan(tmp_path)


def test_a_test_file_that_breaks_the_annotation_rules_fails_the_question_alone(
    tmp_path,
):
    _write(tmp_path, "questions/Tests.elm", "-- mdq: [+1] {manual} Not allowed here\n")
    _write(tmp_path, "questions/soma.md", LINKED)

    (found,) = _scan(tmp_path)

    assert isinstance(found, InvalidQuestion)
    assert "Tests.elm" in found.reason or "invalid-rubric-item" in found.reason


def test_the_linked_files_are_recorded_so_the_push_does_not_report_them(tmp_path):
    _write(tmp_path, "questions/Tests.elm", TESTS_ELM)
    _write(tmp_path, "questions/soma.md", LINKED)

    (found,) = _scan(tmp_path)

    assert isinstance(found, QuestionFile)
    assert found.sources == (tmp_path / "questions" / "Tests.elm",)
    tracked = tuple(scan_files(tmp_path, []))
    consumed = consumed_paths(
        tracked, sources=[tmp_path / "questions" / "Tests.elm"], root=tmp_path
    )
    assert "questions/Tests.elm" in consumed
    assert "questions/Tests.elm" not in consumed_paths(tracked)


def test_an_inline_question_of_an_exam_links_relative_to_the_exam_file(tmp_path):
    _write(tmp_path, "exams/published/Tests.elm", TESTS_ELM)
    exam = mdq.parse(EXAM, kind="exam")

    resolved = resolve_exam_sources(exam, tmp_path / "exams" / "published")

    (entry,) = [e for e in resolved.questions if isinstance(e, CodeQuestion)]
    assert entry.tests[0].text == TESTS_ELM


def test_an_exam_with_a_missing_test_file_is_an_error(tmp_path):
    exam = mdq.parse(EXAM, kind="exam")

    with pytest.raises(QuestionSourceError, match="Tests.elm"):
        resolve_exam_sources(exam, tmp_path)


#
# `ch push`
#
@pytest.fixture(autouse=True)
def token(monkeypatch, tmp_path_factory):
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)
    base_module.save_token("http://localhost:4321", "test-token")


def _course(tmp_path: Path) -> Path:
    toml = (
        '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
        '\n[server]\nurl = "http://localhost:4321"\n'
    )
    _write(tmp_path, "codehood.toml", toml)
    _write(tmp_path, "README.md", "# CS101\n\nA description.\n")
    _write(
        tmp_path,
        "calendar.md",
        "---\nstart: 2026-01-01\nend: 2026-06-01\ndays:\n  - Mon 14:00 2h, Lecture\n"
        "holidays: []\n---\n\n# Schedule\n\n## Overview\n\nText.\n",
    )
    return tmp_path


def test_push_with_a_missing_test_file_fails_before_any_request(tmp_path, monkeypatch):
    calls: list[str] = []

    def get_client(base_url=None):
        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            raise AssertionError("the push reached the server")

        return httpx.Client(
            base_url=base_url or "http://localhost:4321",
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(push_module, "get_client", get_client)
    course = _course(tmp_path)
    _write(course, "questions/falta.md", MISSING)

    result = CliRunner().invoke(app, ["push", str(course), "--dry-run"])

    assert result.exit_code == 1
    assert "Nope.elm" in result.output
    assert calls == []


def test_push_does_not_report_a_linked_test_file_as_not_pushed(tmp_path, monkeypatch):

    def get_client(base_url=None):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and request.url.path.endswith(
                ("/resource", "/grade-column", "/question")
            ):
                return httpx.Response(200, json=[])
            return httpx.Response(404, json={"message": "not found"})

        return httpx.Client(
            base_url=base_url or "http://localhost:4321",
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(push_module, "get_client", get_client)
    course = _course(tmp_path)
    _write(course, "questions/Tests.elm", TESTS_ELM)
    _write(course, "questions/soma.md", LINKED)

    result = CliRunner().invoke(app, ["push", str(course), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "soma" in result.output
    assert "Tests.elm" not in result.output


def test_editing_only_a_linked_test_file_changes_the_version(tmp_path):
    tests = _write(tmp_path, "questions/Tests.elm", TESTS_ELM)
    _write(tmp_path, "questions/soma.md", LINKED)
    (before,) = _scan(tmp_path)

    tests.write_text(TESTS_ELM + "-- another case\n", encoding="utf-8")
    (after,) = _scan(tmp_path)

    assert isinstance(before, QuestionFile) and isinstance(after, QuestionFile)
    assert before.version != after.version


def test_a_question_without_linked_sources_keeps_the_digest_of_its_file(tmp_path):
    path = _write(tmp_path, "questions/soma-cercada.md", FENCED)

    (found,) = _scan(tmp_path)

    assert isinstance(found, QuestionFile)
    assert found.version == question_version(path.read_bytes())
