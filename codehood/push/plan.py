"""
The pure core of `codehood push`: diff a repository against the server's
current state into a `Plan`, the writes to run and the notices that explain
what was left alone.

No client, no ids, no `run()` -- see `dev/specs/to-do/push.md`,
"Architecture". `run.py` is the only thing in `codehood/push/` that
executes a `Write`.

The two inputs are whole values, `LocalState` and `ServerState`, rather
than a dozen loose mappings: `slug -> ref` and `slug -> version` are the
same type and mean different things, and naming them as fields is what
stops a caller from swapping them silently.

Every keyed entity follows one shape: `diff_keyed` walks the keys of both
sides and asks a pure `merge_*` function for a `Decision` per key. A merge
only moves the server forward -- it writes what the repository holds that
the server does not, and prunes what is gone locally unless something
protects it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Container, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from functools import partial
from pathlib import Path
from typing import Literal

from ..models.repo import CourseKey
from .calendar import Event, EventKey, TimeSlot
from .exclude import ExcludedFile
from .grades import GradeColumn
from .project import RemoteEntry, resource_event_of, time_slot_of
from .question import AnyQuestion, InvalidQuestion, QuestionFile, QuestionStatus
from .repository import RepositoryTree
from .resource import ResourceData, ResourceFile
from .wire import instant

__all__ = [
    "STATUS_ORDER",
    "Decision",
    "DeleteCalendarEvent",
    "DeleteGradeColumn",
    "DeleteQuestion",
    "DeleteRepository",
    "DeleteResource",
    "DeleteRollCall",
    "DeleteTimeSlot",
    "Keep",
    "KeptCancelled",
    "KeptDraftPublished",
    "KeptForRollCall",
    "KeptPinnedSlot",
    "KeptRepository",
    "LocalState",
    "Notice",
    "Plan",
    "Prune",
    "Put",
    "Rejected",
    "ServerEvent",
    "ServerQuestion",
    "ServerState",
    "Skip",
    "UpsertCalendarEvent",
    "UpsertCourse",
    "UpsertGradeColumn",
    "UpsertQuestion",
    "UpsertRepository",
    "UpsertResource",
    "UpsertTimeSlot",
    "Write",
    "course_ref",
    "diff_keyed",
    "join_status",
    "merge_event",
    "merge_grade_column",
    "merge_question",
    "merge_repository",
    "merge_resource",
    "merge_time_slot",
    "plan_calendar",
    "plan_grades",
    "plan_push",
    "plan_repositories",
    "protect",
]


#: The order a question's status moves through on a push.
STATUS_ORDER: tuple[QuestionStatus, ...] = ("DRAFT", "PUBLISHED", "HIDDEN")


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

    key: CourseKey
    description: str
    start: date
    end: date
    slots: tuple[TimeSlot, ...] = ()
    events: tuple[Event, ...] = ()
    resources: tuple[ResourceFile, ...] = ()
    questions: tuple[QuestionFile | InvalidQuestion, ...] = ()
    grade_columns: tuple[GradeColumn, ...] | None = ()
    repositories: tuple[RepositoryTree, ...] = ()
    #: Files left out by `[push] exclude`: never written, never pruned.
    excluded: tuple[ExcludedFile, ...] = ()
    #: Versionable files no push stage read, sorted. Reported, never pushed.
    unconsumed: tuple[str, ...] = ()
    #: Problems found while reading that do not stop a push, for the shell to print.
    warnings: tuple[str, ...] = ()

    @property
    def discipline(self) -> str:
        return self.key.discipline

    @property
    def course(self) -> str:
        return self.key.slug


@dataclass(frozen=True)
class ServerEvent:
    """
    What the sync preflight reports about one calendar event.

    `ref` decides whether to rewrite it and `kind` whether to touch it at
    all -- see the mapping's "Sync preflight". `entry` is the event as the
    server holds it, projected to the payload.
    """

    ref: str
    kind: Literal["REGULAR", "HOLIDAY", "CANCELLED"]
    attendances: int | None = None
    entry: RemoteEntry | None = None


@dataclass(frozen=True)
class ServerQuestion:
    """
    What the sync preflight reports about one question.

    `entry` is the question as the server holds it, projected to the
    payload: its `rev` is the server's own, and the version label stays in
    `version`.
    """

    version: str
    status: QuestionStatus = "DRAFT"
    entry: RemoteEntry | None = None


@dataclass(frozen=True)
class ServerState:
    """
    What the server currently holds for a course.

    Each entity carries a `RemoteEntry`: its payload, projected back from
    what the server returned, and the `rev` and `updatedAt` it carries.
    """

    course_exists: bool = False
    #: The course row. Its `rev` is the `course_ref` of its last push.
    course: RemoteEntry | None = None
    resources: Mapping[str, RemoteEntry] = field(default_factory=dict)
    questions: Mapping[str, ServerQuestion] = field(default_factory=dict)
    time_slots: Mapping[str, RemoteEntry] = field(default_factory=dict)
    calendar_events: Mapping[tuple[int, str], ServerEvent] = field(default_factory=dict)
    grade_columns: Mapping[str, RemoteEntry] = field(default_factory=dict)
    #: Slug -> sha1 of the head commit's root tree, `None` before the first
    #: commit.
    repositories: Mapping[str, str | None] = field(default_factory=dict)


#
# Operations
#
@dataclass(frozen=True)
class UpsertCourse:
    """
    The course row to `PUT`, keyed by `(discipline, course)`.
    """

    key: CourseKey
    description: str
    start_at: str
    end_at: str
    #: The `course_ref` the row is stored with, as its `rev`.
    ref: str

    @property
    def discipline(self) -> str:
        return self.key.discipline

    @property
    def course(self) -> str:
        return self.key.slug


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
    status: QuestionStatus = "PUBLISHED"


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


@dataclass(frozen=True)
class UpsertRepository:
    """
    One repository to create if missing and commit `tree` to.

    `message` is the `-m/--message` of the push, `None` for the server's
    default.
    """

    tree: RepositoryTree
    message: str | None = None


@dataclass(frozen=True)
class DeleteRepository:
    """
    A repository to delete by slug: its folder is gone and the push ran with
    `--drop-repositories`.
    """

    slug: str


Write = (
    UpsertCourse
    | UpsertRepository
    | DeleteRepository
    | UpsertResource
    | DeleteResource
    | UpsertQuestion
    | DeleteQuestion
    | UpsertTimeSlot
    | DeleteTimeSlot
    | UpsertCalendarEvent
    | DeleteCalendarEvent
    | DeleteRollCall
    | UpsertGradeColumn
    | DeleteGradeColumn
)


#
# Notices
#
@dataclass(frozen=True)
class Rejected:
    """
    A question file `mdq` refused. The server keeps what it holds under the
    slug and the push fails.
    """

    slug: str
    path: Path
    reason: str


@dataclass(frozen=True)
class KeptDraftPublished:
    """
    A question whose file marks it a draft, kept as the server has it
    because a push never moves a question back down its status.
    """

    slug: str
    status: QuestionStatus
    path: Path


@dataclass(frozen=True)
class KeptPinnedSlot:
    """
    A time slot the preflight would otherwise prune, kept because the
    `CANCELLED` calendar events of `weeks` still pin it.

    A cancelled event is never rewritten or pruned (see the mapping's
    "Calendar events"), and the server refuses to orphan it -- see
    "Deletion and pruning".
    """

    slug: str
    weeks: tuple[int, ...]


@dataclass(frozen=True)
class KeptForRollCall:
    """
    A calendar event kept, though gone locally, because it has a roll call.

    Reported even when the roll call holds no attendance.
    """

    week: int
    time_slot: str
    attendances: int


@dataclass(frozen=True)
class KeptRepository:
    """
    A repository the server has and the course root no longer does, kept
    because deleting it kills its clone URL and history.
    """

    slug: str


@dataclass(frozen=True)
class KeptCancelled:
    """
    A calendar event the server reports as `CANCELLED`, left alone whatever
    the repository says.

    Only an input of the plan: it pins the event's slot, and `plan_calendar`
    folds it into a `KeptPinnedSlot`, so it never reaches `Plan.notices`.
    """

    week: int
    time_slot: str


Notice = (
    Rejected
    | KeptDraftPublished
    | KeptPinnedSlot
    | KeptForRollCall
    | KeptRepository
    | KeptCancelled
)


@dataclass(frozen=True)
class Plan:
    """
    What a push will write and what it leaves alone, and why.

    `writes` is in execution order. `notices` explain what the plan did not
    write; a `Rejected` one also makes the push fail.
    """

    writes: tuple[Write, ...] = ()
    notices: tuple[Notice, ...] = ()

    @classmethod
    def of(cls, decisions: Iterable[Decision]) -> Plan:
        """
        Collect decisions, in order, into the writes and notices they carry.
        """
        writes: list[Write] = []
        notices: list[Notice] = []
        for decision in decisions:
            match decision:
                case Put(op=op, notices=extra):
                    writes.append(op)
                    notices.extend(extra)
                case Prune(op=op, before=before):
                    writes.extend((*before, op))
                case Keep(notice=notice):
                    notices.append(notice)
                case Skip():
                    pass
        return cls(tuple(writes), tuple(notices))

    @property
    def rejected(self) -> tuple[Rejected, ...]:
        """
        The notices that fail the push.
        """
        return tuple(n for n in self.notices if isinstance(n, Rejected))

    def __add__(self, other: Plan) -> Plan:
        return Plan(self.writes + other.writes, self.notices + other.notices)


#
# Decisions
#
@dataclass(frozen=True)
class Skip:
    """
    Both sides already agree, or something protects the server's copy.
    """


@dataclass(frozen=True)
class Put:
    """
    Write `op`, and tell why the write is not the whole story.
    """

    op: Write
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class Prune:
    """
    Delete what the repository no longer holds, after the `before` writes
    the delete depends on.
    """

    op: Write
    before: tuple[Write, ...] = ()


@dataclass(frozen=True)
class Keep:
    """
    Write nothing, and say why.
    """

    notice: Notice


Decision = Skip | Put | Prune | Keep


def diff_keyed[K, L, S](
    local: Mapping[K, L],
    server: Mapping[K, S],
    merge: Callable[[K, L | None, S | None], Decision],
) -> Iterator[Decision]:
    """
    Ask `merge` for a decision on every key of either side: the local keys
    in local order, then the server-only keys in key order.

    `merge` receives the key too, since a server marker alone often cannot
    name what to delete. A side that lacks the key gives `None`.
    """
    for key, value in local.items():
        yield merge(key, value, server.get(key))
    for key in sorted(server.keys() - local.keys()):  # type: ignore[type-var]
        yield merge(key, None, server[key])


def protect[K, L, S](
    merge: Callable[[K, L | None, S | None], Decision], keys: Container[K]
) -> Callable[[K, L | None, S | None], Decision]:
    """
    Wrap `merge` so the server's copy of every key in `keys` is never pruned.
    """

    def protected(key: K, local: L | None, server: S | None) -> Decision:
        if local is None and key in keys:
            return Skip()
        return merge(key, local, server)

    return protected


def join_status(a: QuestionStatus, b: QuestionStatus) -> QuestionStatus:
    """
    The further of two statuses along `STATUS_ORDER`.
    """
    return max(a, b, key=STATUS_ORDER.index)


#
# Merges
#
def merge_resource(
    slug: str,
    local: ResourceFile | None,
    server: tuple[str, EventKey | None] | None,
) -> Decision:
    """
    Upsert a resource whose `(ref, event)` differs from the server's marker;
    delete one whose file is gone.
    """
    if local is None:
        return Prune(DeleteResource(slug=slug))
    if server == (local.ref, local.event):
        return Skip()
    return Put(
        UpsertResource(
            slug=local.slug,
            title=local.title,
            description=local.description,
            data=local.data,
            ref=local.ref,
            path=local.path,
            event=local.event,
        )
    )


def merge_question(
    slug: str,
    local: QuestionFile | InvalidQuestion | None,
    server: ServerQuestion | None,
) -> Decision:
    """
    Upsert a question whose `version` or status moved; delete one whose file
    is gone; reject one `mdq` refused.

    The status only moves forward, `DRAFT` to `PUBLISHED` to `HIDDEN`: the
    file can publish a draft, and only the web hides a question or brings it
    back. So a push never undoes what the web did, and needs no memory of
    the previous push to tell which side changed. A draft file over a
    published question is kept published, with a notice.
    """
    if local is None:
        return Prune(DeleteQuestion(slug=slug))
    if isinstance(local, InvalidQuestion):
        return Keep(Rejected(slug=local.slug, path=local.path, reason=local.reason))

    if server is None:
        return Put(_upsert_question(local, local.status))
    status = join_status(local.status, server.status)
    notices: tuple[Notice, ...] = ()
    if local.status == "DRAFT" and server.status == "PUBLISHED":
        notices = (
            KeptDraftPublished(slug=local.slug, status=server.status, path=local.path),
        )
    if server.version == local.version and server.status == status:
        return Keep(notices[0]) if notices else Skip()
    return Put(_upsert_question(local, status), notices)


def merge_time_slot(slug: str, local: TimeSlot | None, server: str | None) -> Decision:
    """
    Upsert a slot whose `ref` differs from the server's; delete one the
    calendar no longer declares.
    """
    if local is None:
        return Prune(DeleteTimeSlot(slug=slug))
    return Skip() if server == local.ref else Put(UpsertTimeSlot(slot=local))


def merge_event(
    key: tuple[int, str],
    local: Event | None,
    server: ServerEvent | None,
    *,
    drop_roll_calls: bool = False,
) -> Decision:
    """
    Upsert an event whose `(ref, kind)` differs from the server's; delete one
    the calendar no longer fills.

    A `CANCELLED` server event absorbs everything: it is neither rewritten
    nor pruned, whatever the repository says. An event with a roll call is
    kept, unless `drop_roll_calls` deletes the roll call first.
    """
    week, time_slot = key
    if server is not None and server.kind == "CANCELLED":
        return Keep(KeptCancelled(week=week, time_slot=time_slot))
    if local is not None:
        if server is not None and (server.ref, server.kind) == (local.ref, local.kind):
            return Skip()
        return Put(UpsertCalendarEvent(event=local))
    if server is None:
        return Skip()
    delete = DeleteCalendarEvent(week=week, time_slot=time_slot)
    if server.attendances is None:
        return Prune(delete)
    if drop_roll_calls:
        return Prune(delete, before=(DeleteRollCall(week=week, time_slot=time_slot),))
    return Keep(
        KeptForRollCall(week=week, time_slot=time_slot, attendances=server.attendances)
    )


def merge_grade_column(
    slug: str, local: GradeColumn | None, server: str | None
) -> Decision:
    """
    Upsert a column whose `rev` differs from the server's; delete one
    `codehood.toml` no longer declares.
    """
    if local is None:
        return Prune(DeleteGradeColumn(slug=slug))
    return Skip() if server == local.rev else Put(UpsertGradeColumn(column=local))


def merge_repository(
    slug: str,
    local: RepositoryTree | None,
    server: str | None,
    *,
    drop_repositories: bool = False,
    message: str | None = None,
) -> Decision:
    """
    Commit a repository whose `tree_sha` differs from the server's tree
    (`None` before the first commit included); keep or, with
    `drop_repositories`, delete one whose folder is gone.
    """
    if local is None:
        if drop_repositories:
            return Prune(DeleteRepository(slug=slug))
        return Keep(KeptRepository(slug=slug))
    if server == local.tree_sha:
        return Skip()
    return Put(UpsertRepository(tree=local, message=message))


#
# Plan
#
def plan_push(
    local: LocalState,
    server: ServerState,
    *,
    drop_roll_calls: bool = False,
    drop_repositories: bool = False,
    message: str | None = None,
) -> Plan:
    """
    Diff a repository against the server's current state into a `Plan`.

    The course row is `PUT` when it does not exist or its `rev` is not the
    `course_ref` of the description and dates, so a push with nothing new
    plans nothing.

    Repositories come right after the course (see `plan_repositories`):
    an event links them by slug, so they exist before the calendar. Calendar
    slots and events follow (see `plan_calendar`): a slot an event needs has
    to exist before the event is written, and a resource attached to an
    event needs the event to exist first. Resources, questions and grade
    columns follow.
    """
    start_at, end_at = _timestamp(local.start), _timestamp(local.end)
    ref = course_ref(local.description, start_at, end_at)
    course = Plan()
    course_rev = server.course.rev if server.course is not None else None
    if not server.course_exists or course_rev != ref:
        course = Plan(
            writes=(
                UpsertCourse(
                    key=local.key,
                    description=local.description,
                    start_at=start_at,
                    end_at=end_at,
                    ref=ref,
                ),
            )
        )
    return (
        course
        + plan_repositories(
            local, server, drop_repositories=drop_repositories, message=message
        )
        + plan_calendar(local, server, drop_roll_calls=drop_roll_calls)
        + plan_resources(local, server)
        + plan_questions(local, server)
        + plan_grades(local, server)
    )


def plan_resources(local: LocalState, server: ServerState) -> Plan:
    """
    The resource half of a plan: upserts first, then the deletes, except
    for the slugs an `exclude` pattern leaves out.
    """
    markers = {
        slug: (entry.rev or "", _resource_event(entry))
        for slug, entry in server.resources.items()
    }
    merge = protect(merge_resource, _excluded(local, "resource"))
    return Plan.of(
        diff_keyed({file.slug: file for file in local.resources}, markers, merge)
    )


def plan_questions(local: LocalState, server: ServerState) -> Plan:
    """
    The question half of a plan: upserts and rejections first, then the
    deletes, except for the slugs an `exclude` pattern leaves out.
    """
    merge = protect(merge_question, _excluded(local, "question"))
    return Plan.of(
        diff_keyed({q.slug: q for q in local.questions}, server.questions, merge)
    )


def plan_calendar(
    local: LocalState, server: ServerState, *, drop_roll_calls: bool = False
) -> Plan:
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
    place even when no local `days:` entry accounts for it, with one
    `KeptPinnedSlot` per slot naming the weeks.

    An event with a roll call that left the local calendar is kept with a
    `KeptForRollCall`, and pins its slot the same way (silently). With
    `drop_roll_calls` its roll call is deleted first, then the event.
    """
    local_slugs = {slot.slug for slot in local.slots}
    events = list(
        diff_keyed(
            {(event.week, event.time_slot): event for event in local.events},
            server.calendar_events,
            partial(merge_event, drop_roll_calls=drop_roll_calls),
        )
    )
    pinned, pin_notices = _pin_slots(events, local_slugs)
    slots = list(
        diff_keyed(
            {slot.slug: slot for slot in local.slots},
            {slug: _slot_ref(entry) for slug, entry in server.time_slots.items()},
            protect(merge_time_slot, pinned),
        )
    )
    reported = [
        d
        for d in events
        if isinstance(d, Keep) and not isinstance(d.notice, KeptCancelled)
    ]
    return Plan.of(
        [
            *_only(events, Prune),
            *_only(slots, Prune),
            *_only(slots, Put),
            *_only(events, Put),
            *reported,
        ]
    ) + Plan(notices=pin_notices)


