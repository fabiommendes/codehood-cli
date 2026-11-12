"""
Translates the local forms a push writes into the JSON the server accepts.

Every `*_payload` function returns the body of the entity's `PUT`, so the
payload of a local entity and the payload a read model projects to (see
`project.py`) are the same dict, and comparing them is comparing dicts.
Where the server rewrites a value on the way in (a time slot's duration is
carried into hours, a grade column's strings are trimmed), the payload holds
the rewritten value: a payload the server hands back unchanged is the only
kind that can be compared.

`rev` is left out of every payload. It is a digest of the payload, stored and
compared on its own.
"""

from __future__ import annotations

from datetime import date

import mdq
from pydantic import JsonValue

from ..models.repo import CourseKey
from .calendar import Event, TimeSlot
from .grades import GradeColumn
from .question import QuestionFile
from .resource import CodeData, FileData, LinkData, MdData, ResourceFile

__all__ = [
    "Payload",
    "canonical_question",
    "course_payload",
    "event_payload",
    "grade_column_payload",
    "instant",
    "question_payload",
    "resource_payload",
    "time_slot_payload",
    "wire_question",
]

#: The JSON body a push sends for one entity, without its `rev`.
type Payload = dict[str, JsonValue]

#: Lists the mdq schema requires to be absent or non-empty.
_NON_EMPTY_LISTS = ("extra", "accept", "reject")


def wire_question(question: mdq.Question) -> dict[str, JsonValue]:
    """
    Return `question` as the plain mapping the server's `question` union takes.

    Omitted optional fields stay omitted: the server rejects an explicit
    `null`, and an empty `extra`, `accept` or `reject` list, which `mdq`
    models default to but the mdq schema requires to have items.
    """
    payload = question.model_dump(mode="json", by_alias=True, exclude_none=True)
    for key in _NON_EMPTY_LISTS:
        if payload.get(key) == []:
            del payload[key]
    return payload


def canonical_question(question: mdq.Question) -> dict[str, JsonValue]:
    """
    Return `question` in the form two equal questions share: ids filled in
    and fields normalized by `mdq`, then as `wire_question` takes it.
    """
    return wire_question(question.with_ids().normalize())


def instant(day: date) -> str:
    """
    A date as the UTC midnight timestamp the server's `startAt`/`endAt`
    take, spelled the way the server spells it back.
    """
    return f"{day.isoformat()}T00:00:00.000Z"


def course_payload(key: CourseKey, description: str, start: date, end: date) -> Payload:
    """
    The body of the course's `PUT`.
    """
    return {
        "discipline": key.discipline,
        "instructor": key.instructor,
        "edition": key.edition,
        "description": description,
        "startAt": instant(start),
        "endAt": instant(end),
    }


def resource_payload(file: ResourceFile) -> Payload:
    """
    The body of a resource's `PUT`.

    A `FILE` carries the sha-256 of its bytes, not the bytes, which travel in
    a multipart part named by that hash.
    """
    data: dict[str, JsonValue]
    match file.data:
        case MdData(content=content):
            data = {"type": "MD", "content": content}
        case CodeData(content=content, language=language):
            data = {"type": "CODE", "content": content, "language": language}
        case FileData(filename=filename) as upload:
            data = {"type": "FILE", "filename": filename, "hash": upload.sha256}
        case LinkData(url=url):
            data = {"type": "LINK", "url": url}
    return {
        "slug": file.slug,
        "title": file.title,
        "description": file.description,
        "event": (
            {"week": file.event.week, "timeSlot": file.event.time_slot}
            if file.event is not None
            else None
        ),
        "data": data,
    }


def question_payload(file: QuestionFile) -> Payload:
    """
    The canonical form of a question: its slug and its document.

    `status` and `version` are left out: the status follows `join_status`,
    and the version digests the file's bytes rather than its content.
    """
    return {"slug": file.slug, "question": canonical_question(file.question)}


def time_slot_payload(slot: TimeSlot) -> Payload:
    """
    The body of a time slot's `PUT`, with the duration carried into hours
    the way the server stores and reads it back.
    """
    minutes = slot.duration.hours * 60 + slot.duration.minutes
    return {
        "slug": slot.slug,
        "title": slot.title,
        "day": slot.day,
        "start": {"hour": slot.start.hour, "minute": slot.start.minute},
        "duration": {"hours": minutes // 60, "minutes": minutes % 60},
    }


def event_payload(event: Event) -> Payload:
    """
    The body of a calendar event's `PUT`, with the repositories sorted by
    slug, the order the server lists them in.
    """
    repositories: list[JsonValue] = sorted(event.repositories)
    return {
        "kind": event.kind,
        "title": event.title,
        "description": event.description,
        "week": event.week,
        "timeSlot": event.time_slot,
        "repositories": repositories,
    }


def grade_column_payload(column: GradeColumn) -> Payload:
    """
    The body of a grade column's `PUT`, with the strings trimmed and the
    values ordered by username, as the server stores and lists them.
    """
    values: list[JsonValue] = [
        {
            "username": username,
            "value": value.strip() if isinstance(value, str) else value,
        }
        for username, value in sorted(column.values, key=lambda item: item[0])
    ]
    return {
        "slug": column.slug,
        "title": column.title.strip(),
        "kind": column.kind.upper(),
        "position": column.position,
        "values": values,
    }
