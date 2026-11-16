"""
Tests for `codehood exam release`, the Typer command in `codehood.cli.exam`:
it asks the server to release an exam's grades and explains a refusal.

HTTP is answered by an `httpx` mock transport injected by monkeypatching
`get_client` on the command module (see `test_cli_push.py` for why the module
is fetched with `importlib`).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.cli.base import app

exam_module = importlib.import_module("codehood.cli.exam")

runner = CliRunner()

SERVER = "http://localhost:4321"
RELEASE = "/api/course/cs101/ada_2026-1/exam/midterm/release"

TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    f'\n[server]\nurl = "{SERVER}"\n'
)

RELEASED_AT = "2026-11-16T13:00:00.000Z"

EXAM = {
    "slug": "midterm",
    "type": "EXAM",
    "status": "COMPLETED",
    "title": "Midterm",
    "description": None,
    "preamble": None,
    "format": "MARKDOWN",
    "scheduledAt": None,
    "duration": None,
    "extraTime": None,
    "allowCodeRun": None,
    "answerHistory": None,
    "gradesReleasedAt": RELEASED_AT,
    "author": "ada",
    "rev": None,
    "tags": [],
    "questions": [],
    "createdAt": "2026-10-01T00:00:00.000Z",
    "updatedAt": RELEASED_AT,
}


def refusal(reason: str, *, pending: int = 0, exceptions: int = 0) -> dict:
    message = f"refused: {reason}"
    return {
        "type": "error",
        "code": "invalid-data",
        "status": 409,
        "message": message,
        "timestamp": RELEASED_AT,
        "errors": {"exam": [{"code": "invalid", "message": message}]},
        "reason": reason,
        "pendingAnswers": pending,
        "openExceptions": exceptions,
    }


@pytest.fixture(autouse=True)
def credentials_path(tmp_path_factory, monkeypatch):
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)
    base_module.save_token(SERVER, "test-token")


@pytest.fixture
def repo(tmp_path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    (path / "codehood.toml").write_text(TOML, encoding="utf-8")
    return path


def serve(monkeypatch, status: int, body: dict) -> list[tuple[str, str]]:
    """
    Make the command talk to a server that answers the release with
    `status` and `body`, and return the log of requests it receives.
    """
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        return httpx.Response(status, json=body)

    def get_client(base_url=None):
        return httpx.Client(
            base_url=base_url or SERVER, transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(exam_module, "get_client", get_client)
    return calls


def release(repo: Path):
    return runner.invoke(app, ["exam", "release", "midterm", str(repo)])


def test_release_posts_to_the_course_exam_and_reports_the_date(repo, monkeypatch):
    calls = serve(monkeypatch, 200, EXAM)

    result = release(repo)

    assert result.exit_code == 0, result.output
    assert calls == [("POST", RELEASE)]
    assert f"released the grades of midterm at {RELEASED_AT}" in result.output


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (refusal("pending", pending=12), "12 answers still without a grade"),
        (refusal("pending", pending=1), "1 answer still without a grade"),
        (
            refusal("exception-open", exceptions=2),
            "2 student exceptions still keep a personal window open",
        ),
        (refusal("not-closed"), "Close it on the exam's page"),
        (refusal("not-an-exam"), "only an EXAM releases grades"),
    ],
)
def test_a_refusal_is_explained_with_its_counts(repo, monkeypatch, body, expected):
    serve(monkeypatch, 409, body)

    result = release(repo)

    assert result.exit_code == 1
    assert "error: cannot release midterm:" in result.output
    assert expected in result.output


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (403, "only the course's instructor can"),
        (404, "no exam midterm in this course"),
        (500, "the server answered 500"),
    ],
)
def test_other_failures_print_one_error_line(repo, monkeypatch, status, expected):
    serve(monkeypatch, status, {"type": "error"})

    result = release(repo)

    assert result.exit_code == 1
    assert expected in result.output


def test_without_codehood_toml_sends_nothing(tmp_path, monkeypatch):
    calls = serve(monkeypatch, 200, EXAM)

    result = release(tmp_path)

    assert result.exit_code == 1
    assert calls == []
