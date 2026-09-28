"""
Tests for `codehood.push.run`, the imperative shell -- the only part of
`codehood.push` that touches HTTP. See `dev/specs/to-do/push.md`'s
"Architecture" section and `dev/specs/to-do/push.handoff.md`'s
`push/run.py` section.

All HTTP is mocked at the `httpx` transport level (`httpx.MockTransport`),
never by monkeypatching `codehood.api.generated` functions: these tests are
meant to prove the shell builds the right requests and interprets the
real wire shapes, not just that it calls some function.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import mdq
import pytest

from codehood.api import base as base_module
from codehood.push.calendar import Duration, Event, TimeOfDay, TimeSlot
from codehood.push.plan import (
    DeleteCalendarEvent,
    DeleteQuestion,
    DeleteResource,
    DeleteTimeSlot,
    ServerEvent,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertQuestion,
    UpsertResource,
    UpsertTimeSlot,
    WarnTimeSlotPinned,
)
from codehood.push.resource import CodeData, FileData, MdData
from codehood.push.run import fetch_server_state, run_plan

EXAMPLE_MDQ = """---
title: Example question
---

What is 2 + 2?

- [ ] 3
- [*] 4
- [ ] 5
"""

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

DISCIPLINE = "cs101"
COURSE = "ada_2026-1"
BASE = f"/api/course/{DISCIPLINE}/{COURSE}"


@pytest.fixture(autouse=True)
def _authenticated(tmp_path, monkeypatch):
    """
    Every generated call in `run.py` goes through `auth_headers`, which
    raises `NotLoggedInError` with no stored token -- give every test a
    scratch credentials store with a token already saved, so these tests
    exercise the push wire format, not login.
    """
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", tmp_path / "credentials.toml")
    base_module.save_token("http://localhost:4321", "test-token")


def _course_json(**overrides) -> dict:
    body = {
        "description": "A course.",
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
        "startAt": "2026-01-01T00:00:00Z",
        "endAt": "2026-06-01T00:00:00Z",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "joinedAt": "2026-01-01T00:00:00Z",
    }
    body.update(overrides)
    return body


def _resource_json(slug: str, ref: str, **overrides) -> dict:
    body = {
        "slug": slug,
        "title": slug,
        "description": None,
        "data": {"type": "MD", "content": "body"},
        "ref": ref,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    body.update(overrides)
    return body


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="http://localhost:4321", transport=httpx.MockTransport(handler)
    )


def _timeslot_json(
    slug: str, day: str, hour: int, minute: int, hours: int, minutes: int, **overrides
) -> dict:
    body = {
        "id": 1,
        "courseId": 1,
        "slug": slug,
        "title": "Lecture",
        "day": day,
        "start": {"hour": hour, "minute": minute},
        "duration": {"hours": hours, "minutes": minutes},
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    body.update(overrides)
    return body


def _calendar_event_json(
    week: int,
    time_slot_slug: str,
    day: str,
    hour: int,
    minute: int,
    hours: int,
    minutes: int,
    title: str,
    description: str | None,
    *,
    kind: str = "REGULAR",
    ref: str = "ref-event",
    **overrides,
) -> dict:
    body = {
        "kind": kind,
        "title": title,
        "description": description,
        "startAt": "2026-01-05T00:00:00Z",
        "week": week,
        "timeSlot": {
            "slug": time_slot_slug,
            "day": day,
            "start": {"hour": hour, "minute": minute},
            "duration": {"hours": hours, "minutes": minutes},
        },
        "ref": ref,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    body.update(overrides)
    return body


#
# fetch_server_state
#
def _question_json(slug: str, version: str, **overrides) -> dict:
    body = {
        "slug": slug,
        "id": 1,
        "status": "DRAFT",
        "version": version,
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


def test_fetch_server_state_reports_course_missing_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == BASE
        return httpx.Response(404, json={"message": "not found"})

    state = fetch_server_state(DISCIPLINE, COURSE, _client(handler))
    assert state.course_exists is False
    assert dict(state.resources) == {}
    assert dict(state.questions) == {}


def test_fetch_server_state_reports_course_and_resource_refs():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == BASE:
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource":
            return httpx.Response(
                200,
                json=[
                    _resource_json("week1-slides", "ref-a"),
                    _resource_json("week1-notes", "ref-b"),
                ],
            )
        if request.url.path == f"{BASE}/question":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/time-slot":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/calendar-event":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.url}")

    state = fetch_server_state(DISCIPLINE, COURSE, _client(handler))
    assert state.course_exists is True
    assert dict(state.resources) == {"week1-slides": "ref-a", "week1-notes": "ref-b"}


def test_fetch_server_state_reports_question_versions():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == BASE:
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/question":
            return httpx.Response(
                200,
                json=[
                    _question_json("week1-big-o", "md5:aaa"),
                    _question_json("week1-sorting", "md5:bbb"),
                ],
            )
        if request.url.path == f"{BASE}/time-slot":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/calendar-event":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.url}")

    state = fetch_server_state(DISCIPLINE, COURSE, _client(handler))
    assert dict(state.questions) == {
        "week1-big-o": "md5:aaa",
        "week1-sorting": "md5:bbb",
    }


def test_fetch_server_state_course_missing_skips_the_question_listing():
    """
    "A course that does not exist yet reports no resources and no
    questions" -- and does so without even asking the question endpoint,
    the same way it already skips the resource one.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == BASE:
            return httpx.Response(404, json={"message": "not found"})
        raise AssertionError(f"unexpected request: {request.url}")

    state = fetch_server_state(DISCIPLINE, COURSE, _client(handler))
    assert state.questions == {}


