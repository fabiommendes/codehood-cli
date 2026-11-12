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
from dataclasses import dataclass, field, replace
from datetime import date
from functools import partial
from pathlib import Path
from typing import Literal

from ..models.repo import CourseKey
from .base import BaseEntry, BaseState
from .calendar import Event, EventKey, TimeSlot
from .exclude import ExcludedFile
from .grades import GradeColumn
from .project import RemoteEntry, resource_event_of, time_slot_of
from .question import AnyQuestion, InvalidQuestion, QuestionFile, QuestionStatus
from .repository import RepositoryTree
from .resource import ResourceData, ResourceFile
from .wire import (
    Payload,
    course_payload,
    event_payload,
    grade_column_payload,
    instant,
    question_payload,
    resource_payload,
    time_slot_payload,
)

__all__ = [
    "COURSE_KEY",
    "STATUS_ORDER",
    "BaseUpdate",
    "Confirmation",
    "Conflict",
    "ConflictReason",
    "Decision",
    "DeleteCalendarEvent",
    "DeleteGradeColumn",
    "DeleteQuestion",
    "DeleteRepository",
    "DeleteResource",
    "DeleteRollCall",
    "DeleteTimeSlot",
    "EntityKind",
    "Keep",
    "KeptCancelled",
    "KeptDraftPublished",
    "KeptForRollCall",
    "KeptPinnedSlot",
    "KeptRepository",
    "LocalState",
    "Notice",
    "OtherCli",
    "Plan",
    "Prune",
    "Pull",
    "Put",
    "Rejected",
    "ServerDrifted",
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
    "diff_fields",
    "diff_keyed",
    "event_key",
    "join_status",
    "merge_event",
    "merge_grade_column",
    "merge_question",
    "merge_repository",
    "merge_resource",
    "merge_time_slot",
    "parse_event_key",
    "plan_calendar",
    "plan_grades",
    "plan_repositories",
    "plan_sync",
    "protect",
    "three_way",
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
    entry: RemoteEntry
    attendances: int | None = None


@dataclass(frozen=True)
class ServerQuestion:
    """
    What the sync preflight reports about one question.

    `entry` is the question as the server holds it, projected to the
    payload: its `rev` is the server's own, and the version label stays in
    `version`.
    """

    version: str
    entry: RemoteEntry
    status: QuestionStatus = "DRAFT"


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


@dataclass(frozen=True)
class ServerDrifted:
    """
    An entity pushed one way only (a grade column) that the server holds in a
    form other than the base: the push overwrites it, and this says which
    `fields` of it are lost.
    """

    kind: EntityKind
    key: str
    fields: tuple[str, ...]


Notice = (
    Rejected
    | ServerDrifted
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

    The rest is what a three-way plan adds. `pulls`, `conflicts` and
    `other_cli` are the entities the plan does not write to the server.
    `base_updates` are the changes of the base that need no execution: an
    entity both sides agree on, and one gone from both. `confirmations` pair a
    write with the base update to apply once it succeeds.
    """

    writes: tuple[Write, ...] = ()
    notices: tuple[Notice, ...] = ()
    pulls: tuple[Pull, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    other_cli: tuple[OtherCli, ...] = ()
    base_updates: tuple[BaseUpdate, ...] = ()
    confirmations: tuple[Confirmation, ...] = ()

    @classmethod
    def of(cls, decisions: Iterable[Decision]) -> Plan:
        """
        Collect decisions, in order, into the writes and notices they carry.
        """
        writes: list[Write] = []
        notices: list[Notice] = []
        pulls: list[Pull] = []
        conflicts: list[Conflict] = []
        other_cli: list[OtherCli] = []
        updates: list[BaseUpdate] = []
        confirmations: list[Confirmation] = []
        for decision in decisions:
            match decision:
                case Put(op=op, notices=extra, base=base):
                    writes.append(op)
                    notices.extend(extra)
                    if base is not None:
                        confirmations.append(Confirmation(op, base))
                case Prune(op=op, before=before, notices=extra, base=base):
                    writes.extend((*before, op))
                    notices.extend(extra)
                    if base is not None:
                        confirmations.append(Confirmation(op, base))
                case Keep(notice=notice, base=base):
                    notices.append(notice)
                    if base is not None:
                        updates.append(base)
                case Skip(base=base):
                    if base is not None:
                        updates.append(base)
                case Pull():
                    pulls.append(decision)
                case Conflict():
                    conflicts.append(decision)
                case OtherCli():
                    other_cli.append(decision)
        return cls(
            tuple(writes),
            tuple(notices),
            tuple(pulls),
            tuple(conflicts),
            tuple(other_cli),
            tuple(updates),
            tuple(confirmations),
        )

    @property
    def rejected(self) -> tuple[Rejected, ...]:
        """
        The notices that fail the push.
        """
        return tuple(n for n in self.notices if isinstance(n, Rejected))

    def __add__(self, other: Plan) -> Plan:
        return Plan(
            self.writes + other.writes,
            self.notices + other.notices,
            self.pulls + other.pulls,
            self.conflicts + other.conflicts,
            self.other_cli + other.other_cli,
            self.base_updates + other.base_updates,
            self.confirmations + other.confirmations,
        )


#
# Decisions
#
#: The kinds of entity a plan compares against the base, one per `BaseState`
#: collection.
type EntityKind = Literal[
    "course", "resource", "question", "time_slot", "calendar_event", "grade_column"
]


@dataclass(frozen=True)
class BaseUpdate:
    """
    The base entry of `key` to store, `None` to drop it.

    Carried by a `Skip` or `Keep` it applies at once. Carried by a `Put` or
    `Prune` it applies once the write succeeds, and then `entry.rev` and
    `entry.updated_at` are placeholders (`None`): the server's answer to the
    write fills them. `entry.payload` is always the local payload.
    """

    kind: EntityKind
    key: str
    entry: BaseEntry | None


@dataclass(frozen=True)
class Confirmation:
    """
    A `write` of the plan and the base update to apply when it succeeds.
    """

    write: Write
    update: BaseUpdate


@dataclass(frozen=True)
class Skip:
    """
    Both sides already agree, or something protects the server's copy.

    `base` is the update to the base that agreeing leaves to record, if any.
    """

    base: BaseUpdate | None = None


@dataclass(frozen=True)
class Put:
    """
    Write `op`, and tell why the write is not the whole story.

    `base` is what to record once the write succeeds.
    """

    op: Write
    notices: tuple[Notice, ...] = ()
    base: BaseUpdate | None = None


@dataclass(frozen=True)
class Prune:
    """
    Delete what the repository no longer holds, after the `before` writes
    the delete depends on.

    `base` is what to record once the delete succeeds.
    """

    op: Write
    before: tuple[Write, ...] = ()
    base: BaseUpdate | None = None
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class Keep:
    """
    Write nothing, and say why.
    """

    notice: Notice
    base: BaseUpdate | None = None


@dataclass(frozen=True)
class Pull:
    """
    The server changed and the repository did not: bring the change down.

    `change` tells a creation, an alteration and a removal apart. `remote` is
    the server's entry (`None` for a removal) and `fields` the top-level
    payload keys that differ from the base.
    """

    kind: EntityKind
    key: str
    change: Literal["create", "update", "delete"]
    fields: tuple[str, ...]
    remote: RemoteEntry | None = None


#: Why a `Conflict` is one.
type ConflictReason = Literal[
    "both-changed",
    "local-edited-remote-deleted",
    "local-deleted-remote-edited",
    "no-base",
    "rename",
    "link",
    "referenced",
]


@dataclass(frozen=True)
class Conflict:
    """
    Both sides moved apart and no rule says which one wins.

    `ours` holds the operations that settle it for the repository, empty when
    there is none: a `Put`, a `Prune`, or a `Put` and a `Prune` for a
    rename. `renamed_to` is the new key of a rename, `key` the old one.
    """

    kind: EntityKind
    key: str
    fields: tuple[str, ...]
    reason: ConflictReason
    ours: tuple[Put | Prune, ...] = ()
    renamed_to: str | None = None


@dataclass(frozen=True)
class OtherCli:
    """
    The server changed through another CLI: its source is in git, so the
    answer is a `git pull`, not a `Pull`.
    """

    kind: EntityKind
    key: str
    fields: tuple[str, ...]
    renamed_to: str | None = None


Decision = Skip | Put | Prune | Keep | Pull | Conflict | OtherCli


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
    return Put(_upsert_resource(local))


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
# Three-way sync
#
#: The `BaseState` key of the one course row.
COURSE_KEY = "course"

#: Payload fields that make up an entity's key, which a rename changes.
_SLUG = ("slug",)
_EVENT_KEY = ("week", "timeSlot")

_MISSING = object()


def event_key(week: int, time_slot: str) -> str:
    """
    The base key of a calendar event: `"<week>/<time slot>"`.
    """
    return f"{week}/{time_slot}"


def parse_event_key(key: str) -> tuple[int, str]:
    """
    The `(week, time slot)` of a base key made by `event_key`.

    Raises:
        ValueError: `key` is not of that form.
    """
    week, sep, time_slot = key.partition("/")
    if not sep or not time_slot:
        raise ValueError(f"not an event key: {key!r}")
    return int(week), time_slot


def diff_fields(a: Payload | None, b: Payload | None) -> tuple[str, ...]:
    """
    The sorted top-level keys whose values differ between two payloads, where
    a side that is `None` holds none.
    """
    left, right = a or {}, b or {}
    return tuple(
        sorted(
            key
            for key in left.keys() | right.keys()
            if left.get(key, _MISSING) != right.get(key, _MISSING)
        )
    )


def three_way(
    kind: EntityKind,
    key: str,
    local: Payload | None,
    base: BaseEntry | None,
    remote: RemoteEntry | None,
    *,
    local_ref: str | None = None,
    server_ref: str | None = None,
    put: Callable[[], Put],
    prune: Callable[[], Decision],
) -> Decision:
    """
    Decide one entity from its local, base and server payloads.

    `put` and `prune` build the write that moves the server to the local
    side; `prune` may answer a `Keep` when something protects the entity.
    `local_ref` and `server_ref` are the hash the local side computes and the
    one the server stores, used only when the base is absent: equal ones mean
    the server holds what this checkout last sent.

    The server changed through another CLI when its `rev` is not the base's;
    that takes precedence over a conflict. See the RFC's decision table.
    """

    stored = base

    def put_() -> Put:
        assert local is not None
        return replace(put(), base=BaseUpdate(kind, key, BaseEntry(local)))

    def prune_() -> Decision:
        decision = prune()
        if isinstance(decision, Prune):
            return replace(decision, base=BaseUpdate(kind, key, None))
        return decision

    def ours_prune() -> tuple[Put | Prune, ...]:
        decision = prune_()
        return (decision,) if isinstance(decision, Prune) else ()

    def adopt() -> Skip:
        assert local is not None and remote is not None
        entry = BaseEntry(local, remote.rev, remote.updated_at)
        stale = stored is None or (stored.payload, stored.rev) != (local, remote.rev)
        return Skip(BaseUpdate(kind, key, entry) if stale else None)

    if base is None:
        if local is None:
            if remote is None:
                return Skip()
            fields = diff_fields(None, remote.payload)
            if remote.rev is None:
                return Pull(kind, key, "create", fields, remote)
            return OtherCli(kind, key, fields)
        if remote is None:
            return put_()
        if server_ref is not None and server_ref == local_ref:
            base = BaseEntry(local, remote.rev, remote.updated_at)
        elif local == remote.payload:
            return adopt()
        else:
            fields = diff_fields(local, remote.payload)
            return Conflict(kind, key, fields, "no-base", ours=(put_(),))
    assert base is not None
    if local is None:
        if remote is None:
            return Skip(BaseUpdate(kind, key, None))
        if remote.payload == base.payload:
            return prune_()
        fields = diff_fields(base.payload, remote.payload)
        if remote.rev != base.rev:
            return OtherCli(kind, key, fields)
        return Conflict(kind, key, fields, "local-deleted-remote-edited", ours_prune())
    if remote is None:
        if local == base.payload:
            return Pull(kind, key, "delete", diff_fields(base.payload, None))
        fields = diff_fields(local, None)
        return Conflict(
            kind, key, fields, "local-edited-remote-deleted", ours=(put_(),)
        )
    local_changed = local != base.payload
    remote_changed = remote.payload != base.payload
    if local == remote.payload:
        return adopt()
    if not remote_changed:
        return put_()
    if remote.rev != base.rev:
        return OtherCli(kind, key, diff_fields(base.payload, remote.payload))
    if not local_changed:
        return Pull(
            kind, key, "update", diff_fields(base.payload, remote.payload), remote
        )
    return Conflict(
        kind, key, diff_fields(local, remote.payload), "both-changed", ours=(put_(),)
    )


def plan_sync(
    local: LocalState,
    base: BaseState,
    remote: ServerState,
    *,
    drop_roll_calls: bool = False,
    drop_repositories: bool = False,
    message: str | None = None,
) -> Plan:
    """
    Compare a repository, the base and the server by entity, by natural key,
    into a `Plan`.

    Each entity goes through `three_way` on payloads in the wire format:
    local through the `wire` constructors, base and server as stored. The
    plan keeps the order: course, repositories, calendar, resources,
    questions, grade columns. Repositories and grade columns stay one-way:
    the repository overwrites, and a grade column the server holds in a form
    other than the base's gets a `ServerDrifted` notice.

    The course row is never pulled for removal: a course missing on the
    server is written back.
    """
    return (
        _sync_course(local, base, remote)
        + plan_repositories(
            local, remote, drop_repositories=drop_repositories, message=message
        )
        + _sync_calendar(local, base, remote, drop_roll_calls=drop_roll_calls)
        + Plan.of(_sync_resources(local, base, remote))
        + Plan.of(_sync_questions(local, base, remote))
        + _sync_grades(local, base, remote)
    )


def _sync_course(local: LocalState, base: BaseState, remote: ServerState) -> Plan:
    start_at, end_at = _timestamp(local.start), _timestamp(local.end)
    ref = course_ref(local.description, start_at, end_at)
    payload = course_payload(local.key, local.description, local.start, local.end)
    op = UpsertCourse(
        key=local.key,
        description=local.description,
        start_at=start_at,
        end_at=end_at,
        ref=ref,
    )
    entry = remote.course if remote.course_exists else None
    if entry is None:
        return Plan.of(
            [Put(op, base=BaseUpdate("course", COURSE_KEY, BaseEntry(payload)))]
        )
    decision = three_way(
        "course",
        COURSE_KEY,
        payload,
        base.course.get(COURSE_KEY),
        entry,
        local_ref=ref,
        server_ref=entry.rev,
        put=lambda: Put(op),
        prune=lambda: Skip(),
    )
    return Plan.of([decision])


def _sync_kind(
    kind: EntityKind,
    local: Mapping[str, Payload],
    base: Mapping[str, BaseEntry],
    remote: Mapping[str, RemoteEntry],
    decide: Callable[
        [str, Payload | None, BaseEntry | None, RemoteEntry | None], Decision
    ],
    *,
    key_fields: tuple[str, ...] = _SLUG,
    extra: Iterable[str] = (),
) -> list[Decision]:
    """
    Run `decide` on every key of the three sides: local keys in local order,
    then the others in key order. A new local entity and a locally deleted
    one that are the same apart from their key, the deleted one changed on
    the server, become one rename. `extra` are keys with no payload that
    `decide` still has to see.
    """
    extras = [k for k in extra if k not in local]
    keys = [
        *local,
        *extras,
        *sorted((base.keys() | remote.keys()) - local.keys() - set(extras)),
    ]
    decisions = {
        key: decide(key, local.get(key), base.get(key), remote.get(key)) for key in keys
    }
    new = [
        key
        for key, decision in decisions.items()
        if isinstance(decision, Put)
        and key in local
        and key not in base
        and key not in remote
    ]
    for old, decision in list(decisions.items()):
        if old in local or old not in base or old not in remote:
            continue
        if not isinstance(decision, OtherCli) and not (
            isinstance(decision, Conflict)
            and decision.reason == "local-deleted-remote-edited"
        ):
            continue
        shape = _without(base[old].payload, key_fields)
        found = next((k for k in new if _without(local[k], key_fields) == shape), None)
        if found is None:
            continue
        new.remove(found)
        added = decisions.pop(found)
        if isinstance(decision, OtherCli):
            decisions[old] = replace(decision, renamed_to=found)
        elif isinstance(added, Put):
            decisions[old] = Conflict(
                kind,
                old,
                decision.fields,
                "rename",
                ours=(added, *decision.ours),
                renamed_to=found,
            )
    return list(decisions.values())


def _sync_resources(
    local: LocalState, base: BaseState, remote: ServerState
) -> list[Decision]:
    files = {file.slug: file for file in local.resources}
    excluded = _excluded(local, "resource")

    def decide(
        key: str,
        payload: Payload | None,
        entry: BaseEntry | None,
        server: RemoteEntry | None,
    ) -> Decision:
        if payload is None and key in excluded:
            return Skip()
        file = files.get(key)
        decision = three_way(
            "resource",
            key,
            payload,
            entry,
            server,
            local_ref=file.ref if file else None,
            server_ref=server.rev if server else None,
            put=lambda: Put(_upsert_resource(files[key])),
            prune=lambda: Prune(DeleteResource(slug=key)),
        )
        if not isinstance(decision, Pull):
            return decision
        ours = (
            (_put("resource", key, payload, _upsert_resource(file)),)
            if file is not None and payload is not None
            else ()
        )
        if decision.change == "delete":
            if file is not None and file.event is not None:
                return Conflict("resource", key, decision.fields, "referenced", ours)
            return decision
        assert decision.remote is not None
        stored = entry.payload if entry else payload
        before = resource_event_of(stored) if stored is not None else None
        if resource_event_of(decision.remote.payload) != before:
            return Conflict("resource", key, decision.fields, "link", ours)
        return decision

    return _sync_kind(
        "resource",
        {slug: resource_payload(file) for slug, file in files.items()},
        base.resources,
        remote.resources,
        decide,
    )


def _sync_questions(
    local: LocalState, base: BaseState, remote: ServerState
) -> list[Decision]:
    files = {q.slug: q for q in local.questions}
    excluded = _excluded(local, "question")
    entries = {slug: question.entry for slug, question in remote.questions.items()}

    def decide(
        key: str,
        payload: Payload | None,
        entry: BaseEntry | None,
        server: RemoteEntry | None,
    ) -> Decision:
        if payload is None and key in excluded:
            return Skip()
        file = files.get(key)
        if isinstance(file, InvalidQuestion):
            return Keep(Rejected(slug=file.slug, path=file.path, reason=file.reason))
        question = remote.questions.get(key)
        if isinstance(file, QuestionFile):
            status = (
                join_status(file.status, question.status) if question else file.status
            )
            notices: tuple[Notice, ...] = ()
            if question is not None and (file.status, question.status) == (
                "DRAFT",
                "PUBLISHED",
            ):
                notices = (
                    KeptDraftPublished(
                        slug=file.slug, status=question.status, path=file.path
                    ),
                )

            def put() -> Put:
                return Put(_upsert_question(file, status), notices)

        else:

            def put() -> Put:
                raise AssertionError("a missing question is never written")

        decision = three_way(
            "question",
            key,
            payload,
            entry,
            server,
            local_ref=file.version if file else None,
            server_ref=question.version if question else None,
            put=put,
            prune=lambda: Prune(DeleteQuestion(slug=key)),
        )
        if not isinstance(decision, Skip) or file is None or question is None:
            return decision
        if status != question.status:
            assert payload is not None
            return _put(
                "question", key, payload, _upsert_question(file, status), notices
            )
        if notices:
            return Keep(notices[0], decision.base)
        return decision

    return _sync_kind(
        "question",
        {
            slug: question_payload(file)
            for slug, file in files.items()
            if isinstance(file, QuestionFile)
        },
        base.questions,
        entries,
        decide,
        extra=[q.slug for q in local.questions if isinstance(q, InvalidQuestion)],
    )


def _sync_calendar(
    local: LocalState,
    base: BaseState,
    remote: ServerState,
    *,
    drop_roll_calls: bool,
) -> Plan:
    """
    The calendar half of a three-way plan, ordered as `plan_calendar` is.
    """
    events = {event_key(e.week, e.time_slot): e for e in local.events}
    servers = {event_key(*key): ev for key, ev in remote.calendar_events.items()}
    entries = {key: ev.entry for key, ev in servers.items() if ev.kind != "CANCELLED"}

    def decide_event(
        key: str,
        payload: Payload | None,
        entry: BaseEntry | None,
        server: RemoteEntry | None,
    ) -> Decision:
        week, time_slot = parse_event_key(key)
        found = servers.get(key)
        if found is not None and found.kind == "CANCELLED":
            return Keep(KeptCancelled(week=week, time_slot=time_slot))
        event = events.get(key)
        return three_way(
            "calendar_event",
            key,
            payload,
            entry,
            server,
            local_ref=event.ref if event else None,
            server_ref=server.rev if server else None,
            put=lambda: Put(UpsertCalendarEvent(event=events[key])),
            prune=lambda: merge_event(
                (week, time_slot), None, found, drop_roll_calls=drop_roll_calls
            ),
        )

    cancelled = {
        k: RemoteEntry({}) for k, ev in servers.items() if ev.kind == "CANCELLED"
    }
    decided = _sync_kind(
        "calendar_event",
        {key: event_payload(event) for key, event in events.items()},
        base.calendar_events,
        {**entries, **cancelled},
        decide_event,
        key_fields=_EVENT_KEY,
    )
    pinned, pin_notices = _pin_slots(decided, {slot.slug for slot in local.slots})
    deleted = {
        (d.op.week, d.op.time_slot)
        for d in _only(decided, Prune)
        if isinstance(d.op, DeleteCalendarEvent)
    }
    held: dict[str, list[str]] = {}
    for week, time_slot in sorted(
        {*remote.calendar_events, *(parse_event_key(k) for k in events)} - deleted
    ):
        held.setdefault(time_slot, []).append(event_key(week, time_slot))
    slots = {slot.slug: slot for slot in local.slots}

    def decide_slot(
        key: str,
        payload: Payload | None,
        entry: BaseEntry | None,
        server: RemoteEntry | None,
    ) -> Decision:
        if payload is None and key in pinned:
            return Skip()
        decision = three_way(
            "time_slot",
            key,
            payload,
            entry,
            server,
            put=lambda: Put(UpsertTimeSlot(slot=slots[key])),
            prune=lambda: Prune(DeleteTimeSlot(slug=key)),
        )
        if isinstance(decision, Prune) and key in held:
            return Conflict("time_slot", key, tuple(held[key]), "referenced")
        return decision

    decided_slots = _sync_kind(
        "time_slot",
        {key: time_slot_payload(slot) for key, slot in slots.items()},
        base.time_slots,
        remote.time_slots,
        decide_slot,
    )
    reported = [
        d
        for d in decided
        if isinstance(d, Keep) and not isinstance(d.notice, KeptCancelled)
    ]
    rest = [
        d
        for d in (*decided, *decided_slots)
        if isinstance(d, Skip | Pull | Conflict | OtherCli)
    ]
    return Plan.of(
        [
            *_only(decided, Prune),
            *_only(decided_slots, Prune),
            *_only(decided_slots, Put),
            *_only(decided, Put),
            *reported,
            *rest,
        ]
    ) + Plan(notices=pin_notices)


def _sync_grades(local: LocalState, base: BaseState, remote: ServerState) -> Plan:
    """
    The grade columns of a plan: the repository overwrites the server, and a
    column the server changed since the base is overwritten with a notice.
    """
    if local.grade_columns is None:
        return Plan()
    columns = {column.slug: column for column in local.grade_columns}
    payloads = {slug: grade_column_payload(column) for slug, column in columns.items()}
    decisions: list[Decision] = []
    keys = [
        *columns,
        *sorted(
            (base.grade_columns.keys() | remote.grade_columns.keys()) - columns.keys()
        ),
    ]
    for key in keys:
        entry, server = base.grade_columns.get(key), remote.grade_columns.get(key)
        column = columns.get(key)
        if column is None:
            if server is None:
                if entry is not None:
                    decisions.append(Skip(BaseUpdate("grade_column", key, None)))
                continue
            fields = diff_fields(entry.payload if entry else None, server.payload)
            drift = (ServerDrifted("grade_column", key, fields),) if fields else ()
            decisions.append(
                Prune(
                    DeleteGradeColumn(slug=key),
                    base=BaseUpdate("grade_column", key, None),
                    notices=drift,
                )
            )
            continue
        payload = payloads[key]
        if server is not None and server.payload == payload:
            stale = entry is None or (entry.payload, entry.rev) != (payload, server.rev)
            update = BaseUpdate(
                "grade_column", key, BaseEntry(payload, server.rev, server.updated_at)
            )
            decisions.append(Skip(update if stale else None))
            continue
        drift = ()
        if server is not None:
            if entry is not None and server.payload != entry.payload:
                drift = (
                    ServerDrifted(
                        "grade_column", key, diff_fields(entry.payload, server.payload)
                    ),
                )
            elif entry is None and server.rev in (None, column.rev):
                drift = (
                    ServerDrifted(
                        "grade_column", key, diff_fields(payload, server.payload)
                    ),
                )
        put = _put("grade_column", key, payload, UpsertGradeColumn(column=column))
        decisions.append(replace(put, notices=drift))
    return Plan.of(decisions)


#
# Utilities
#
def _put(
    kind: EntityKind,
    key: str,
    payload: Payload,
    op: Write,
    notices: tuple[Notice, ...] = (),
) -> Put:
    """
    A `Put` of `op` that records `payload` in the base once it succeeds.
    """
    return Put(op, notices, BaseUpdate(kind, key, BaseEntry(payload)))


def _without(payload: Payload, fields: tuple[str, ...]) -> Payload:
    return {k: v for k, v in payload.items() if k not in fields}


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


def _upsert_resource(file: ResourceFile) -> UpsertResource:
    return UpsertResource(
        slug=file.slug,
        title=file.title,
        description=file.description,
        data=file.data,
        ref=file.ref,
        path=file.path,
        event=file.event,
    )


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
