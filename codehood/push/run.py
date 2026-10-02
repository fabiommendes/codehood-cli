"""
The imperative shell of `codehood push`.

The only thing in `codehood/push/` that touches HTTP: `fetch_server_state`
reads what the server currently holds, so `plan.plan_push` can diff
against it; `run_plan` executes a plan one `PushOp` at a time.

This module is also the single place the core's `ResourceData` is
translated into the generated request models, so a change to the server's
union lands here and nowhere else.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import httpx

from ..api import generated
from ..api.base import CodehoodAPIError
from .calendar import Duration, TimeOfDay, TimeSlot
from .plan import (
    DeleteCalendarEvent,
    DeleteQuestion,
    DeleteResource,
    DeleteTimeSlot,
    PushOp,
    ServerEvent,
    ServerState,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertQuestion,
    UpsertResource,
    UpsertTimeSlot,
    WarnTimeSlotPinned,
)
from .resource import CodeData, FileData, MdData, ResourceData

__all__ = ["OpResult", "fetch_server_state", "run_plan"]

#: The generated request-side members of `Resource.data`. The `FILE` member
#: exists twice in the spec -- the upload shape (`filename` plus `buffer`)
#: and the read-back shape (`link`, `mimeType`, `filename`) -- so the
#: generator qualifies both by the schema that owns them:
#: `ResourceCreateDataFile` is the one a push sends.
type RequestData = (
    generated.DataMd | generated.DataCode | generated.ResourceCreateDataFile
)

#: Fields `mdq`'s models carry that the server's `additionalProperties:
#: false` question schema rejects -- see `dev/specs/to-do/push-questions.md`,
#: "`weight` and `grading` are dropped on the wire". A server gap, not a CLI
#: preference; recorded in `ROADBLOCKS.md`.
DROPPED_QUESTION_KEYS = ("weight", "grading")


@dataclass(frozen=True)
class OpResult:
    """
    The outcome of executing one `PushOp`.
    """

    op: PushOp
    ok: bool
    message: str


def fetch_server_state(
    discipline: str, course: str, client: httpx.Client
) -> ServerState:
    """
    Read what the server currently holds for a course.

    The mapping's `cli.course.preSync` RPC does not exist on the server
    (see `ROADBLOCKS.md`), so this reads the list endpoints instead and
    projects each one down to the markers `plan_push` compares: `GET
    /api/course/{discipline}/{course}` to check the course exists,
    `.../resource` to `slug -> ref`, `.../question` to `slug -> version`,
    `.../time-slot` to `slug -> ref`, and `.../calendar-event` to
    `(week, timeSlot) -> ServerEvent`.

    A time slot carries no `ref` column server-side, so its ref is
    recomputed here from the fields the listing did return -- which is
    what lets a slot the CLI never wrote still compare equal.

    Returns:
        A course that does not exist yet reports nothing at all,
        regardless of what those listings themselves would say.
    """
    try:
        generated.read_course(discipline=discipline, course=course, client=client)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return ServerState(course_exists=False)

    resources = generated.list_resource(
        discipline=discipline, course=course, client=client
    )
    # `deleteQuestion` archives rather than removes a row -- see
    # `ROADBLOCKS.md` -- so an archived question would otherwise look
    # "current" forever and get re-planned for deletion on every push.
    # Filtering to the statuses a repository can still produce keeps a
    # deleted question gone for good, which is what `plan_push`'s
    # convergence (a second push plans nothing) requires.
    questions = generated.list_question(
        discipline=discipline,
        course=course,
        statuses=["DRAFT", "PUBLISHED"],
        client=client,
    )
    time_slots = generated.list_timeslot(
        discipline=discipline, course=course, client=client
    )
    calendar_events = generated.list_calendar_event(
        discipline=discipline, course=course, client=client
    )
    return ServerState(
        course_exists=True,
        resources={resource.slug: resource.rev or "" for resource in resources},
        questions={question.slug: question.version for question in questions},
        time_slots={slot.slug: _time_slot_ref(slot) for slot in time_slots},
        calendar_events={
            (event.week, event.time_slot.slug): _server_event(event)
            for event in calendar_events
        },
    )


def run_plan(
    ops: Iterable[PushOp], *, discipline: str, course: str, client: httpx.Client
) -> Iterator[OpResult]:
    """
    Execute a plan, yielding one result per operation.

    A failure executing any operation, including the course row's own
    `PUT`, is caught and reported as a failed `OpResult`; the remaining
    operations still run -- see `push.md`, "FR-SYNC-005", "a sync is not
    atomic", and the CLI surface's "a failure does not stop the push".
    A missing discipline or edition therefore surfaces as one failed
    `OpResult` for the `UpsertCourse` op, not a raise.
    """
    for op in ops:
        yield _run_op(op, discipline=discipline, course=course, client=client)


#
# Utilities
#
def _run_op(
    op: PushOp, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    match op:
        case UpsertCourse():
            return _run_upsert_course(op, client=client)
        case UpsertResource():
            return _run_upsert_resource(
                op, discipline=discipline, course=course, client=client
            )
        case DeleteResource():
            return _run_delete_resource(
                op, discipline=discipline, course=course, client=client
            )
        case UpsertQuestion():
            return _run_upsert_question(
                op, discipline=discipline, course=course, client=client
            )
        case DeleteQuestion():
            return _run_delete_question(
                op, discipline=discipline, course=course, client=client
            )
        case UpsertTimeSlot():
            return _run_upsert_time_slot(
                op, discipline=discipline, course=course, client=client
            )
        case DeleteTimeSlot():
            return _run_delete_time_slot(
                op, discipline=discipline, course=course, client=client
            )
        case UpsertCalendarEvent():
            return _run_upsert_calendar_event(
                op, discipline=discipline, course=course, client=client
            )
        case DeleteCalendarEvent():
            return _run_delete_calendar_event(
                op, discipline=discipline, course=course, client=client
            )
        case WarnTimeSlotPinned():
            return _run_warn_time_slot_pinned(op)


def _run_upsert_course(op: UpsertCourse, *, client: httpx.Client) -> OpResult:
    """
    `PUT /api/course`, which takes the whole natural key in its body.

    The course is addressed by `{instructor}_{edition}` everywhere else,
    so it is split back apart here rather than carried twice through the
    plan.
    """
    instructor, _, edition = op.course.partition("_")
    body = generated.CourseCreate(
        discipline=op.discipline,
        instructor=instructor,
        edition=edition,
        description=op.description,
        startAt=op.start_at,
        endAt=op.end_at,
    )
    try:
        generated.upsert_course(body=body, client=client)
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(
        op=op, ok=True, message=f"upserted course {op.discipline}/{op.course}"
    )


def _run_upsert_resource(
    op: UpsertResource, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    if isinstance(op.data, FileData):
        # ROADBLOCKS.md item 1: the server's `buffer` is `z.instanceof(Buffer)`,
        # which no JSON body can satisfy, and no multipart branch exists.
        # Planned, never executed.
        return OpResult(
            op=op,
            ok=False,
            message=f"blocked: the server accepts no FILE upload yet ({op.path})",
        )

    body = generated.ResourceCreate(
        slug=op.slug,
        title=op.title,
        description=op.description,
        rev=op.ref,
        data=_request_data(op.data),
    )
    try:
        generated.upsert_resource(
            discipline=discipline, course=course, body=body, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(op=op, ok=True, message=f"upserted {op.slug}")


def _run_delete_resource(
    op: DeleteResource, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_resource(
            discipline=discipline, course=course, slug=op.slug, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(op=op, ok=True, message=f"deleted {op.slug}")


def _run_upsert_question(
    op: UpsertQuestion, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    if op.question.type == "ordering":
        # `mdq` parses `ordering` questions; the server's `question` union
        # has no such member -- see `dev/specs/to-do/push-questions.md`,
        # "Out, and why". Planned, never executed.
        return OpResult(
            op=op,
            ok=False,
            message=(
                f"blocked: the server has no `ordering` question type ({op.path})"
            ),
        )

    payload = op.question.model_dump(mode="json", by_alias=True, exclude_none=True)
    for key in DROPPED_QUESTION_KEYS:
        payload.pop(key, None)

    # `model_validate` would round-trip `payload` through one of the
    # generated union members, and that member fills every absent optional
    # field back in as an explicit `None` -- which the server's schema
    # rejects (`expected string, received null`), undoing the
    # `exclude_none` above. `model_construct` skips validation and keeps
    # `question` as the plain dict `generated.upsert_question`'s own
    # `model_dump(by_alias=True)` then serializes verbatim.
    body = generated.QuestionCreate.model_construct(
        slug=op.slug, status="DRAFT", version=op.version, question=payload
    )
    try:
        with warnings.catch_warnings():
            # Pydantic warns that `question` (a plain dict, on purpose --
            # see above) doesn't look like the union member it's typed as.
            # The dict is exactly the payload we mean to send, so this is
            # noise, not a signal.
            warnings.simplefilter("ignore", UserWarning)
            generated.upsert_question(
                discipline=discipline, course=course, body=body, client=client
            )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(op=op, ok=True, message=f"upserted {op.slug}")


def _run_delete_question(
    op: DeleteQuestion, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_question(
            discipline=discipline, course=course, slug=op.slug, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(op=op, ok=True, message=f"deleted {op.slug}")


def _run_upsert_time_slot(
    op: UpsertTimeSlot, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    body = generated.TimeSlotCreate(
        slug=op.slot.slug,
        title=op.slot.title,
        day=op.slot.day,
        start=generated.Start(hour=op.slot.start.hour, minute=op.slot.start.minute),
        duration=generated.Duration(
            hours=op.slot.duration.hours, minutes=op.slot.duration.minutes
        ),
    )
    try:
        generated.upsert_timeslot(
            discipline=discipline, course=course, body=body, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(op=op, ok=True, message=f"upserted {op.slot.slug}")


def _run_delete_time_slot(
    op: DeleteTimeSlot, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_timeslot(
            discipline=discipline, course=course, slug=op.slug, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(op=op, ok=True, message=f"deleted {op.slug}")


def _run_upsert_calendar_event(
    op: UpsertCalendarEvent, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    body = generated.CalendarEventCreate(
        kind=op.event.kind,
        title=op.event.title,
        description=op.event.description,
        week=op.event.week,
        rev=op.event.ref,
        timeSlot=op.event.time_slot,
    )
    try:
        generated.upsert_calendar_event(
            discipline=discipline, course=course, body=body, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(
        op=op, ok=True, message=f"upserted {op.event.week}/{op.event.time_slot}"
    )


def _run_delete_calendar_event(
    op: DeleteCalendarEvent, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_calendar_event(
            discipline=discipline,
            course=course,
            week=str(op.week),
            time_slot=op.time_slot,
            client=client,
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {exc}")
    return OpResult(op=op, ok=True, message=f"deleted {op.week}/{op.time_slot}")


def _run_warn_time_slot_pinned(op: WarnTimeSlotPinned) -> OpResult:
    """
    Not a write: `plan_calendar` already decided to keep this slot because
    a `CANCELLED` calendar event still pins it. Nothing to send; report it
    the same way every other op reports what it did.
    """
    return OpResult(
        op=op,
        ok=True,
        message=(f"kept: calendar event {op.week}/{op.slug} is CANCELLED and pins it"),
    )


def _server_event(item: generated.CalendarEvent) -> ServerEvent:
    """
    Project one item of the calendar-event listing down to its markers.
    """
    return ServerEvent(ref=item.rev or "", kind=item.kind)


def _time_slot_ref(item: generated.TimeSlot) -> str:
    """
    Recompute a server-listed time slot's `ref` from the fields the listing
    returned, via the same `TimeSlot` dataclass the core uses -- the server
    stores no `ref` column of its own.
    """
    slot = TimeSlot(
        slug=item.slug,
        day=item.day,
        start=TimeOfDay(hour=item.start.hour, minute=item.start.minute),
        duration=Duration(
            hours=item.duration.hours or 0, minutes=item.duration.minutes or 0
        ),
        title=item.title,
    )
    return slot.ref


def _request_data(data: ResourceData) -> RequestData:
    """
    Translate the core's `ResourceData` into the generated union member.

    Raises:
        NotImplementedError: `data` is a `FileData`, whose upload the
            server does not accept yet. `_run_upsert_resource` refuses
            those before reaching here; this is the guard for a caller
            that does not.
    """
    match data:
        case MdData(content=content):
            return generated.DataMd(type="MD", content=content)
        case CodeData(content=content, language=language):
            return generated.DataCode(type="CODE", content=content, language=language)
        case FileData():
            raise NotImplementedError("FILE upload is blocked server-side")