def plan_repositories(
    local: LocalState,
    server: ServerState,
    *,
    drop_repositories: bool = False,
    message: str | None = None,
) -> Plan:
    """
    The repository half of a plan, in slug order.

    A local repository gets an `UpsertRepository` when the server lacks it
    or reports a `tree` other than its `tree_sha` (`None` included). A
    server repository with no local folder gets a `KeptRepository`, or
    a `DeleteRepository` with `drop_repositories`.
    """
    merge = partial(
        merge_repository, drop_repositories=drop_repositories, message=message
    )
    return Plan.of(
        diff_keyed(
            {tree.slug: tree for tree in local.repositories}, server.repositories, merge
        )
    )


def plan_grades(local: LocalState, server: ServerState) -> Plan:
    """
    The grade column half of a plan: upsert what changed, delete what
    `codehood.toml` no longer declares.

    Nothing is planned when `local.grade_columns` is `None`: columns that
    could not be computed are not evidence that the server's should go.
    """
    if local.grade_columns is None:
        return Plan()
    return Plan.of(
        diff_keyed(
            {column.slug: column for column in local.grade_columns},
            {slug: entry.rev or "" for slug, entry in server.grade_columns.items()},
            merge_grade_column,
        )
    )


#
# Utilities
#
def _excluded(local: LocalState, kind: str) -> frozenset[str]:
    """
    The slugs of `kind` that an `exclude` pattern leaves out of the push.
    """
    return frozenset(file.slug for file in local.excluded if file.kind == kind)


