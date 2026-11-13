"""
Projects what the server returns for an entity back into the payload the CLI
sends for it.

A push compares local, base and server in the space of the payload (see
`wire.py`), so the server side needs the inverse of what the server does on
the way out: `project(GET after PUT p) == p` for every payload `p` the server
accepts. Each projection drops the fields only a read has (`createdAt`, the
embedded `id`s), turns nested objects back into the slugs a write names them
by, and undoes the rewrites of a read (a `FILE`'s link back into its hash, a
question document back into the form `mdq` normalizes to).

Pure: no HTTP, no clock. `run.fetch_server_state` is what feeds it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import mdq
from pydantic import JsonValue, TypeAdapter, ValidationError

from ..api import generated
from .calendar import Duration, EventKey, TimeOfDay, TimeSlot
from .wire import Payload, canonical_question

__all__ = [
    "Payload",
    "RemoteEntry",
    "project_calendar_event",
    "project_course",
    "project_exam",
    "project_grade_column",
    "project_question",
    "project_resource",
    "project_time_slot",
    "resource_event_of",
    "time_slot_of",
]

#: Reads a question document of the server back into an `mdq` model.
_QUESTION: TypeAdapter[mdq.Question] = TypeAdapter(mdq.Question)

#: The path the server gives a `FILE` resource: `/files/<sha-256>/<filename>`.
_FILE_LINK = re.compile(r"^/files/(?P<hash>[^/]+)/")


@dataclass(frozen=True)
class RemoteEntry:
    """
    One entity as the server holds it: its projected payload and the two
    markers that say whether it changed.

    `rev` is `None` for an entity that stores none (a time slot) and
    `updated_at` is the ISO timestamp as the server spelled it.
    """

    payload: Payload
    rev: str | None = None
    updated_at: str | None = None


def project_course(course: generated.Course) -> Payload:
    """
    The payload of the course `PUT`, read from `GET /api/course/...`.
    """
    return {
        "discipline": course.discipline.slug,
        "instructor": course.instructor.username,
        "edition": course.edition.slug,
        "description": course.description or "",
        "startAt": _instant(course.start_at),
        "endAt": _instant(course.end_at),
    }


def project_resource(resource: generated.Resource) -> Payload:
    """
    The payload of a resource `PUT`.

    A `FILE` read has a link, not a hash: the hash is the link's first
    segment. A link that does not have the shape stays whole in `hash`, so it
    never equals a sha-256 and shows up as a difference.
    """
    data: dict[str, JsonValue]
    match resource.data:
        case generated.DataMd(content=content):
            data = {"type": "MD", "content": content}
        case generated.DataCode(content=content, language=language):
            data = {"type": "CODE", "content": content, "language": language}
        case generated.ResourceDataFile(filename=filename, link=link):
            found = _FILE_LINK.match(link)
            data = {
                "type": "FILE",
                "filename": filename,
                "hash": found["hash"] if found else link,
            }
        case generated.DataLink(url=url):
            data = {"type": "LINK", "url": url}
    event = resource.event
    return {
        "slug": resource.slug,
        "title": resource.title,
        "description": resource.description,
        "event": (
            {"week": event.week, "timeSlot": event.time_slot}
            if event is not None
            else None
        ),
        "data": data,
    }


def project_question(item: Mapping[str, JsonValue]) -> Payload:
    """
    The canonical payload of one item of the question listing.

    Takes the item as JSON rather than as a generated model: the models drop
    the fields of a question type they do not declare. A document `mdq`
    cannot read (one stored in an older format) stays as the server holds
    it, so it differs from every local question.
    """
    document = item["question"]
    try:
        question = _QUESTION.validate_python(document)
    except ValidationError:
        return {"slug": item["slug"], "question": document}
    return {"slug": item["slug"], "question": canonical_question(question)}


def project_exam(exam: generated.Exam) -> Payload:
    """
    The payload of an exam `PUT`, without `status` and `rev`.

    `duration` and `scheduledAt` are left out when the server holds none, the
    way a file that declares none leaves them out of its payload. The
    questions come back unpinned: a push never sends a version.
    """
    questions: list[JsonValue] = [
        {"slug": item.slug, "version": None} for item in exam.questions
    ]
    tags: list[JsonValue] = [*sorted(exam.tags)]
    payload: Payload = {
        "slug": exam.slug,
        "type": exam.type,
        "title": exam.title,
        "description": exam.description,
        "preamble": exam.preamble,
        "format": exam.format,
        "tags": tags,
        "allowCodeRun": exam.allow_code_run,
        "questions": questions,
    }
    if exam.duration is not None:
        minutes = (exam.duration.hours or 0) * 60 + (exam.duration.minutes or 0)
        payload["duration"] = {"hours": minutes // 60, "minutes": minutes % 60}
    if exam.scheduled_at is not None:
        payload["scheduledAt"] = _instant(exam.scheduled_at)
    return payload


def project_time_slot(slot: generated.TimeSlot) -> Payload:
    """
    The payload of a time slot `PUT`.
    """
    minutes = (slot.duration.hours or 0) * 60 + (slot.duration.minutes or 0)
    return {
        "slug": slot.slug,
        "title": slot.title,
        "day": slot.day,
        "start": {"hour": slot.start.hour, "minute": slot.start.minute},
        "duration": {"hours": minutes // 60, "minutes": minutes % 60},
    }


def resource_event_of(payload: Payload) -> EventKey | None:
    """
    The lesson a resource payload is attached to, `None` for a general one.

    Raises:
        pydantic.ValidationError: `payload` has an `event` of another shape.
    """
    event = payload["event"]
    if event is None:
        return None
    key = generated.Event.model_validate(event)
    return EventKey(week=key.week, time_slot=key.time_slot)


def time_slot_of(payload: Payload) -> TimeSlot:
    """
    The `TimeSlot` a time slot payload describes.

    Raises:
        pydantic.ValidationError: `payload` is not a time slot payload.
    """
    body = generated.TimeSlotCreate.model_validate(payload)
    return TimeSlot(
        slug=body.slug,
        day=body.day,
        start=TimeOfDay(hour=body.start.hour, minute=body.start.minute),
        duration=Duration(
            hours=body.duration.hours or 0, minutes=body.duration.minutes or 0
        ),
        title=body.title,
    )


def project_calendar_event(event: generated.CalendarEvent) -> Payload:
    """
    The payload of a calendar event `PUT`.

    The repositories are linked by slug, and the time slot is named by its
    slug rather than embedded.
    """
    repositories: list[JsonValue] = [
        slug for slug in sorted(item.slug for item in event.repositories)
    ]
    return {
        "kind": event.kind,
        "title": event.title,
        "description": event.description or "",
        "week": event.week,
        "timeSlot": event.time_slot.slug,
        "repositories": repositories,
    }


def project_grade_column(column: generated.GradeColumn) -> Payload:
    """
    The payload of a grade column `PUT`: `releasedAt` is the server's alone.
    """
    values: list[JsonValue] = [
        {"username": entry.username, "value": entry.value}
        for entry in sorted(column.values, key=lambda entry: entry.username)
    ]
    return {
        "slug": column.slug,
        "title": column.title,
        "kind": column.kind,
        "position": column.position,
        "values": values,
    }


#
# Utilities
#
def _instant(text: str) -> str:
    """
    Respell an ISO timestamp the way `wire.instant` does: UTC, milliseconds,
    a `Z`.
    """
    moment = datetime.fromisoformat(text).astimezone(UTC)
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"
