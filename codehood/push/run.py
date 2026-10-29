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
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

import httpx

from ..api import generated
from ..api.base import CodehoodAPIError, auth_headers
from ..grades import ExamResult, ExamState
from .calendar import Duration, EventKey, TimeOfDay, TimeSlot
from .grades import ServerStudent
from .plan import (
    DeleteCalendarEvent,
    DeleteGradeColumn,
    DeleteQuestion,
    DeleteRepository,
    DeleteResource,
    DeleteRollCall,
    DeleteTimeSlot,
    PushOp,
    ServerEvent,
    ServerState,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertGradeColumn,
    UpsertQuestion,
    UpsertRepository,
    UpsertResource,
    UpsertTimeSlot,
    WarnEventHasRollCall,
    WarnRepositoryKept,
    WarnTimeSlotPinned,
)
from .repository import RepositoryEntry, batch_entries
from .resource import CodeData, FileData, MdData, ResourceData
from .wire import wire_question

__all__ = [
    "HttpRepositoryApi",
    "OpResult",
    "RepositoryApi",
    "describe_failure",
    "fetch_server_state",
    "fetch_students",
    "run_plan",
]

#: The generated request-side members of `Resource.data`. The `FILE` member
#: exists twice in the spec -- the upload shape (`filename` plus `buffer`)
#: and the read-back shape (`link`, `mimeType`, `filename`) -- so the
#: generator qualifies both by the schema that owns them:
#: `ResourceCreateDataFile` is the one a push sends.
type RequestData = (
    generated.DataMd | generated.DataCode | generated.ResourceCreateDataFile
)

#: What each cell of the server's grades table is called in `ExamResult`.
EXAM_STATES: dict[str, ExamState] = {
    "total": "graded",
    "pending": "pending",
    "in-progress": "in_progress",
    "missed": "missed",
    "empty": "not_held",
}


@dataclass(frozen=True)
class OpResult:
    """
    The outcome of executing one `PushOp`.
    """

    op: PushOp
    ok: bool
    message: str
    #: The operation was never attempted because an earlier one it depends
    #: on failed. Always paired with `ok=False`.
    skipped: bool = False


class RepositoryApi(Protocol):
    """
    The repository endpoints of one course, as `run.py` uses them.

    A seam: tests can pass a fake. `HttpRepositoryApi` is the real one. Every method
    raises `httpx.HTTPStatusError` (or `CodehoodAPIError`) on a refused
    request.
    """

    def list_trees(self) -> Mapping[str, str | None]:
        """
        `GET .../repository`: slug -> `tree`, `None` before the first commit.
        """
        ...

    def upsert(self, slug: str) -> None:
        """
        `PUT .../repository` with `{slug}`.
        """
        ...

    def missing(self, hashes: Sequence[str]) -> list[str]:
        """
        `POST /api/blob/missing`: the sha-256 hashes the server lacks.
        """
        ...

    def upload(self, slug: str, entries: Sequence[RepositoryEntry]) -> None:
        """
        `POST .../repository/<slug>/files`: one multipart request, one part
        per file, named by its sha-256.
        """
        ...

    def commit(
        self, slug: str, entries: Sequence[RepositoryEntry], message: str | None
    ) -> str | None:
        """
        `POST .../repository/<slug>/commit`; returns the new `head`.
        """
        ...

    def delete(self, slug: str) -> None:
        """
        `DELETE .../repository/<slug>`.
        """
        ...


