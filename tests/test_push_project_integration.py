"""
Round trip of every synchronized entity against a real dev server: write it
the way `codehood push` does, read it back the way `fetch_server_state`
does, and compare the projection with the payload built from the local form.

Skipped unless `--run-integration` is given and a server answers at
`CODEHOOD_SERVER` (default `http://localhost:4321`).

Writes to `cs101/ada_2026-1` under slugs prefixed `proj-` and deletes them
afterwards. The course row is restored to what it held.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx
import mdq
import pytest

from codehood.api import base as base_module
from codehood.api import generated
from codehood.models.repo import CourseKey
from codehood.push.calendar import Duration, Event, EventKey, TimeOfDay, TimeSlot
from codehood.push.grades import GradeColumn
from codehood.push.plan import (
    DeleteCalendarEvent,
    DeleteGradeColumn,
    DeleteQuestion,
    DeleteResource,
    DeleteTimeSlot,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertGradeColumn,
    UpsertQuestion,
    UpsertResource,
    UpsertTimeSlot,
    Write,
    course_ref,
)
from codehood.push.project import RemoteEntry
from codehood.push.question import QuestionFile, question_version
from codehood.push.resource import (
    CodeData,
    FileData,
    LinkData,
    MdData,
    ResourceData,
    ResourceFile,
    content_ref,
)
from codehood.push.run import fetch_server_state, fetch_students, run_plan
from codehood.push.wire import (
    Payload,
    course_payload,
    event_payload,
    grade_column_payload,
    question_payload,
    resource_payload,
    time_slot_payload,
)

pytestmark = pytest.mark.integration

SERVER_URL = os.environ.get("CODEHOOD_SERVER", "http://localhost:4321")
KEY = CourseKey("cs101", "ada", "2026-1")
DISCIPLINE, COURSE = KEY.discipline, KEY.slug

#: A slot far from the ones the seed data uses, so it overlaps none.
SLOT = TimeSlot("proj-slot", "SUNDAY", TimeOfDay(3, 0), Duration(0, 90), "Project slot")
EVENT = Event(week=90, time_slot=SLOT.slug, title="Project event", description="")

QUESTION = """---
title: Round trip
---

What is 2 + 2?

