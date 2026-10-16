"""
Tests for `codehood push`, the Typer command in `codehood.cli.push`. See
`dev/specs/to-do/push.md`'s "CLI surface" and "Proof" sections, and
`dev/specs/to-do/push.handoff.md`'s "Acceptance criteria".

HTTP is mocked at the `httpx` transport level and injected by monkeypatching
`get_client` on the `codehood.cli.push` module -- the name the command
actually calls, not the function it was imported from (patching
`codehood.api.base.get_client` would not affect an already-bound import).
`codehood.cli`'s `__init__.py` rebinds the `push` attribute on the package
to the Typer command function, shadowing the submodule -- `importlib` is
what still hands back the real module, mirroring `test_cli_api.py`.
"""

from __future__ import annotations

import importlib
import json

import httpx
import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.cli.base import app

push_module = importlib.import_module("codehood.cli.push")

runner = CliRunner()

DISCIPLINE = "cs101"
COURSE = "ada_2026-1"
EDITION = "2026-1"
SERVER = "http://localhost:4321"
BASE = f"/api/course/{DISCIPLINE}/{COURSE}"
#: `upsertCourse` is mounted on the collection, not on the course itself.
COURSE_COLLECTION = "/api/course"

TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    f'\n[server]\nurl = "{SERVER}"\n'
)

#: `calendar.md` sets the course's own `start`/`end` -- `push.py` no longer
#: reads the edition for dates (see `push-calendar.handoff.md`, "Changed:
#: `codehood/cli/push.py`"). One Monday slot and one undated section: every
#: `repo`-based test gets exactly one `TimeSlot` and one allocated `Event`
#: on top of whatever resources/questions it adds, so every handler in this
#: file has to answer `.../time-slot` and `.../calendar-event` too.
CALENDAR_MD = """---
start: 2026-01-01
end:   2026-06-01
days:
  - Mon 14:00 2h, Lecture
holidays: []
---

# Schedule

## Course overview

What we will cover.
"""


def _course_json(**overrides) -> dict:
    body = {
        "description": "A description.",
        "discipline": {"slug": DISCIPLINE, "name": "Intro to CS"},
        "edition": {
            "slug": "2026-1",
            "name": "2026-1",
            "startAt": "2026-01-01T00:00:00Z",
            "endAt": "2026-06-01T00:00:00Z",
            "createdAt": "2026-01-01T00:00:00Z",
        },
        "instructor": {"name": "Ada Lovelace", "username": "ada"},
        "enrollmentCount": 0,
        "rev": None,
        "startAt": "2026-01-01T00:00:00Z",
        "endAt": "2026-06-01T00:00:00Z",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "joinedAt": "2026-01-01T00:00:00Z",
    }
    body.update(overrides)
    return body