def test_fetch_server_state_course_missing_skips_the_calendar_listings():
    """
    Same short-circuit as resources/questions: a course that does not
    exist yet reports no time slots and no calendar events, without ever
    asking `.../time-slot` or `.../calendar-event`.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == BASE:
            return httpx.Response(404, json={"message": "not found"})
        raise AssertionError(f"unexpected request: {request.url}")

    state = fetch_server_state(DISCIPLINE, COURSE, _client(handler))
    assert state.time_slots == {}
    assert state.calendar_events == {}


def test_fetch_server_state_recomputes_time_slot_refs_locally():
    """
    "The server's TimeSlot carries no `ref` column, so `fetch_server_state`
    recomputes each slot's ref from the fields it did return, via the same
    `TimeSlot` dataclass" -- so a slot the CLI never wrote still compares
    correctly against a local one with identical content.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == BASE:
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/question":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/time-slot":
            return httpx.Response(
                200,
                json=[_timeslot_json("mon", "MONDAY", 14, 0, 2, 0, title="Lecture")],
            )
        if request.url.path == f"{BASE}/calendar-event":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.url}")

    state = fetch_server_state(DISCIPLINE, COURSE, _client(handler))
    expected_ref = TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
        title="Lecture",
    ).ref
    assert dict(state.time_slots) == {"mon": expected_ref}


def test_fetch_server_state_reports_calendar_events_as_markers():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == BASE:
            return httpx.Response(200, json=_course_json())
        if request.url.path == f"{BASE}/resource":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/question":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/time-slot":
            return httpx.Response(200, json=[])
        if request.url.path == f"{BASE}/calendar-event":
            return httpx.Response(
                200,
                json=[
                    _calendar_event_json(
                        0,
                        "mon",
                        "MONDAY",
                        14,
                        0,
                        2,
                        0,
                        "Intro",
                        "Welcome.",
                        kind="REGULAR",
                        ref="ref-a",
                    ),
                    _calendar_event_json(
                        3,
                        "mon",
                        "MONDAY",
                        14,
                        0,
                        2,
                        0,
                        "Midterm break",
                        None,
                        kind="CANCELLED",
                        ref="ref-b",
                    ),
                ],
            )
        raise AssertionError(f"unexpected request: {request.url}")

    state = fetch_server_state(DISCIPLINE, COURSE, _client(handler))
    assert dict(state.calendar_events) == {
        (0, "mon"): ServerEvent(ref="ref-a", kind="REGULAR"),
        (3, "mon"): ServerEvent(ref="ref-b", kind="CANCELLED"),
    }