- [ ] 3
- [*] 4
- [ ] 5
"""


@pytest.fixture(scope="module")
def client() -> Iterator[httpx.Client]:
    live = httpx.Client(base_url=SERVER_URL, timeout=10.0)
    try:
        live.get("/openapi.json")
    except httpx.TransportError as exc:
        pytest.skip(f"no Codehood server reachable at {SERVER_URL} ({exc})")
    yield live
    live.close()


@pytest.fixture(autouse=True)
def _logged_in(client: httpx.Client) -> None:
    result = generated.login(
        body=generated.LoginRequest(login="ada", password="ada"), client=client
    )
    base_module.save_token(SERVER_URL, result.token)


def _run(client: httpx.Client, *ops: Write) -> None:
    results = list(run_plan(ops, discipline=DISCIPLINE, course=COURSE, client=client))
    failed = [result.message for result in results if not result.ok]
    assert not failed, failed


def _entry(client: httpx.Client, kind: str, key: object) -> RemoteEntry:
    state = fetch_server_state(DISCIPLINE, COURSE, client)
    entry = getattr(state, kind)[key]
    return entry if isinstance(entry, RemoteEntry) else entry.entry


@pytest.fixture
def slot(client: httpx.Client) -> Iterator[TimeSlot]:
    _run(client, UpsertTimeSlot(slot=SLOT))
    yield SLOT
    _run(client, DeleteTimeSlot(slug=SLOT.slug))


def test_course_round_trips(client: httpx.Client) -> None:
    before = generated.read_course(discipline=DISCIPLINE, course=COURSE, client=client)
    start = date.fromisoformat(before.start_at[:10])
    end = date.fromisoformat(before.end_at[:10])
    payload = course_payload(KEY, "Round trip description.", start, end)
    ref = course_ref("Round trip description.", payload["startAt"], payload["endAt"])  # type: ignore[arg-type]
    try:
        _run(
            client,
            UpsertCourse(
                key=KEY,
                description="Round trip description.",
                start_at=str(payload["startAt"]),
                end_at=str(payload["endAt"]),
                ref=ref,
            ),
        )
        state = fetch_server_state(DISCIPLINE, COURSE, client)
        assert state.course is not None
        assert state.course.payload == payload
        assert state.course.rev == ref
    finally:
        _run(
            client,
            UpsertCourse(
                key=KEY,
                description=before.description or "",
                start_at=before.start_at,
                end_at=before.end_at,
                ref=before.rev or "",
            ),
        )


def test_time_slot_round_trips_a_duration_the_server_carries(
    client: httpx.Client, slot: TimeSlot
) -> None:
    entry = _entry(client, "time_slots", slot.slug)
    assert entry.payload == time_slot_payload(slot)
    assert entry.payload["duration"] == {"hours": 1, "minutes": 30}
    assert entry.rev is None


def test_calendar_event_round_trips(client: httpx.Client, slot: TimeSlot) -> None:
    _run(client, UpsertCalendarEvent(event=EVENT))
    try:
        entry = _entry(client, "calendar_events", (EVENT.week, EVENT.time_slot))
        assert entry.payload == event_payload(EVENT)
        assert entry.rev == EVENT.ref
    finally:
        _run(client, DeleteCalendarEvent(week=EVENT.week, time_slot=EVENT.time_slot))


@pytest.mark.parametrize(
    "data",
    [
        MdData("# Title\n\nBody.\n"),
        CodeData("print('x')\n", "python"),
        LinkData("https://example.org/page"),
        FileData("proj-file.bin", b"round trip bytes"),
    ],
    ids=["md", "code", "link", "file"],
)
@pytest.mark.parametrize("attached", [False, True], ids=["general", "attached"])
def test_resource_round_trips(
    client: httpx.Client, slot: TimeSlot, data: ResourceData, attached: bool
) -> None:
    _run(client, UpsertCalendarEvent(event=EVENT))
    event = EventKey(EVENT.week, EVENT.time_slot) if attached else None
    file = ResourceFile(
        slug="proj-resource",
        title="Round trip",
        description="About it.",
        data=data,
        ref=content_ref("Round trip", "About it.", data, event),
        path=Path("resources/proj-resource"),
        event=event,
    )
    try:
        _run(
            client,
            UpsertResource(
                slug=file.slug,
                title=file.title,
                description=file.description,
                data=file.data,
                ref=file.ref,
                path=file.path,
                event=file.event,
            ),
        )
        entry = _entry(client, "resources", file.slug)
        assert entry.payload == resource_payload(file)
        assert entry.rev == file.ref
    finally:
        _run(
            client,
            DeleteResource(slug=file.slug),
            DeleteCalendarEvent(week=EVENT.week, time_slot=EVENT.time_slot),
        )


def test_grade_column_round_trips_what_the_server_trims(client: httpx.Client) -> None:
    students = fetch_students(DISCIPLINE, COURSE, client)
    values = tuple((student.username, 7.5) for student in students[:2])
    column = GradeColumn("proj-column", "  Round trip  ", "number", 99, values)
    try:
        _run(client, UpsertGradeColumn(column=column))
        entry = _entry(client, "grade_columns", column.slug)
        assert entry.payload == grade_column_payload(column)
        assert entry.payload["title"] == "Round trip"
    finally:
        _run(client, DeleteGradeColumn(slug=column.slug))


def test_question_round_trips_normalized(client: httpx.Client) -> None:
    parsed = mdq.parse(QUESTION, kind="question", ids="fill")
    file = QuestionFile(
        slug="proj-question",
        version=question_version(QUESTION.encode()),
        question=parsed,
        path=Path("questions/proj-question.md"),
    )
    try:
        _run(
            client,
            UpsertQuestion(
                slug=file.slug,
                version=file.version,
                question=file.question,
                path=file.path,
                status="DRAFT",
            ),
        )
        entry = _entry(client, "questions", file.slug)
        expected: Payload = question_payload(file)
        assert entry.payload == expected
    finally:
        _run(client, DeleteQuestion(slug=file.slug))