def _timeslot_json(slug: str = "mon", **overrides) -> dict:
    body = {
        "id": 1,
        "courseId": 1,
        "slug": slug,
        "title": "Lecture",
        "day": "MONDAY",
        "start": {"hour": 14, "minute": 0},
        "duration": {"hours": 2, "minutes": 0},
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    body.update(overrides)
    return body


def _calendar_event_json(
    week: int = 0, time_slot_slug: str = "mon", **overrides
) -> dict:
    body = {
        "kind": "REGULAR",
        "title": "Course overview",
        "description": "What we will cover.",
        "startAt": "2026-01-05T00:00:00Z",
        "week": week,
        "timeSlot": {
            "slug": time_slot_slug,
            "day": "MONDAY",
            "start": {"hour": 14, "minute": 0},
            "duration": {"hours": 2, "minutes": 0},
        },
        "rev": "ref-event",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    body.update(overrides)
    return body


def _calendar_defaults(request: httpx.Request) -> httpx.Response | None:
    """
    A default answer for the calendar half of a course's server state, for
    handlers that don't care about it: an empty listing on `GET`, a bare
    success on `PUT`. Every `repo`-based handler needs *some* answer here,
    since `read_local_state` always derives one `TimeSlot` and one `Event`
    from `calendar.md`. Returns `None` when `request` isn't a calendar
    call, so callers can fall through to their own branches.
    """
    if request.url.path == f"{BASE}/roll-call" and request.method == "GET":
        return httpx.Response(200, json=[])
    if request.url.path == f"{BASE}/time-slot":
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.method == "PUT":
            return httpx.Response(200, json=_timeslot_json())
    if request.url.path == f"{BASE}/calendar-event":
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.method == "PUT":
            return httpx.Response(200, json=_calendar_event_json())
    return None


def _resource_json(slug: str, ref: str, **overrides) -> dict:
    body = {
        "slug": slug,
        "title": slug,
        "description": None,
        "data": {"type": "MD", "content": "body"},
        "event": None,
        "rev": ref,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    body.update(overrides)
    return body


EXAMPLE_MDQ = """---
title: Example question
---

What is 2 + 2?

- [ ] 3
- [*] 4
- [ ] 5
"""


def _question_json(slug: str, version: str, **overrides) -> dict:
    body = {
        "slug": slug,
        "id": 1,
        "status": "DRAFT",
        "version": version,
        "rev": None,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "question": {
            "type": "multiple-choice",
            "stem": "What is 2 + 2?",
            "choices": [
                {"id": "three", "text": "3", "score": 0.0},
                {"id": "four", "text": "4", "score": 1.0},
            ],
        },
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def credentials_path(tmp_path_factory, monkeypatch):
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)
    base_module.save_token(SERVER, "test-token")


@pytest.fixture
def repo(tmp_path):
    """
    A minimal course repository: `codehood.toml`, `README.md`,
    `calendar.md`, one resource.
    """
    (tmp_path / "codehood.toml").write_text(TOML, encoding="utf-8")
    (tmp_path / "README.md").write_text("# CS101\n\nA description.\n", encoding="utf-8")
    (tmp_path / "calendar.md").write_text(CALENDAR_MD, encoding="utf-8")
    resources = tmp_path / "resources" / "week1"
    resources.mkdir(parents=True)
    (resources / "slides.md").write_text("# Slides\n\nBody.\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def repo_with_question(repo):
    """`repo`, plus one question under `questions/`."""
    questions = repo / "questions"
    questions.mkdir()
    (questions / "big-o.md").write_text(EXAMPLE_MDQ, encoding="utf-8")
    return repo


def _install_transport(monkeypatch, handler) -> None:
    def _get_client(base_url=None):
        return httpx.Client(
            base_url=base_url or SERVER, transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(push_module, "get_client", _get_client)


def _fresh_server_handler(calls: list[tuple[str, str]]):
    """No course, no resources server-side -- everything local is new."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == BASE and request.method == "GET":
            return httpx.Response(404, json={"message": "not found"})
        if request.url.path == f"{BASE}/resource" and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path == COURSE_COLLECTION and request.method == "PUT":
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource" and request.method == "PUT":
            slug = json.loads(request.content)["slug"]
            return httpx.Response(200, json=_resource_json(slug, "whatever"))
        if (response := _calendar_defaults(request)) is not None:
            return response
        if request.method == "GET" and request.url.path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return handler


def test_help_exits_zero():
    result = runner.invoke(app, ["push", "--help"])
    assert result.exit_code == 0


def test_dry_run_performs_zero_writes(repo, monkeypatch):
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method != "GET":
            raise AssertionError(
                f"--dry-run made a write: {request.method} {request.url}"
            )
        if request.url.path == BASE:
            return httpx.Response(404, json={"message": "not found"})
        if request.url.path == f"{BASE}/resource":
            return httpx.Response(200, json=[])
        if request.method == "GET" and request.url.path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.url}")

    _install_transport(monkeypatch, handler)
    result = runner.invoke(app, ["push", str(repo), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert all(method == "GET" for method, _ in calls)
    assert "week1-slides" in result.output


def test_dry_run_prints_a_warning_for_a_cancelled_events_pinned_slot(repo, monkeypatch):
    """
    A `CANCELLED`-pinned slot the local `calendar.md` no longer declares
    survives, but the instructor still needs to see it before deciding --
    `--dry-run` must print the `WarnTimeSlotPinned` line, not only surface
    it once the push actually executes.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            raise AssertionError(
                f"--dry-run made a write: {request.method} {request.url}"
            )
        if request.url.path == BASE:
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/question":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/time-slot":
            return httpx.Response(
                200,
                json=[
                    _timeslot_json("mon"),
                    _timeslot_json(
                        "wed",
                        day="WEDNESDAY",
                        start={"hour": 9, "minute": 0},
                        duration={"hours": 1, "minutes": 0},
                    ),
                ],
            )
        if request.url.path == f"{BASE}/roll-call":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/calendar-event":
            return httpx.Response(
                200,
                json=[
                    _calendar_event_json(),
                    _calendar_event_json(
                        week=2,
                        time_slot_slug="wed",
                        kind="CANCELLED",
                        title="Midterm",
                        description=None,
                        ref="ref-cancelled",
                    ),
                ],
            )
        if request.method == "GET" and request.url.path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    _install_transport(monkeypatch, handler)
    result = runner.invoke(app, ["push", str(repo), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "wed" in result.output


def test_full_push_creates_course_and_resource(repo, monkeypatch):
    calls: list[tuple[str, str]] = []
    _install_transport(monkeypatch, _fresh_server_handler(calls))

    result = runner.invoke(app, ["push", str(repo)])

    assert result.exit_code == 0, result.output
    assert ("PUT", COURSE_COLLECTION) in calls
    assert ("PUT", f"{BASE}/resource") in calls
    assert "week1-slides" in result.output


def test_no_prune_reports_deletion_without_executing_it(repo, monkeypatch):
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == BASE and request.method == "GET":
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource" and request.method == "GET":
            # A resource the server has that the local repo no longer does.
            return httpx.Response(
                200,
                json=[
                    _resource_json("week1-slides", _local_ref(repo)),
                    _resource_json("stale-handout", "server-only-ref"),
                ],
            )
        if request.url.path == f"{BASE}/question" and request.method == "GET":
            # `fetch_server_state` now also reads questions; this repo
            # fixture has none, so nothing is planned for them either way.
            return httpx.Response(200, json=[])
        if request.url.path == COURSE_COLLECTION and request.method == "PUT":
            return httpx.Response(200, json=_course_json())
        if (
            request.url.path.startswith(f"{BASE}/resource/")
            and request.method == "DELETE"
        ):
            raise AssertionError("--no-prune must not execute a deletion")
        if (response := _calendar_defaults(request)) is not None:
            return response
        if request.method == "GET" and request.url.path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    _install_transport(monkeypatch, handler)
    result = runner.invoke(app, ["push", str(repo), "--no-prune"])

    assert result.exit_code == 0, result.output
    assert not any(method == "DELETE" for method, _ in calls)
    assert "stale-handout" in result.output


def _local_ref(repo, exclude=()) -> str:
    """
    The `ref` the local `week1/slides.md` fixture would produce, so the
    no-prune scenario's unrelated resource genuinely matches and only
    `stale-handout` is a deletion candidate.
    """
    from codehood.push.resource import scan_resources

    [resource] = list(scan_resources(repo, exclude))
    return resource.ref


def test_a_failed_operation_exits_nonzero_but_still_runs_the_rest(repo, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == BASE and request.method == "GET":
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource" and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path == COURSE_COLLECTION and request.method == "PUT":
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/question" and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/time-slot" and request.method == "PUT":
            return httpx.Response(500, json={"message": "server error"})
        if request.url.path == f"{BASE}/resource" and request.method == "PUT":
            slug = json.loads(request.content)["slug"]
            return httpx.Response(200, json=_resource_json(slug, "whatever"))
        if (response := _calendar_defaults(request)) is not None:
            return response
        if request.method == "GET" and request.url.path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    _install_transport(monkeypatch, handler)
    result = runner.invoke(app, ["push", str(repo)])

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    # The time slot upsert failed, but the resource after it still ran.
    assert "1 failed" in result.output
    assert "ok  resource week1-slides" in result.output


def test_a_failed_course_upsert_stops_the_push_without_a_cascade_of_errors(
    repo_with_question, monkeypatch
):
    """
    Nothing hangs off a course that could not be written: the dependent
    operations are reported as not attempted, never sent, and the one
    real failure is what the instructor reads.
    """
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == BASE and request.method == "GET":
            return httpx.Response(404, json={"message": "not found"})
        if request.url.path == COURSE_COLLECTION and request.method == "PUT":
            return httpx.Response(
                400, json={"message": "the edition does not accept new courses"}
            )
        if request.method == "GET":
            return httpx.Response(200, json=[])
        raise AssertionError(
            f"sent after the course failed: {request.method} {request.url}"
        )

    _install_transport(monkeypatch, handler)
    result = runner.invoke(app, ["push", str(repo_with_question)])

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    assert "the edition does not accept new courses" in result.output
    assert "1 failed" in result.output
    assert "not attempted" in result.output
    assert "404" not in result.output
    assert [call for call in calls if call[0] != "GET"] == [("PUT", COURSE_COLLECTION)]


#
# Questions -- see `dev/specs/to-do/push-questions.md`'s "CLI surface":
# `--dry-run` prints question ops alongside resource ops; `--prune/
# --no-prune` governs question deletions the same way it governs resource
# deletions; a failed question does not stop the push and the exit code
# is 1 if anything failed.
#
def test_dry_run_prints_question_ops(repo_with_question, monkeypatch):
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method != "GET":
            raise AssertionError(
                f"--dry-run made a write: {request.method} {request.url}"
            )
        if request.url.path == BASE:
            return httpx.Response(404, json={"message": "not found"})
        if request.url.path == f"{BASE}/resource":
            return httpx.Response(200, json=[])
        if request.method == "GET" and request.url.path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.url}")

    _install_transport(monkeypatch, handler)
    result = runner.invoke(app, ["push", str(repo_with_question), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert all(method == "GET" for method, _ in calls)
    assert "big-o" in result.output


def test_no_prune_skips_question_deletions(repo_with_question, monkeypatch):
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == BASE and request.method == "GET":
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource" and request.method == "GET":
            return httpx.Response(
                200,
                json=[_resource_json("week1-slides", _local_ref(repo_with_question))],
            )
        if request.url.path == f"{BASE}/question" and request.method == "GET":
            # `big-o` is local, `stale-warmup` is server-only -- the local
            # question is unchanged, so only `stale-warmup` is a deletion
            # candidate.
            return httpx.Response(
                200,
                json=[
                    _question_json(
                        "big-o", _local_question_version(repo_with_question)
                    ),
                    _question_json("stale-warmup", "md5:server-only"),
                ],
            )
        if request.url.path == COURSE_COLLECTION and request.method == "PUT":
            return httpx.Response(200, json=_course_json())
        if (
            request.url.path.startswith(f"{BASE}/question/")
            and request.method == "DELETE"
        ):
            raise AssertionError("--no-prune must not execute a question deletion")
        if (response := _calendar_defaults(request)) is not None:
            return response
        if request.method == "GET" and request.url.path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    _install_transport(monkeypatch, handler)
    result = runner.invoke(app, ["push", str(repo_with_question), "--no-prune"])

    assert result.exit_code == 0, result.output
    assert not any(
        method == "DELETE" and path.startswith(f"{BASE}/question/")
        for method, path in calls
    )
    assert "stale-warmup" in result.output


def _local_question_version(repo, exclude=()) -> str:
    """The `version` the local `questions/big-o.md` fixture would produce."""
    from codehood.push.question import scan_questions

    [question] = list(scan_questions(repo, exclude))
    return question.version


def test_a_failed_question_operation_exits_nonzero_but_still_runs_the_rest(
    repo_with_question, monkeypatch
):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == BASE and request.method == "GET":
            return httpx.Response(404, json={"message": "not found"})
        if request.url.path == f"{BASE}/resource" and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path == COURSE_COLLECTION and request.method == "PUT":
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource" and request.method == "PUT":
            slug = json.loads(request.content)["slug"]
            return httpx.Response(200, json=_resource_json(slug, "whatever"))
        if request.url.path == f"{BASE}/question" and request.method == "PUT":
            return httpx.Response(500, json={"message": "server error"})
        if (response := _calendar_defaults(request)) is not None:
            return response
        if request.method == "GET" and request.url.path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    _install_transport(monkeypatch, handler)
    result = runner.invoke(app, ["push", str(repo_with_question)])

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    # The question upsert failed, but the resource upsert still ran.
    assert "week1-slides" in result.output
    assert "big-o" in result.output


#
# Roll calls -- an event removed from `calendar.md` that has a roll call is
# kept with a warning; `--drop-roll-calls` deletes the roll call and then the
# event, and `--no-prune` skips both deletions.
#
def _roll_call_json(week: int, time_slot: str, attendances: int) -> dict:
    return {
        "week": week,
        "timeSlot": time_slot,
        "actsAsInvite": False,
        "closesAt": "2026-02-02T15:00:00Z",
        "attendances": {
            f"student{number}": {
                "source": "CODE",
                "joined": "ENROLLMENT",
                "note": None,
                "sharedWith": [],
                "createdAt": "2026-02-02T14:30:00Z",
            }
            for number in range(attendances)
        },
        "createdAt": "2026-02-02T14:00:00Z",
        "updatedAt": "2026-02-02T14:00:00Z",
    }


def _roll_call_server_handler(repo, calls: list[tuple[str, str]]):
    """
    A course whose server still has event `(5, mon)`, with a roll call of 32
    presences, that the local `calendar.md` no longer declares.
    """
    deleted = {"success": True, "message": "deleted", "deleted": True}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path, method = request.url.path, request.method
        if path == BASE and method == "GET":
            return httpx.Response(200, json=_course_json())
        if path == f"{BASE}/resource" and method == "GET":
            return httpx.Response(
                200, json=[_resource_json("week1-slides", _local_ref(repo))]
            )
        if path == f"{BASE}/question" and method == "GET":
            return httpx.Response(200, json=[])
        if path == f"{BASE}/time-slot" and method == "GET":
            return httpx.Response(200, json=[_timeslot_json("mon")])
        if path == f"{BASE}/calendar-event" and method == "GET":
            return httpx.Response(200, json=[_calendar_event_json(week=5)])
        if path == f"{BASE}/roll-call" and method == "GET":
            return httpx.Response(200, json=[_roll_call_json(5, "mon", 32)])
        if path == f"{BASE}/grade-column" and method == "GET":
            return httpx.Response(200, json=[])
        if method == "DELETE" and path in (
            f"{BASE}/roll-call/5/mon",
            f"{BASE}/calendar-event/5/mon",
        ):
            return httpx.Response(200, json=deleted)
        if path == COURSE_COLLECTION and method == "PUT":
            return httpx.Response(200, json=_course_json())
        if (response := _calendar_defaults(request)) is not None:
            return response
        raise AssertionError(f"unexpected request: {method} {request.url}")

    return handler


def _deletes(calls: list[tuple[str, str]]) -> list[str]:
    return [path for method, path in calls if method == "DELETE"]


def test_push_reports_an_event_kept_for_its_roll_call_and_deletes_nothing(
    repo, monkeypatch
):
    calls: list[tuple[str, str]] = []
    _install_transport(monkeypatch, _roll_call_server_handler(repo, calls))

    result = runner.invoke(app, ["push", str(repo)])

    assert result.exit_code == 0, result.output
    assert "5/mon" in result.output
    assert "32" in result.output
    assert "--drop-roll-calls" in result.output
    assert _deletes(calls) == []


def test_drop_roll_calls_deletes_the_roll_call_before_its_event(repo, monkeypatch):
    calls: list[tuple[str, str]] = []
    _install_transport(monkeypatch, _roll_call_server_handler(repo, calls))

    result = runner.invoke(app, ["push", str(repo), "--drop-roll-calls"])

    assert result.exit_code == 0, result.output
    assert _deletes(calls) == [
        f"{BASE}/roll-call/5/mon",
        f"{BASE}/calendar-event/5/mon",
    ]


def test_drop_roll_calls_with_no_prune_skips_both_deletions(repo, monkeypatch):
    calls: list[tuple[str, str]] = []
    _install_transport(monkeypatch, _roll_call_server_handler(repo, calls))

    result = runner.invoke(app, ["push", str(repo), "--drop-roll-calls", "--no-prune"])

    assert result.exit_code == 0, result.output
    assert _deletes(calls) == []
    assert result.output.count("(--no-prune)") == 2


#
# `[push] exclude` -- files matching a pattern are neither parsed nor
# pushed, and what the server already holds for them is left alone.
#
ORDERING_MDQ = """---
title: Order the steps
type: ordering
---

Put these steps in order.

[ordering]
```
first
second
third
```
"""


def _exclude_toml(*patterns: str) -> str:
    listed = ", ".join(json.dumps(pattern) for pattern in patterns)
    return TOML + f"\n[push]\nexclude = [{listed}]\n"


def _add_question(repo, name: str, text: str = EXAMPLE_MDQ) -> None:
    path = repo / "questions" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _server_with(
    calls: list[tuple[str, str]],
    *,
    questions: list[dict] | None = None,
    resources: list[dict] | None = None,
):
    """A course that exists and already holds the given questions/resources."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path, method = request.url.path, request.method
        if path == BASE and method == "GET":
            return httpx.Response(200, json=_course_json())
        if path == f"{BASE}/resource" and method == "GET":
            return httpx.Response(200, json=resources or [])
        if path == f"{BASE}/question" and method == "GET":
            return httpx.Response(200, json=questions or [])
        if path == COURSE_COLLECTION and method == "PUT":
            return httpx.Response(200, json=_course_json())
        if path == f"{BASE}/resource" and method == "PUT":
            slug = json.loads(request.content)["slug"]
            return httpx.Response(200, json=_resource_json(slug, "whatever"))
        if path == f"{BASE}/question" and method == "PUT":
            slug = json.loads(request.content)["slug"]
            return httpx.Response(200, json=_question_json(slug, "whatever"))
        if (response := _calendar_defaults(request)) is not None:
            return response
        if method == "GET" and path == f"{BASE}/grade-column":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {method} {request.url}")

    return handler


def _writes_to(calls: list[tuple[str, str]], kind: str) -> list[tuple[str, str]]:
    return [
        (method, path)
        for method, path in calls
        if method in ("PUT", "DELETE") and path.startswith(f"{BASE}/{kind}")
    ]


def test_an_unsupported_question_blocks_the_push_unless_excluded(
    repo_with_question, monkeypatch
):
    _add_question(repo_with_question, "order.mdq", ORDERING_MDQ)
    calls: list[tuple[str, str]] = []
    _install_transport(monkeypatch, _server_with(calls))

    blocked = runner.invoke(app, ["push", str(repo_with_question)])
    assert blocked.exit_code == 1, blocked.output

    (repo_with_question / "codehood.toml").write_text(
        _exclude_toml("questions/order.mdq"), encoding="utf-8"
    )
    calls.clear()
    result = runner.invoke(app, ["push", str(repo_with_question)])

    assert result.exit_code == 0, result.output
    assert "blocked" not in result.output
    assert "questions/order.mdq" in result.output
    assert "1 excluded" in result.output
    # The question that is not excluded still goes out.
    assert _writes_to(calls, "question") == [("PUT", f"{BASE}/question")]


@pytest.mark.parametrize(
    "pattern",
    [
        "questions/wip",
        "questions/wip/",
        "questions/wip/**",
        "questions/**/draft-*.mdq",
        "questions/wip/draft-?.mdq",
        "**/draft-1.mdq",
    ],
)
def test_exclude_patterns_reach_nested_questions(
    repo_with_question, monkeypatch, pattern
):
    _add_question(repo_with_question, "wip/draft-1.mdq", "not a valid question {{")
    (repo_with_question / "codehood.toml").write_text(
        _exclude_toml(pattern), encoding="utf-8"
    )
    calls: list[tuple[str, str]] = []
    _install_transport(monkeypatch, _server_with(calls))

    result = runner.invoke(app, ["push", str(repo_with_question)])

    # The excluded file is not even parsed: it would be a parse error.
    assert result.exit_code == 0, result.output
    assert "wip/draft-1.mdq" in result.output
    assert len(_writes_to(calls, "question")) == 1


def test_a_pattern_that_matches_nothing_excludes_nothing(
    repo_with_question, monkeypatch
):
    (repo_with_question / "codehood.toml").write_text(
        _exclude_toml("questions/other.mdq", "questions/*.txt"), encoding="utf-8"
    )
    calls: list[tuple[str, str]] = []
    _install_transport(monkeypatch, _server_with(calls))

    result = runner.invoke(app, ["push", str(repo_with_question)])

    assert result.exit_code == 0, result.output
    assert "excluded" not in result.output
    assert ("PUT", f"{BASE}/question") in calls


def test_an_excluded_question_that_is_on_the_server_is_left_alone(
    repo_with_question, monkeypatch
):
    _add_question(repo_with_question, "order.mdq", ORDERING_MDQ)
    (repo_with_question / "codehood.toml").write_text(
        _exclude_toml("questions/order.mdq"), encoding="utf-8"
    )
    calls: list[tuple[str, str]] = []
    server = _server_with(
        calls,
        resources=[_resource_json("week1-slides", _local_ref(repo_with_question))],
        questions=[
            _question_json(
                "big-o",
                _local_question_version(repo_with_question, ["questions/order.mdq"]),
            ),
            _question_json("order", "md5:old-version-from-the-server"),
        ],
    )
    _install_transport(monkeypatch, server)

    result = runner.invoke(app, ["push", str(repo_with_question)])

    assert result.exit_code == 0, result.output
    assert _writes_to(calls, "question") == []


def test_an_excluded_resource_is_neither_pushed_nor_deleted(repo, monkeypatch):
    (repo / "resources" / "week1" / "private.md").write_text(
        "# Private\n", encoding="utf-8"
    )
    (repo / "codehood.toml").write_text(
        _exclude_toml("resources/week1/private.md"), encoding="utf-8"
    )
    calls: list[tuple[str, str]] = []
    server = _server_with(
        calls,
        resources=[
            _resource_json(
                "week1-slides", _local_ref(repo, ["resources/week1/private.md"])
            ),
            _resource_json("week1-private", "server-ref"),
        ],
    )
    _install_transport(monkeypatch, server)

    result = runner.invoke(app, ["push", str(repo)])

    assert result.exit_code == 0, result.output
    assert _writes_to(calls, "resource") == []
    assert "resources/week1/private.md" in result.output


def test_dry_run_reports_excluded_files(repo_with_question, monkeypatch):
    _add_question(repo_with_question, "order.mdq", ORDERING_MDQ)
    (repo_with_question / "codehood.toml").write_text(
        _exclude_toml("questions/order.mdq"), encoding="utf-8"
    )
    calls: list[tuple[str, str]] = []
    _install_transport(monkeypatch, _server_with(calls))

    result = runner.invoke(app, ["push", str(repo_with_question), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "questions/order.mdq" in result.output
    assert "1 excluded" in result.output


def test_a_malformed_exclude_table_is_a_config_error(repo, monkeypatch):
    (repo / "codehood.toml").write_text(TOML + '\n[push]\nexclude = "x"\n')
    _install_transport(monkeypatch, _server_with([]))

    result = runner.invoke(app, ["push", str(repo)])

    assert result.exit_code == 1, result.output
    assert "exclude" in result.output