class HttpRepositoryApi:
    """
    `RepositoryApi` over the REST API. Listing, upsert, delete and `missing`
    use the generated client; the multipart upload and the commit are
    hand-written because the generator handles neither a multipart body nor
    an array of inline objects.
    """

    def __init__(self, client: httpx.Client, discipline: str, course: str) -> None:
        self.client = client
        self.discipline = discipline
        self.course = course

    def list_trees(self) -> Mapping[str, str | None]:
        """
        See `RepositoryApi.list_trees`.
        """
        items = generated.repository_list(
            discipline=self.discipline, course=self.course, client=self.client
        )
        return {item.slug: item.tree for item in items}

    def upsert(self, slug: str) -> None:
        """
        See `RepositoryApi.upsert`.
        """
        generated.repository_upsert(
            discipline=self.discipline,
            course=self.course,
            body=generated.RepositoryCreate(slug=slug),
            client=self.client,
        )

    def missing(self, hashes: Sequence[str]) -> list[str]:
        """
        See `RepositoryApi.missing`.
        """
        result = generated.blob_missing(
            body=generated.BlobMissingInput(hashes=list(hashes)), client=self.client
        )
        return list(result.missing)

    def upload(self, slug: str, entries: Sequence[RepositoryEntry]) -> None:
        """
        See `RepositoryApi.upload`. Reads each file from `entry.source`.
        """
        parts = {entry.sha256: entry.source for entry in entries}
        files = [
            (sha256, (sha256, source.read_bytes(), "application/octet-stream"))
            for sha256, source in parts.items()
        ]
        # Built apart from the client: its default `Content-Type: application/json`
        # would hide the multipart boundary `httpx` computes.
        request = httpx.Request(
            "POST",
            self.client.base_url.join(self._url(slug, "files")),
            files=files,
            headers=auth_headers(self.client),
        )
        self.client.send(request).raise_for_status()

    def commit(
        self, slug: str, entries: Sequence[RepositoryEntry], message: str | None
    ) -> str | None:
        """
        See `RepositoryApi.commit`.
        """
        body: dict[str, object] = {
            "tree": [
                {"path": entry.path, "mode": entry.mode, "hash": entry.sha256}
                for entry in entries
            ]
        }
        if message is not None:
            body["message"] = message
        response = self.client.post(
            self._url(slug, "commit"), json=body, headers=auth_headers(self.client)
        )
        response.raise_for_status()
        head = response.json().get("head")
        return head if isinstance(head, str) else None

    def delete(self, slug: str) -> None:
        """
        See `RepositoryApi.delete`.
        """
        generated.repository_delete(
            discipline=self.discipline,
            course=self.course,
            slug=slug,
            client=self.client,
        )

    def _url(self, *parts: str) -> str:
        base = f"/api/course/{self.discipline}/{self.course}/repository"
        return "/".join((base, *(quote(part, safe="") for part in parts)))


