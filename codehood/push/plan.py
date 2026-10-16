"""
The pure core of `codehood push`: a generator that diffs a repository
against the server's current state and yields a plan.

No client, no ids, no `run()` -- see `dev/specs/to-do/push.md`,
"Architecture". `run.py` is the only thing in `codehood/push/` that
executes a `PushOp`.

The two inputs are whole values, `LocalState` and `ServerState`, rather
than a dozen loose mappings: `slug -> ref` and `slug -> version` are the
same type and mean different things, and naming them as fields is what
stops a caller from swapping them silently.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from .calendar import Event, EventKey, TimeSlot
from .exclude import ExcludedFile
from .grades import GradeColumn
from .question import AnyQuestion, QuestionFile
from .resource import ResourceData, ResourceFile

__all__ = [
    "DeleteCalendarEvent",
    "DeleteGradeColumn",
    "DeleteQuestion",
    "DeleteResource",
    "DeleteRollCall",
    "DeleteTimeSlot",
    "LocalState",
    "PushOp",
    "ServerEvent",
    "ServerState",
    "UpsertCalendarEvent",
    "UpsertCourse",
    "UpsertGradeColumn",
    "UpsertQuestion",
    "UpsertResource",
    "UpsertTimeSlot",
    "WarnEventHasRollCall",
    "WarnTimeSlotPinned",
    "plan_push",
]


#
# Inputs
#
@dataclass(frozen=True)
class LocalState:
    """
    Everything a repository holds that a push can write.

    `start` and `end` come from `calendar.md`, not from the edition: the
    edition is an institutional term shared across courses, and a course's
    own span is the instructor's to set -- see the mapping's "Course".

    `grade_columns` is `None` when the columns could not be computed, which
    leaves the server's columns alone. An empty tuple is a course that
    declares none, and prunes whatever the server holds.
    """

    discipline: str
    course: str
    description: str
    start: date
    end: date
    slots: tuple[TimeSlot, ...] = ()
    events: tuple[Event, ...] = ()
    resources: tuple[ResourceFile, ...] = ()
    questions: tuple[QuestionFile, ...] = ()
    grade_columns: tuple[GradeColumn, ...] | None = ()
    #: Files left out by `[push] exclude`: never written, never pruned.
    excluded: tuple[ExcludedFile, ...] = ()


@dataclass(frozen=True)
class ServerEvent:
    """
    What the sync preflight reports about one calendar event.

    A marker, not a payload: `ref` decides whether to rewrite it and
    `kind` whether to touch it at all -- see the mapping's "Sync
    preflight".
    """

    ref: str
    kind: Literal["REGULAR", "HOLIDAY", "CANCELLED"]
    attendances: int | None = None


@dataclass(frozen=True)
class ServerState:
    """
    What the server currently holds for a course, as markers only.
    """

    course_exists: bool = False
    resources: Mapping[str, str] = field(default_factory=dict)
    resource_events: Mapping[str, EventKey | None] = field(default_factory=dict)
    questions: Mapping[str, str] = field(default_factory=dict)
    time_slots: Mapping[str, str] = field(default_factory=dict)
    calendar_events: Mapping[tuple[int, str], ServerEvent] = field(default_factory=dict)
    grade_columns: Mapping[str, str] = field(default_factory=dict)


#
# Operations
#
@dataclass(frozen=True)
class UpsertCourse:
    """
    The course row to `PUT`, keyed by `(discipline, course)`.
    """

    discipline: str
    course: str
    description: str
    start_at: str | None
    end_at: str | None


@dataclass(frozen=True)
class UpsertResource:
    """
    One resource to `PUT`, whole, whatever its type.

    `data` is the same tagged union the server stores, so the shell has
    nothing left to infer -- see `push.md`, "Architecture". `ref` is the
    digest the server hands back on the next read, which is what makes a
    second push of an unchanged resource a no-op.
    """

    slug: str
    title: str
    description: str | None
    data: ResourceData
    ref: str
    path: Path
    event: EventKey | None = None


@dataclass(frozen=True)
class DeleteResource:
    """
    A resource to delete by slug: its local file is gone.
    """

    slug: str


@dataclass(frozen=True)
class UpsertQuestion:
    """
    One question to `PUT`, parsed but untranslated.

    `question` is the same `mdq` union `question.scan_questions` yields;
    `run.py` is the only place that turns it into the generated request
    model, dropping the fields the server's schema rejects.
    """

    slug: str
    version: str
    question: AnyQuestion
    path: Path


@dataclass(frozen=True)
class DeleteQuestion:
    """
    A question to delete by slug: its local file is gone.
    """

    slug: str


@dataclass(frozen=True)
class UpsertTimeSlot:
    """
    One time slot to `PUT`, carried whole.
    """

    slot: TimeSlot


@dataclass(frozen=True)
class DeleteTimeSlot:
    """
    A time slot to hard-delete by slug: its `days:` entry is gone.
    """

    slug: str


@dataclass(frozen=True)
class UpsertCalendarEvent:
    """
    One calendar event to `PUT`, carried whole.
    """

    event: Event


@dataclass(frozen=True)
class DeleteCalendarEvent:
    """
    A calendar event to hard-delete, by the `(week, timeSlot)` pair that
    is both its primary key and its URL.
    """

    week: int
    time_slot: str


@dataclass(frozen=True)
class WarnTimeSlotPinned:
    """
    Not a write: a time slot the preflight would otherwise prune, kept
    because a `CANCELLED` calendar event still pins it.

    The cancelled event is never rewritten or pruned (see the mapping's
    "Calendar events"), so it pins the slot indefinitely, and the server
    refuses to orphan it -- see "Deletion and pruning". `plan_calendar` is
    a pure generator with no other channel to explain why a slug it would
    otherwise delete survives, so this rides `PushOp` itself: `run.py`
    executes it as a no-op and the CLI prints it like any other planned
    line.
    """

    slug: str
    week: int


@dataclass(frozen=True)
class WarnEventHasRollCall:
    """
    A calendar event kept, though gone locally, because it has a roll call.

    Reported even when the roll call holds no attendance.
    """

    week: int
    time_slot: str
    attendances: int


@dataclass(frozen=True)
class DeleteRollCall:
    """
    A roll call to delete, by the `(week, timeSlot)` of its event.
    """

    week: int
    time_slot: str


@dataclass(frozen=True)
class UpsertGradeColumn:
    """
    One grade column to `PUT`, whole: the server replaces its values with
    the ones carried here.
    """

    column: GradeColumn


@dataclass(frozen=True)
class DeleteGradeColumn:
    """
    A grade column to delete by slug: `codehood.toml` no longer declares it.
    """

    slug: str


PushOp = (
    UpsertCourse
    | UpsertResource
    | DeleteResource
    | UpsertQuestion
    | DeleteQuestion
    | UpsertTimeSlot
    | DeleteTimeSlot
    | UpsertCalendarEvent
    | DeleteCalendarEvent
    | WarnTimeSlotPinned
    | WarnEventHasRollCall
    | DeleteRollCall
    | UpsertGradeColumn
    | DeleteGradeColumn
)


def plan_push(
    local: LocalState, server: ServerState, *, drop_roll_calls: bool = False
) -> Iterator[PushOp]:
    """
    Diff a repository against the server's current state and yield a plan.

    The course row is always `PUT`, since every write is idempotent and
    the course carries no comparable hash of its own -- see `push.md`,
    "Every write is a `PUT`". `server.course_exists` mirrors what the
    shell already fetched (`fetch_server_state`) so a future check has
    somewhere to plug in; it does not gate this call, on purpose.

    A resource is planned when its `ref` differs from (or is absent from)
    `server.resources`; a server slug absent locally is planned for
    deletion, unless an `exclude` pattern leaves its local file out.
    Questions follow the same rule on `version`.

    Calendar slots and events come right after the course, in that
    order: a slot an event needs has to exist before the event is
    written, and a resource attached to an event needs the event to exist
    first. Resources, questions and grade columns follow.
    """
    yield UpsertCourse(
        discipline=local.discipline,
        course=local.course,
        description=local.description,
        start_at=_timestamp(local.start),
        end_at=_timestamp(local.end),
    )

    yield from plan_calendar(local, server, drop_roll_calls=drop_roll_calls)

    seen_slugs: set[str] = set()
    for resource in local.resources:
        seen_slugs.add(resource.slug)
        if (
            server.resources.get(resource.slug) == resource.ref
            and server.resource_events.get(resource.slug) == resource.event
        ):
            continue
        yield UpsertResource(
            slug=resource.slug,
            title=resource.title,
            description=resource.description,
            data=resource.data,
            ref=resource.ref,
            path=resource.path,
            event=resource.event,
        )

    excluded = {(file.kind, file.slug) for file in local.excluded}

    for slug in server.resources:
        if slug not in seen_slugs and ("resource", slug) not in excluded:
            yield DeleteResource(slug=slug)

    seen_question_slugs: set[str] = set()
    for question in local.questions:
        seen_question_slugs.add(question.slug)
        if server.questions.get(question.slug) == question.version:
            continue
        yield UpsertQuestion(
            slug=question.slug,
            version=question.version,
            question=question.question,
            path=question.path,
        )

    for slug in server.questions:
        if slug not in seen_question_slugs and ("question", slug) not in excluded:
            yield DeleteQuestion(slug=slug)

    yield from plan_grades(local, server)


def plan_calendar(
    local: LocalState, server: ServerState, *, drop_roll_calls: bool = False
) -> Iterator[PushOp]:
    """
    The calendar half of a plan: delete events, delete slots, upsert
    slots, upsert events, in that exact order.

    A calendar event references its time slot, so a slot cannot be
    deleted while an event still points at it; and two slots may not
    overlap on one weekday, so a slug that changed cannot be created
    while the old slug still holds its hour. This order is the only one
    that satisfies both -- see the mapping's "Deletion and pruning".

    An event the server reports as `CANCELLED` is neither rewritten nor
    pruned -- see the mapping's "Calendar events" -- and that pins its
    time slot: a slot a `CANCELLED` event still points at is left in
    place even when no local `days:` entry accounts for it, with a
    `WarnTimeSlotPinned` naming both.

    An event with a roll call that left the local calendar is kept with a
    `WarnEventHasRollCall`, and pins its slot the same way. With
    `drop_roll_calls` its roll call is deleted first, then the event.
    """
    local_slugs = {slot.slug for slot in local.slots}
    local_events = {(event.week, event.time_slot): event for event in local.events}

    kept_for_roll_call: set[tuple[int, str]] = set()
    for key, server_event in server.calendar_events.items():
        if server_event.kind == "CANCELLED":
            continue
        if key in local_events:
            continue
        week, time_slot = key
        if server_event.attendances is None:
            yield DeleteCalendarEvent(week=week, time_slot=time_slot)
        elif drop_roll_calls:
            yield DeleteRollCall(week=week, time_slot=time_slot)
            yield DeleteCalendarEvent(week=week, time_slot=time_slot)
        else:
            kept_for_roll_call.add(key)
            yield WarnEventHasRollCall(
                week=week, time_slot=time_slot, attendances=server_event.attendances
            )

    pinned_slugs: set[str] = set()
    for week, time_slot in kept_for_roll_call:
        pinned_slugs.add(time_slot)
    for (week, time_slot), server_event in server.calendar_events.items():
        if server_event.kind == "CANCELLED" and time_slot not in local_slugs:
            pinned_slugs.add(time_slot)
            yield WarnTimeSlotPinned(slug=time_slot, week=week)

    for slug in server.time_slots:
        if slug not in local_slugs and slug not in pinned_slugs:
            yield DeleteTimeSlot(slug=slug)

    for slot in local.slots:
        if server.time_slots.get(slot.slug) == slot.ref:
            continue
        yield UpsertTimeSlot(slot=slot)

    for key, event in local_events.items():
        matching_server_event = server.calendar_events.get(key)
        if (
            matching_server_event is not None
            and matching_server_event.kind == "CANCELLED"
        ):
            continue
        if matching_server_event is not None and (
            matching_server_event.ref,
            matching_server_event.kind,
        ) == (event.ref, event.kind):
            continue
        yield UpsertCalendarEvent(event=event)


def plan_grades(local: LocalState, server: ServerState) -> Iterator[PushOp]:
    """
    The grade column half of a plan: upsert what changed, delete what
    `codehood.toml` no longer declares.

    A column is planned when its `rev` differs from, or is absent from,
    `server.grade_columns`. Nothing is planned when `local.grade_columns`
    is `None`: columns that could not be computed are not evidence that
    the server's should go.
    """
    if local.grade_columns is None:
        return

    for column in local.grade_columns:
        if server.grade_columns.get(column.slug) != column.rev:
            yield UpsertGradeColumn(column=column)

    declared = {column.slug for column in local.grade_columns}
    for slug in server.grade_columns:
        if slug not in declared:
            yield DeleteGradeColumn(slug=slug)


#
# Utilities
#
def _timestamp(day: date) -> str:
    """
    A date as the UTC midnight timestamp the server's `startAt`/`endAt`
    expect.
    """
    return f"{day.isoformat()}T00:00:00.000Z"