#
# run_plan: UpsertCourse
#
def test_run_plan_upsert_course_puts_the_natural_key_in_the_body():
    """
    `upsertCourse` is mounted on the collection, not on the course's own
    path, so `{instructor}_{edition}` has to be split back into the two
    fields the body names.
    """
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/api/course"
        sent.update(json.loads(request.content))
        return httpx.Response(200, json=_course_json())

    op = UpsertCourse(
        discipline=DISCIPLINE,
        course=COURSE,
        description="A course.",
        start_at="2026-01-01T00:00:00Z",
        end_at="2026-06-01T00:00:00Z",
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.op is op
    assert result.ok is True
    assert sent["discipline"] == DISCIPLINE
    assert sent["instructor"] == "ada"
    assert sent["edition"] == "2026-1"
    assert sent["description"] == "A course."


def test_run_plan_upsert_course_404_yields_a_failed_result_not_a_raise():
    """
    Missing discipline/edition: the spec's "Missing discipline/edition
    fails with a clear message, no traceback" combined with "A failure
    does not stop the push... remaining operations still run" means
    `run_plan` must catch this per-op, not let it propagate out of the
    generator.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "discipline not found"})

    op = UpsertCourse(
        discipline=DISCIPLINE,
        course=COURSE,
        description="A course.",
        start_at="2026-01-01T00:00:00Z",
        end_at="2026-06-01T00:00:00Z",
    )
    results = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert [r.ok for r in results] == [False]
    assert results[0].message


#
# run_plan: UpsertResource / DeleteResource
#
def test_run_plan_upsert_resource_md_sends_the_tagged_union():
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == f"{BASE}/resource"
        sent.update(json.loads(request.content))
        return httpx.Response(200, json=_resource_json("week1-slides", "ref-a"))

    op = UpsertResource(
        slug="week1-slides",
        title="Slides",
        description=None,
        data=MdData(content="# Slides\n"),
        ref="ref-a",
        path=Path("resources/week1/slides.md"),
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True
    assert sent == {
        "slug": "week1-slides",
        "title": "Slides",
        "description": None,
        "ref": "ref-a",
        "data": {"type": "MD", "content": "# Slides\n"},
    }


def test_run_plan_upsert_resource_code_carries_its_language():
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(200, json=_resource_json("factorial", "ref-c"))

    op = UpsertResource(
        slug="factorial",
        title="factorial",
        description=None,
        data=CodeData(content="def f(): ...\n", language="python"),
        ref="ref-c",
        path=Path("resources/factorial.py"),
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True
    assert sent["data"] == {
        "type": "CODE",
        "content": "def f(): ...\n",
        "language": "python",
    }


def test_run_plan_delete_resource_succeeds():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == f"{BASE}/resource/week1-slides"
        return httpx.Response(
            200, json={"success": True, "message": "deleted", "deleted": True}
        )

    op = DeleteResource(slug="week1-slides")
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True


def test_run_plan_file_resource_is_blocked_without_any_http_call():
    """
    ROADBLOCKS.md item 1: the server types a `FILE`'s `buffer` as
    `z.instanceof(Buffer)`, which no JSON body can satisfy, and offers no
    multipart branch. So a `FILE` `UpsertResource` must fail cleanly and
    touch no endpoint at all -- a request reaching the transport is itself
    the failure.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"FILE upload must not call the network: {request.url}")

    op = UpsertResource(
        slug="handout",
        title="Handout",
        description=None,
        data=FileData(filename="handout.pdf", blob=b"%PDF-not-really\n"),
        ref="ref-file",
        path=Path("resources/handout.pdf"),
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is False
    assert "blocked" in result.message


def test_run_plan_continues_after_a_failure():
    """FR-SYNC-005: one failed op does not stop the remaining ones."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        # Both upserts `PUT` the same collection path now, so the slug in
        # the body is the only thing that tells them apart.
        slug = json.loads(request.content)["slug"]
        calls.append(slug)
        if slug == "bad":
            return httpx.Response(500, json={"message": "server error"})
        return httpx.Response(200, json=_resource_json("good", "ref-good"))

    bad = UpsertResource(
        slug="bad",
        title="Bad",
        description=None,
        data=MdData(content="x"),
        ref="ref-bad",
        path=Path("resources/bad.md"),
    )
    good = UpsertResource(
        slug="good",
        title="Good",
        description=None,
        data=MdData(content="x"),
        ref="ref-good",
        path=Path("resources/good.md"),
    )
    results = list(
        run_plan(
            [bad, good], discipline=DISCIPLINE, course=COURSE, client=_client(handler)
        )
    )
    assert [r.ok for r in results] == [False, True]
    # Both requests were actually made -- the failure did not short-circuit.
    assert len(calls) == 2


#
# run_plan: UpsertQuestion / DeleteQuestion
#
def test_run_plan_upsert_question_drops_weight_and_grading_but_keeps_the_rest():
    """
    "weight and grading are dropped on the wire" -- see
    `dev/specs/to-do/push-questions.md`. Every other field, including the
    camelCase-aliased ones `mdq` already produces, survives untouched.
    """
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == f"{BASE}/question"
        sent.update(json.loads(request.content))
        return httpx.Response(
            200, json=_question_json("week1-big-o", "md5:aaa", status="DRAFT")
        )

    question = mdq.parse(EXAMPLE_MDQ, kind="question", ids="fill")
    op = UpsertQuestion(
        slug="week1-big-o",
        version="md5:aaa",
        question=question,
        path=Path("questions/week1/big-o.md"),
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True
    assert "weight" not in sent["question"]
    assert "grading" not in sent["question"]
    assert sent["question"]["type"] == "multiple-choice"
    assert sent["question"]["stem"] == "What is 2 + 2?"
    assert sent["slug"] == "week1-big-o"
    assert sent["version"] == "md5:aaa"
    assert sent["status"] == "DRAFT"


def test_run_plan_upsert_question_short_answer_keeps_camel_case_aliases():
    """
    `mdq` sets a camelCase alias generator: `openEnded` must survive the
    round trip through `run.py`'s translation, not get dropped or
    renamed.
    """
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(
            200, json=_question_json("open-answer", "md5:bbb", status="DRAFT")
        )

    short_answer = """---
title: Open answer
type: short-answer
openEnded: true
---

Describe your reasoning.

[short-answer]:
"""
    question = mdq.parse(short_answer, kind="question", ids="fill")
    op = UpsertQuestion(
        slug="open-answer",
        version="md5:bbb",
        question=question,
        path=Path("questions/open-answer.md"),
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True
    assert sent["question"]["openEnded"] is True


def test_run_plan_upsert_ordering_question_is_blocked_without_any_http_call():
    """
    `mdq` parses `ordering` questions; the server's `question` union has
    no such member. Refused at execution, like a `FILE` resource, and
    must send no request at all.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"an ordering question must not call the network: {request.url}"
        )

    question = mdq.parse(ORDERING_MDQ, kind="question", ids="fill")
    op = UpsertQuestion(
        slug="order-the-steps",
        version="md5:ccc",
        question=question,
        path=Path("questions/order-the-steps.md"),
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is False
    assert result.message


def test_run_plan_upsert_question_http_failure_yields_a_failed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    question = mdq.parse(EXAMPLE_MDQ, kind="question", ids="fill")
    op = UpsertQuestion(
        slug="week1-big-o",
        version="md5:aaa",
        question=question,
        path=Path("questions/week1-big-o.md"),
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is False
    assert result.message


def test_run_plan_delete_question_succeeds():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == f"{BASE}/question/stale-warmup"
        return httpx.Response(
            200, json={"success": True, "message": "deleted", "deleted": True}
        )

    op = DeleteQuestion(slug="stale-warmup")
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True


def test_run_plan_delete_question_http_failure_yields_a_failed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    op = DeleteQuestion(slug="stale-warmup")
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is False
    assert result.message


#
# run_plan: UpsertTimeSlot / DeleteTimeSlot
#
def test_run_plan_upsert_time_slot_puts_the_slot_on_the_collection():
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == f"{BASE}/time-slot"
        sent.update(json.loads(request.content))
        return httpx.Response(
            200, json=_timeslot_json("mon", "MONDAY", 14, 0, 2, 0, title="Lecture")
        )

    op = UpsertTimeSlot(
        slot=TimeSlot(
            slug="mon",
            day="MONDAY",
            start=TimeOfDay(hour=14, minute=0),
            duration=Duration(hours=2, minutes=0),
            title="Lecture",
        )
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True
    assert sent == {
        "slug": "mon",
        "title": "Lecture",
        "day": "MONDAY",
        "start": {"hour": 14, "minute": 0},
        "duration": {"hours": 2, "minutes": 0},
    }


def test_run_plan_upsert_time_slot_http_failure_yields_a_failed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    op = UpsertTimeSlot(
        slot=TimeSlot(
            slug="mon",
            day="MONDAY",
            start=TimeOfDay(hour=14, minute=0),
            duration=Duration(hours=2, minutes=0),
        )
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is False
    assert result.message


def test_run_plan_delete_time_slot_by_slug():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == f"{BASE}/time-slot/mon"
        return httpx.Response(
            200, json={"success": True, "message": "deleted", "deleted": True}
        )

    op = DeleteTimeSlot(slug="mon")
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True


def test_run_plan_delete_time_slot_http_failure_yields_a_failed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    op = DeleteTimeSlot(slug="mon")
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is False
    assert result.message


#
# run_plan: UpsertCalendarEvent / DeleteCalendarEvent
#
def test_run_plan_upsert_calendar_event_puts_week_and_time_slot_slug():
    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == f"{BASE}/calendar-event"
        sent.update(json.loads(request.content))
        return httpx.Response(
            200,
            json=_calendar_event_json(
                0, "mon", "MONDAY", 14, 0, 2, 0, "Intro", "Welcome.", ref="ref-a"
            ),
        )

    event = Event(week=0, time_slot="mon", title="Intro", description="Welcome.")
    op = UpsertCalendarEvent(event=event)
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True
    assert sent["week"] == 0
    assert sent["timeSlot"] == "mon"
    assert sent["title"] == "Intro"
    assert sent["description"] == "Welcome."
    assert sent["kind"] == "REGULAR"
    assert sent["ref"] == event.ref


def test_run_plan_upsert_calendar_event_http_failure_yields_a_failed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    op = UpsertCalendarEvent(
        event=Event(week=0, time_slot="mon", title="Intro", description="")
    )
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is False
    assert result.message


def test_run_plan_delete_calendar_event_by_week_and_time_slot():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == f"{BASE}/calendar-event/3/mon"
        return httpx.Response(
            200, json={"success": True, "message": "deleted", "deleted": True}
        )

    op = DeleteCalendarEvent(week=3, time_slot="mon")
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True


def test_run_plan_delete_calendar_event_http_failure_yields_a_failed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "server error"})

    op = DeleteCalendarEvent(week=3, time_slot="mon")
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is False
    assert result.message


def test_run_plan_warn_time_slot_pinned_makes_no_request_and_succeeds():
    """
    `WarnTimeSlotPinned` isn't a write: the mapping's "Deletion and
    pruning" leaves a `CANCELLED`-pinned slot untouched, so executing this
    op must call no endpoint at all and still report success.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"a pinned-slot warning must not call the network: {request.url}"
        )

    op = WarnTimeSlotPinned(slug="wed", week=2)
    [result] = list(
        run_plan([op], discipline=DISCIPLINE, course=COURSE, client=_client(handler))
    )
    assert result.ok is True