def fetch_server_state(
    discipline: str,
    course: str,
    client: httpx.Client,
    repositories: RepositoryApi | None = None,
) -> ServerState:
    """
    Read what the server currently holds for a course.

    The mapping's `cli.course.preSync` RPC does not exist on the server
    (see `ROADBLOCKS.md`), so this reads the list endpoints instead and
    projects each one down to the markers `plan_push` compares: `GET
    /api/course/{discipline}/{course}` to check the course exists,
    `.../resource` to `slug -> ref`, `.../question` to `slug -> version`,
    `.../time-slot` to `slug -> ref`, `.../calendar-event` to
    `(week, timeSlot) -> ServerEvent`, and `.../grade-column` to
    `slug -> rev`; `.../roll-call` adds each event's attendance count.
    `repositories` gives `slug -> tree`; without it no repository is listed.

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
    grade_columns = generated.list_grade_column(
        discipline=discipline, course=course, client=client
    )
    # A roll call hangs off a calendar event, so none can exist without one.
    roll_calls = (
        {
            (roll_call.week, roll_call.time_slot): len(roll_call.attendances)
            for roll_call in generated.list_roll_call(
                discipline=discipline, course=course, client=client
            )
        }
        if calendar_events
        else {}
    )
    return ServerState(
        course_exists=True,
        resources={resource.slug: resource.rev or "" for resource in resources},
        resource_events={
            resource.slug: (
                EventKey(week=resource.event.week, time_slot=resource.event.time_slot)
                if resource.event is not None
                else None
            )
            for resource in resources
        },
        questions={question.slug: question.version for question in questions},
        time_slots={slot.slug: _time_slot_ref(slot) for slot in time_slots},
        calendar_events={
            (event.week, event.time_slot.slug): _server_event(
                event, roll_calls.get((event.week, event.time_slot.slug))
            )
            for event in calendar_events
        },
        grade_columns={column.slug: column.rev or "" for column in grade_columns},
        repositories=dict(repositories.list_trees()) if repositories else {},
    )


def fetch_students(
    discipline: str, course: str, client: httpx.Client
) -> tuple[ServerStudent, ...]:
    """
    Read every enrolled student with their result at every exam.

    Returns:
        Nothing for a course the server does not have yet: it has no
        student to grade, and the columns are pushed empty.
    """
    try:
        report = generated.course_grades(
            discipline=discipline, course=course, client=client
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return ()
    return tuple(_server_student(item) for item in report.students)


def run_plan(
    ops: Iterable[PushOp],
    *,
    discipline: str,
    course: str,
    client: httpx.Client,
    repositories: RepositoryApi | None = None,
) -> Iterator[OpResult]:
    """
    Execute a plan, yielding one result per operation.

    A failure executing an operation is caught and reported as a failed
    `OpResult`; the remaining operations still run -- see `push.md`,
    "FR-SYNC-005", "a sync is not atomic". The exception is the course
    row's own `PUT`: every other operation hangs off the course, so after
    it fails the rest come back as skipped results, never attempted.

    Repository ops go through `repositories`, `HttpRepositoryApi` over
    `client` by default.
    """
    api = repositories or HttpRepositoryApi(client, discipline, course)
    course_failed = False
    for op in ops:
        if course_failed:
            yield OpResult(
                op=op,
                ok=False,
                skipped=True,
                message="not attempted: the course could not be written",
            )
            continue
        result = _run_op(
            op, discipline=discipline, course=course, client=client, repositories=api
        )
        yield result
        course_failed = isinstance(op, UpsertCourse) and not result.ok


#
# Utilities
#
def describe_failure(exc: CodehoodAPIError | httpx.HTTPStatusError) -> str:
    """
    One line saying why a request failed, with the server's own message.

    An undocumented error status (`400` on a question the server refuses)
    reaches here as a bare `httpx.HTTPStatusError`, whose text only repeats
    the URL; the reason is in the response body.
    """
    if not isinstance(exc, httpx.HTTPStatusError):
        return str(exc)
    status = exc.response.status_code
    try:
        message = exc.response.json()["message"]
    except (ValueError, KeyError, TypeError):
        message = exc.response.text.strip()
    return (
        f"{status} {message}" if message else f"{status} {exc.response.reason_phrase}"
    )


def _run_op(
    op: PushOp,
    *,
    discipline: str,
    course: str,
    client: httpx.Client,
    repositories: RepositoryApi,
) -> OpResult:
    match op:
        case UpsertCourse():
            return _run_upsert_course(op, client=client)
        case UpsertRepository():
            return run_upsert_repository(op, repositories)
        case WarnRepositoryKept():
            return run_warn_repository_kept(op)
        case DeleteRepository():
            return run_delete_repository(op, repositories)
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
        case WarnEventHasRollCall():
            return _run_warn_event_has_roll_call(op)
        case DeleteRollCall():
            return _run_delete_roll_call(
                op, discipline=discipline, course=course, client=client
            )
        case UpsertGradeColumn():
            return _run_upsert_grade_column(
                op, discipline=discipline, course=course, client=client
            )
        case DeleteGradeColumn():
            return _run_delete_grade_column(
                op, discipline=discipline, course=course, client=client
            )


def run_upsert_repository(op: UpsertRepository, api: RepositoryApi) -> OpResult:
    """
    Push one repository: upsert it, ask which blobs are missing, upload
    those in batches of at most `MAX_FILE_BYTES` (`batch_entries`), then
    commit the tree.

    A failed step stops the op and reports it; nothing after it runs. The
    message says how many files were uploaded and the new head.
    """
    slug = op.tree.slug
    entries = op.tree.entries
    uploaded = 0
    try:
        api.upsert(slug)
        hashes = list(dict.fromkeys(entry.sha256 for entry in entries))
        missing = set(api.missing(hashes))
        pending = [entry for entry in entries if entry.sha256 in missing]
        for batch in batch_entries(_unique_blobs(pending)):
            api.upload(slug, batch)
            uploaded += len(batch)
        head = api.commit(slug, entries, op.message)
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(
        op=op,
        ok=True,
        message=f"uploaded {uploaded} file(s), head {head}"
        if head
        else f"uploaded {uploaded} file(s)",
    )


def run_warn_repository_kept(op: WarnRepositoryKept) -> OpResult:
    """
    Not a write: report the repository `plan_repositories` kept.
    """
    return OpResult(
        op=op,
        ok=True,
        message=f"kept: {op.slug} has no folder; --drop-repositories deletes it",
    )


def run_delete_repository(op: DeleteRepository, api: RepositoryApi) -> OpResult:
    """
    Delete one repository, reporting a refused request as a failed result.
    """
    try:
        api.delete(op.slug)
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(op=op, ok=True, message=f"deleted {op.slug}")


def _unique_blobs(entries: Sequence[RepositoryEntry]) -> list[RepositoryEntry]:
    """
    One entry per distinct content: a part name may not repeat in an upload.
    """
    return list({entry.sha256: entry for entry in entries}.values())


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
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
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
        event=(
            generated.Event(week=op.event.week, timeSlot=op.event.time_slot)
            if op.event is not None
            else None
        ),
        data=_request_data(op.data),
    )
    try:
        generated.upsert_resource(
            discipline=discipline, course=course, body=body, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(op=op, ok=True, message=f"upserted {op.slug}")


def _run_delete_resource(
    op: DeleteResource, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_resource(
            discipline=discipline, course=course, slug=op.slug, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(op=op, ok=True, message=f"deleted {op.slug}")


def _run_upsert_question(
    op: UpsertQuestion, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    payload = wire_question(op.question)

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
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(op=op, ok=True, message=f"upserted {op.slug}")


def _run_delete_question(
    op: DeleteQuestion, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_question(
            discipline=discipline, course=course, slug=op.slug, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
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
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(op=op, ok=True, message=f"upserted {op.slot.slug}")


def _run_delete_time_slot(
    op: DeleteTimeSlot, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_timeslot(
            discipline=discipline, course=course, slug=op.slug, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
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
        repositories=list(op.event.repositories),
    )
    try:
        generated.upsert_calendar_event(
            discipline=discipline, course=course, body=body, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
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
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
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


def _run_delete_roll_call(
    op: DeleteRollCall, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_roll_call(
            discipline=discipline,
            course=course,
            week=str(op.week),
            time_slot=op.time_slot,
            client=client,
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(op=op, ok=True, message=f"deleted {op.week}/{op.time_slot}")


def _run_warn_event_has_roll_call(op: WarnEventHasRollCall) -> OpResult:
    """
    Not a write: `plan_calendar` already decided to keep this event because
    it has a roll call. Report it like every other op.
    """
    return OpResult(
        op=op,
        ok=True,
        message=(
            f"kept: event {op.week}/{op.time_slot} has a roll call with "
            f"{op.attendances} attendance(s)"
        ),
    )


def _run_upsert_grade_column(
    op: UpsertGradeColumn, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    column = op.column
    body = generated.GradeColumnCreate(
        slug=column.slug,
        title=column.title,
        kind="NUMBER" if column.kind == "number" else "LABEL",
        position=column.position,
        rev=column.rev,
        values=[
            generated.ValuesItem(username=username, value=value)
            for username, value in column.values
        ],
    )
    try:
        generated.upsert_grade_column(
            discipline=discipline, course=course, body=body, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(
        op=op, ok=True, message=f"upserted {column.slug} ({len(column.values)} values)"
    )


def _run_delete_grade_column(
    op: DeleteGradeColumn, *, discipline: str, course: str, client: httpx.Client
) -> OpResult:
    try:
        generated.delete_grade_column(
            discipline=discipline, course=course, slug=op.slug, client=client
        )
    except (CodehoodAPIError, httpx.HTTPStatusError) as exc:
        return OpResult(op=op, ok=False, message=f"failed: {describe_failure(exc)}")
    return OpResult(op=op, ok=True, message=f"deleted {op.slug}")


def _server_student(item: generated.CourseGradesResponseStudentsItem) -> ServerStudent:
    """
    Project one student of the grades report into what the core computes
    from, with each exam total turned into the percentage the web shows.
    """
    exams: dict[str, ExamResult] = {}
    for slug, cell in item.results.items():
        total = getattr(cell, "total", None)
        exams[slug] = ExamResult(
            score=None if total is None else round(total * 100, 2),
            state=EXAM_STATES[cell.kind],
        )
    return ServerStudent(
        username=item.username,
        name=item.name,
        email=item.email,
        school_id=item.school_id,
        github=item.github_id,
        status="active" if item.status == "ACTIVE" else "dropped",
        exams=exams,
    )


def _server_event(
    item: generated.CalendarEvent, attendances: int | None
) -> ServerEvent:
    """
    Project one item of the calendar-event listing down to its markers.

    `attendances` is the size of the event's roll call, `None` without one.
    """
    return ServerEvent(ref=item.rev or "", kind=item.kind, attendances=attendances)


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