def _only[D: Decision](decisions: Iterable[Decision], kind: type[D]) -> list[D]:
    return [d for d in decisions if isinstance(d, kind)]


def _pin_slots(
    events: Iterable[Decision], local_slugs: set[str]
) -> tuple[frozenset[str], tuple[KeptPinnedSlot, ...]]:
    """
    Fold the kept events into the slots they pin and one notice per slot
    whose pin the calendar does not account for.
    """
    pinned: set[str] = set()
    weeks: dict[str, list[int]] = {}
    for decision in events:
        if not isinstance(decision, Keep):
            continue
        match decision.notice:
            case KeptForRollCall(time_slot=slot):
                pinned.add(slot)
            case KeptCancelled(week=week, time_slot=slot):
                pinned.add(slot)
                if slot not in local_slugs:
                    weeks.setdefault(slot, []).append(week)
    notices = tuple(
        KeptPinnedSlot(slug=slug, weeks=tuple(sorted(found)))
        for slug, found in sorted(weeks.items())
    )
    return frozenset(pinned), notices


def _upsert_question(question: QuestionFile, status: QuestionStatus) -> UpsertQuestion:
    return UpsertQuestion(
        slug=question.slug,
        version=question.version,
        question=question.question,
        path=question.path,
        status=status,
    )


def course_ref(description: str, start_at: str, end_at: str) -> str:
    """
    Digest the fields a push writes on the course row into the `rev` it
    stores, the way `resource.content_ref` digests a resource.
    """
    canonical = json.dumps(
        {"v": "v1", "description": description, "startAt": start_at, "endAt": end_at},
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    return f"v1:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _timestamp(day: date) -> str:
    """
    A date as the UTC midnight timestamp the server's `startAt`/`endAt`
    expect.
    """
    return instant(day)


def _resource_event(entry: RemoteEntry) -> EventKey | None:
    """
    The lesson a server resource is attached to, from its payload.
    """
    return resource_event_of(entry.payload)


def _slot_ref(entry: RemoteEntry) -> str:
    """
    The `ref` of a server time slot, which stores none: recomputed from its
    payload through the same `TimeSlot` the core uses.
    """
    return time_slot_of(entry.payload).ref
