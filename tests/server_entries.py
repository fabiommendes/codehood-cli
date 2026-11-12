"""
Test helper: turn the placeholder entries a test declares for the server
(an empty payload and the `rev` or version it wants) into entries holding the
real payload, built from the local state with the `wire` constructors.

A placeholder whose `rev` equals what the local entity hashes to holds the
local payload, so the server agrees with the repository; any other `rev`
holds a payload that differs from it.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from codehood.push.calendar import Event
from codehood.push.grades import GradeColumn
from codehood.push.plan import LocalState, ServerEvent, ServerQuestion, ServerState
from codehood.push.project import RemoteEntry
from codehood.push.question import QuestionFile
from codehood.push.resource import MdData, ResourceFile, content_ref
from codehood.push.wire import (
    Payload,
    course_payload,
    event_payload,
    grade_column_payload,
    question_payload,
    resource_payload,
)

__all__ = ["placeholder", "realize"]


def placeholder(rev: str | None) -> RemoteEntry:
    """
    A server entry that only says which `rev` it carries.
    """
    return RemoteEntry({}, rev=rev)


def _pending(entry: RemoteEntry) -> bool:
    return not entry.payload or entry.payload == {"event": None}


def _entry(entry: RemoteEntry, payload: Payload) -> RemoteEntry:
    return replace(entry, payload=payload)


def _resource(slug: str, entry: RemoteEntry, file: ResourceFile | None) -> RemoteEntry:
    if file is not None and file.ref == entry.rev:
        return _entry(entry, resource_payload(file))
    data = MdData(content=f"server {entry.rev}")
    title = f"server {entry.rev}"
    stand_in = ResourceFile(
        slug=slug,
        title=title,
        description=None,
        data=data,
        ref=content_ref(title, None, data),
        path=Path(f"resources/{slug}.md"),
        event=file.event if file is not None else None,
    )
    return _entry(entry, resource_payload(stand_in))


def _question(
    slug: str, question: ServerQuestion, file: QuestionFile | None
) -> ServerQuestion:
    entry = question.entry
    if not _pending(entry):
        return question
    if file is not None and file.version == question.version:
        return replace(question, entry=_entry(entry, question_payload(file)))
    payload: Payload = (
        {**question_payload(file), "version": question.version}
        if file is not None
        else {"slug": slug, "version": question.version}
    )
    return replace(question, entry=_entry(entry, payload))


def _event(key: tuple[int, str], server: ServerEvent, local: Event | None):
    if not _pending(server.entry):
        return server
    if local is not None and local.ref == server.ref:
        event = replace(local, kind=server.kind)
    else:
        event = Event(key[0], key[1], title=f"server {server.ref}", kind=server.kind)
    return replace(server, entry=_entry(server.entry, event_payload(event)))


def _column(slug: str, entry: RemoteEntry, column: GradeColumn | None) -> RemoteEntry:
    if column is not None and column.rev == entry.rev:
        return _entry(entry, grade_column_payload(column))
    stand_in = GradeColumn(slug, f"server {entry.rev}", "number", 0, ())
    return _entry(entry, grade_column_payload(stand_in))


def realize(local: LocalState, server: ServerState) -> ServerState:
    """
    `server` with every placeholder entry given the payload it implies.
    """
    from codehood.push.plan import course_ref
    from codehood.push.wire import instant

    files = {f.slug: f for f in local.resources}
    questions = {q.slug: q for q in local.questions if isinstance(q, QuestionFile)}
    events = {(e.week, e.time_slot): e for e in local.events}
    columns = {c.slug: c for c in local.grade_columns or ()}
    course = server.course
    if course is not None and _pending(course):
        ref = course_ref(local.description, instant(local.start), instant(local.end))
        description = local.description if course.rev == ref else "server copy"
        course = _entry(
            course, course_payload(local.key, description, local.start, local.end)
        )
    return replace(
        server,
        course=course,
        resources={
            k: _resource(k, v, files.get(k)) if _pending(v) else v
            for k, v in server.resources.items()
        },
        questions={
            k: _question(k, v, questions.get(k)) for k, v in server.questions.items()
        },
        calendar_events={
            k: _event(k, v, events.get(k)) for k, v in server.calendar_events.items()
        },
        grade_columns={
            k: _column(k, v, columns.get(k)) if _pending(v) else v
            for k, v in server.grade_columns.items()
        },
    )
