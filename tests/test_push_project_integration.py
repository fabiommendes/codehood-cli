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
from codehood.push.calendar import (
    Duration,
    Event,
    EventKey,
    EventKind,
    TimeOfDay,
    TimeSlot,
)
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
from codehood.push.project import RemoteEntry, project_question
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
    canonical_question,
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
def _logged_in(
    client: httpx.Client, tmp_path_factory: pytest.TempPathFactory, monkeypatch
) -> None:
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)
    result = generated.login(
        body=generated.LoginRequest(login="ada", password="ada"), client=client
    )
    # The login sets a session cookie; the server rejects it next to the Bearer.
    client.cookies.clear()
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
                ref=before.rev or "restored",
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


def _raw(client: httpx.Client, path: str) -> object:
    token = base_module.load_token(SERVER_URL)
    response = client.get(path, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response.json()


def test_course_with_an_empty_description_comes_back_empty(
    client: httpx.Client,
) -> None:
    before = generated.read_course(discipline=DISCIPLINE, course=COURSE, client=client)
    start = date.fromisoformat(before.start_at[:10])
    end = date.fromisoformat(before.end_at[:10])
    payload = course_payload(KEY, "", start, end)
    try:
        _run(
            client,
            UpsertCourse(
                key=KEY,
                description="",
                start_at=str(payload["startAt"]),
                end_at=str(payload["endAt"]),
                ref=course_ref("", payload["startAt"], payload["endAt"]),  # type: ignore[arg-type]
            ),
        )
        state = fetch_server_state(DISCIPLINE, COURSE, client)
        assert state.course is not None
        assert state.course.payload == payload
        raw = _raw(client, f"/api/course/{DISCIPLINE}/{COURSE}/")
        assert raw["description"] in ("", None)  # type: ignore[index]
    finally:
        _run(
            client,
            UpsertCourse(
                key=KEY,
                description=before.description or "",
                start_at=before.start_at,
                end_at=before.end_at,
                ref=before.rev or "restored",
            ),
        )


def test_event_with_an_empty_description_and_a_padded_title(
    client: httpx.Client, slot: TimeSlot
) -> None:
    event = Event(
        week=91, time_slot=slot.slug, title="  Padded  title ", description=""
    )
    _run(client, UpsertCalendarEvent(event=event))
    try:
        entry = _entry(client, "calendar_events", (event.week, event.time_slot))
        assert entry.payload["description"] == ""
        assert entry.payload == event_payload(event)
    finally:
        _run(client, DeleteCalendarEvent(week=event.week, time_slot=event.time_slot))


def test_resource_with_an_empty_description_and_a_padded_title(
    client: httpx.Client,
) -> None:
    data = MdData("# Empty\n")
    file = ResourceFile(
        slug="proj-empty",
        title="  Padded  title ",
        description="",
        data=data,
        ref=content_ref("  Padded  title ", "", data, None),
        path=Path("resources/proj-empty.md"),
        event=None,
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
                event=None,
            ),
        )
        entry = _entry(client, "resources", file.slug)
        assert entry.payload["description"] == ""
        assert entry.payload == resource_payload(file)
    finally:
        _run(client, DeleteResource(slug=file.slug))


@pytest.mark.parametrize(
    "data",
    [CodeData("print('x')\n", "python"), LinkData("https://example.org/empty")],
    ids=["code", "link"],
)
def test_code_and_link_resources_with_an_empty_description(
    client: httpx.Client, data: ResourceData
) -> None:
    file = ResourceFile(
        slug="proj-empty-desc",
        title="Empty description",
        description="",
        data=data,
        ref=content_ref("Empty description", "", data, None),
        path=Path("resources/proj-empty-desc"),
        event=None,
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
                event=None,
            ),
        )
        entry = _entry(client, "resources", file.slug)
        assert entry.payload["description"] == ""
        assert entry.payload == resource_payload(file)
    finally:
        _run(client, DeleteResource(slug=file.slug))


@pytest.mark.parametrize("kind", ["HOLIDAY", "CANCELLED"])
def test_event_kinds_round_trip(
    client: httpx.Client, slot: TimeSlot, kind: EventKind
) -> None:
    event = Event(week=92, time_slot=slot.slug, title="Not a class", kind=kind)
    _run(client, UpsertCalendarEvent(event=event))
    try:
        entry = _entry(client, "calendar_events", (event.week, event.time_slot))
        assert entry.payload["kind"] == kind
        assert entry.payload == event_payload(event)
    finally:
        _run(client, DeleteCalendarEvent(week=event.week, time_slot=event.time_slot))


def test_time_slot_title_with_padding_round_trips(client: httpx.Client) -> None:
    slot = TimeSlot(
        "proj-pad", "SUNDAY", TimeOfDay(4, 0), Duration(0, 90), " Pad  ded "
    )
    _run(client, UpsertTimeSlot(slot=slot))
    try:
        assert _entry(client, "time_slots", slot.slug).payload == time_slot_payload(
            slot
        )
    finally:
        _run(client, DeleteTimeSlot(slug=slot.slug))


def test_file_hash_is_the_one_in_the_link(client: httpx.Client) -> None:
    data = FileData("proj-hash.bin", b"hash me")
    file = ResourceFile(
        slug="proj-hash",
        title="Hash",
        description="",
        data=data,
        ref=content_ref("Hash", "", data, None),
        path=Path("resources/proj-hash.bin"),
        event=None,
    )
    try:
        _run(
            client,
            UpsertResource(
                slug=file.slug,
                title=file.title,
                description="",
                data=data,
                ref=file.ref,
                path=file.path,
                event=None,
            ),
        )
        entry = _entry(client, "resources", file.slug)
        assert entry.payload["data"]["hash"] == data.sha256  # type: ignore[index]
    finally:
        _run(client, DeleteResource(slug=file.slug))


def test_question_option_ids_match_the_ones_python_derives(
    client: httpx.Client,
) -> None:
    text = QUESTION.replace("Round trip", "Ids")
    parsed = mdq.parse(text, kind="question", ids="fill")
    file = QuestionFile(
        slug="proj-ids",
        version=question_version(text.encode()),
        question=parsed,
        path=Path("questions/proj-ids.md"),
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
        items = _raw(client, f"/api/course/{DISCIPLINE}/{COURSE}/question/")
        item = next(i for i in items if i["slug"] == file.slug)  # type: ignore[union-attr]
        sent = canonical_question(parsed)
        assert project_question(item)["question"] == sent
        sent_ids = [o["id"] for o in sent["choices"]]  # type: ignore[index]
        got_ids = [o["id"] for o in item["question"]["choices"]]
        assert got_ids == sent_ids
    finally:
        _run(client, DeleteQuestion(slug=file.slug))
