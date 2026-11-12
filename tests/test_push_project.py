"""
Tests for `codehood.push.project`: for every payload the server accepts,
projecting what it reads back gives the payload again.

Each property plays the server with a small function that turns what a push
sends into what a read returns -- the rewrites `src/db/services/*.service.ts`
does: a duration carried into hours, strings trimmed, the repositories of an
event listed by slug, a `FILE` read as a link. The same property runs against
the dev server in `test_push_project_integration.py`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import mdq
import mdq.hypothesis
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import JsonValue

from codehood.api import generated
from codehood.models.repo import CourseKey
from codehood.push.calendar import (
    Duration,
    Event,
    EventKey,
    TimeOfDay,
    TimeSlot,
    Weekday,
)
from codehood.push.grades import GradeColumn
from codehood.push.project import (
    Payload,
    RemoteEntry,
    project_calendar_event,
    project_course,
    project_grade_column,
    project_question,
    project_resource,
    project_time_slot,
)
from codehood.push.question import QuestionFile
from codehood.push.resource import (
    CodeData,
    FileData,
    LinkData,
    MdData,
    ResourceData,
    ResourceFile,
)
from codehood.push.wire import (
    course_payload,
    event_payload,
    grade_column_payload,
    instant,
    question_payload,
    resource_payload,
    time_slot_payload,
    wire_question,
)

STAMP = "2026-03-01T12:30:00.123Z"

slugs = st.from_regex(r"[a-z][a-z0-9-]{0,10}", fullmatch=True)
texts = st.text(min_size=1, max_size=30)
days = st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31))
WEEKDAYS: tuple[Weekday, ...] = (
    "SUNDAY",
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
)


def wire(value: object) -> dict[str, JsonValue]:
    """
    `value` after a trip through JSON, which is what the server sees and says.
    """
    loaded = json.loads(json.dumps(value))
    assert isinstance(loaded, dict)
    return loaded


#
# The server's side of each round trip
#
def read_course(payload: Payload) -> generated.Course:
    return generated.Course.model_validate(
        wire(
            {
                "description": payload["description"],
                "discipline": {"slug": payload["discipline"], "name": "Discipline"},
                "edition": {"slug": payload["edition"], "name": "Edition"},
                "instructor": {"username": payload["instructor"], "name": "Name"},
                "enrollmentCount": 0,
                "rev": None,
                "startAt": payload["startAt"],
                "endAt": payload["endAt"],
                "createdAt": STAMP,
                "updatedAt": STAMP,
                "joinedAt": STAMP,
            }
        )
    )


def read_resource(payload: Payload) -> generated.Resource:
    data = payload["data"]
    assert isinstance(data, dict)
    if data["type"] == "FILE":
        data = {
            "type": "FILE",
            "filename": data["filename"],
            "link": f"/files/{data['hash']}/{data['filename']}",
            "mimeType": "application/octet-stream",
        }
    event = payload["event"]
    return generated.Resource.model_validate(
        wire(
            {
                "slug": payload["slug"],
                "title": payload["title"],
                "description": payload["description"],
                "data": data,
                "event": {"id": 7, **event} if isinstance(event, dict) else None,
                "rev": "v1:abc",
                "createdAt": STAMP,
                "updatedAt": STAMP,
            }
        )
    )


def read_time_slot(slot: TimeSlot) -> generated.TimeSlot:
    """
    The server stores minutes, and reads them back carried into hours.
    """
    total = slot.duration.hours * 60 + slot.duration.minutes
    return generated.TimeSlot.model_validate(
        wire(
            {
                "slug": slot.slug,
                "title": slot.title,
                "day": slot.day,
                "start": {"hour": slot.start.hour, "minute": slot.start.minute},
                "duration": {"hours": total // 60, "minutes": total % 60},
                "createdAt": STAMP,
                "updatedAt": STAMP,
            }
        )
    )


def read_event(event: Event, description: str | None) -> generated.CalendarEvent:
    """
    The server embeds the time slot and lists the repositories by slug.
    """
    return generated.CalendarEvent.model_validate(
        wire(
            {
                "kind": event.kind,
                "title": event.title,
                "description": description,
                "week": event.week,
                "startAt": STAMP,
                "timeSlot": {
                    "slug": event.time_slot,
                    "day": "MONDAY",
                    "start": {"hour": 8, "minute": 0},
                    "duration": {"hours": 1, "minutes": 0},
                },
                "rev": None,
                "repositories": [
                    {"slug": slug, "title": f"Title of {slug}"}
                    for slug in sorted(event.repositories)
                ],
                "createdAt": STAMP,
                "updatedAt": STAMP,
            }
        )
    )


def read_grade_column(column: GradeColumn) -> generated.GradeColumn:
    """
    The server trims the title and the label values, and lists values by
    username.
    """
    values = [
        {
            "username": username,
            "value": value.strip() if isinstance(value, str) else value,
        }
        for username, value in column.values
    ]
    return generated.GradeColumn.model_validate(
        wire(
            {
                "slug": column.slug,
                "title": column.title.strip(),
                "kind": column.kind.upper(),
                "position": column.position,
                "releasedAt": None,
                "rev": "abc",
                "values": sorted(values, key=lambda entry: entry["username"]),
                "createdAt": STAMP,
                "updatedAt": STAMP,
            }
        )
    )


#
# What a local repository holds
#
@st.composite
def time_slots(draw) -> TimeSlot:
    return TimeSlot(
        slug=draw(slugs),
        day=draw(st.sampled_from(WEEKDAYS)),
        start=TimeOfDay(draw(st.integers(0, 23)), draw(st.integers(0, 59))),
        duration=Duration(draw(st.integers(0, 5)), draw(st.integers(0, 200))),
        title=draw(st.none() | texts),
    )


@st.composite
def events(draw) -> Event:
    return Event(
        week=draw(st.integers(0, 40)),
        time_slot=draw(slugs),
        title=draw(texts),
        description=draw(st.text(max_size=30)),
        kind=draw(st.sampled_from(("REGULAR", "HOLIDAY"))),
        repositories=tuple(sorted(draw(st.lists(slugs, unique=True, max_size=3)))),
    )


@st.composite
def grade_columns(draw) -> GradeColumn:
    kind = draw(st.sampled_from(("number", "label")))
    value = (
        st.floats(min_value=-1000, max_value=1000, allow_nan=False)
        if kind == "number"
        else texts
    )
    usernames = draw(st.lists(slugs, unique=True, max_size=4))
    return GradeColumn(
        slug=draw(slugs),
        title=draw(texts),
        kind=kind,
        position=draw(st.integers(0, 20)),
        values=tuple((username, draw(value)) for username in sorted(usernames)),
    )


@st.composite
def resources(draw) -> ResourceFile:
    data: ResourceData = draw(
        st.one_of(
            st.builds(MdData, texts),
            st.builds(CodeData, texts, slugs),
            st.builds(LinkData, slugs.map(lambda slug: f"https://example.org/{slug}")),
            st.builds(FileData, texts, st.binary(max_size=20)),
        )
    )
    event = draw(st.none() | st.builds(EventKey, st.integers(0, 40), slugs))
    return ResourceFile(
        slug=draw(slugs),
        title=draw(texts),
        description=draw(st.none() | texts),
        data=data,
        ref="v1:ref",
        path=Path("resources/a"),
        event=event,
    )


@st.composite
def course_keys(draw) -> CourseKey:
    return CourseKey(draw(slugs), draw(slugs), draw(slugs))


#
# The round trips
#
@settings(max_examples=100)
@given(
    key=course_keys(),
    description=st.text(max_size=30),
    start=days,
    end=days,
)
def test_course_round_trips(key, description, start, end):
    payload = course_payload(key, description, start, end)
    assert project_course(read_course(payload)) == payload


@settings(max_examples=100)
@given(file=resources())
def test_resource_round_trips(file):
    payload = resource_payload(file)
    assert project_resource(read_resource(payload)) == payload


@settings(max_examples=100)
@given(slot=time_slots())
def test_time_slot_round_trips_what_the_push_sends(slot):
    assert project_time_slot(read_time_slot(slot)) == time_slot_payload(slot)


@settings(max_examples=100)
@given(event=events())
def test_calendar_event_round_trips(event):
    read = read_event(event, event.description)
    assert project_calendar_event(read) == event_payload(event)


@settings(max_examples=100)
@given(column=grade_columns())
def test_grade_column_round_trips_what_the_push_sends(column):
    assert project_grade_column(read_grade_column(column)) == grade_column_payload(
        column
    )


@settings(max_examples=200, deadline=None)
@given(question=mdq.hypothesis.questions(), slug=slugs)
def test_question_round_trips_normalized(question, slug):
    file = QuestionFile(slug=slug, version="v", question=question, path=Path("q.md"))
    sent = wire(wire_question(question.with_ids()))
    item = {"slug": slug, "question": sent, "status": "PUBLISHED", "version": "v"}
    assert project_question(item) == question_payload(file)


#
# Examples
#
def test_a_file_resource_projects_to_the_hash_in_its_link():
    resource = generated.Resource.model_validate(
        {
            "slug": "slides",
            "title": "Slides",
            "description": None,
            "data": {
                "type": "FILE",
                "filename": "a b.pdf",
                "link": "/files/abc123/a b.pdf",
                "mimeType": "application/pdf",
            },
            "event": None,
            "rev": None,
            "createdAt": STAMP,
            "updatedAt": STAMP,
        }
    )
    assert project_resource(resource)["data"] == {
        "type": "FILE",
        "filename": "a b.pdf",
        "hash": "abc123",
    }


def test_a_file_resource_payload_holds_the_hash_of_its_bytes_not_the_bytes():
    data = FileData(filename="a.bin", blob=b"bytes")
    file = ResourceFile("a", "A", None, data, "ref", Path("a.bin"))
    assert resource_payload(file)["data"] == {
        "type": "FILE",
        "filename": "a.bin",
        "hash": data.sha256,
    }


def test_the_foreign_key_of_a_resource_is_part_of_its_payload():
    file = ResourceFile(
        "a", "A", None, MdData("x"), "ref", Path("a.md"), EventKey(2, "mon")
    )
    assert resource_payload(file)["event"] == {"week": 2, "timeSlot": "mon"}


def test_a_duration_the_server_carries_is_carried_in_the_payload_too():
    slot = TimeSlot("mon", "MONDAY", TimeOfDay(8, 0), Duration(0, 90))
    assert time_slot_payload(slot)["duration"] == {"hours": 1, "minutes": 30}


def test_an_event_without_description_reads_as_an_empty_one():
    event = Event(week=1, time_slot="mon", title="Intro")
    read = read_event(event, None)
    assert project_calendar_event(read) == event_payload(event)


def test_an_instant_is_respelled_in_utc_with_milliseconds():
    start = date(2026, 3, 1)
    key = CourseKey("cs101", "ada", "2026-1")
    payload = course_payload(key, "d", start, start)
    read = read_course({**payload, "startAt": "2026-03-01T00:00:00Z"})
    assert project_course(read)["startAt"] == instant(start)


def test_a_question_document_mdq_cannot_read_stays_as_the_server_holds_it():
    legacy = {"type": "essay", "preamble": "old format"}
    item = {"slug": "q", "question": legacy}
    assert project_question(item) == {"slug": "q", "question": legacy}


def test_a_remote_entry_has_the_payload_and_both_markers():
    entry = RemoteEntry({"slug": "a"}, rev="r", updated_at=STAMP)
    assert (entry.payload, entry.rev, entry.updated_at) == ({"slug": "a"}, "r", STAMP)
    assert RemoteEntry({"slug": "a"}) == RemoteEntry({"slug": "a"}, None, None)
