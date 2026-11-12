"""
`diff_keyed`, the per-entity `merge_*` functions and the properties they
give `plan_push`: replanning after applying a plan plans nothing, a push
never lowers a question's status, a `CANCELLED` event is absorbed, and a
pinned slot is noticed at most once.

`apply` below is a pure model of the server: it folds a plan's writes into
a `ServerState`, with no HTTP and no ids.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import mdq
from hypothesis import given, settings
from hypothesis import strategies as st

from codehood.models.repo import CourseKey
from codehood.push.calendar import Duration, Event, EventKey, TimeOfDay, TimeSlot
from codehood.push.exclude import ExcludedFile
from codehood.push.grades import GradeColumn
from codehood.push.plan import (
    STATUS_ORDER,
    DeleteCalendarEvent,
    DeleteGradeColumn,
    DeleteQuestion,
    DeleteRepository,
    DeleteResource,
    DeleteRollCall,
    DeleteTimeSlot,
    Keep,
    KeptCancelled,
    KeptDraftPublished,
    KeptForRollCall,
    KeptPinnedSlot,
    LocalState,
    Plan,
    Prune,
    Put,
    Rejected,
    ServerEvent,
    ServerQuestion,
    ServerState,
    Skip,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertGradeColumn,
    UpsertQuestion,
    UpsertRepository,
    UpsertResource,
    UpsertTimeSlot,
    diff_keyed,
    join_status,
    merge_event,
    merge_question,
    plan_push,
    protect,
)
from codehood.push.project import RemoteEntry
from codehood.push.question import InvalidQuestion, QuestionFile
from codehood.push.repository import RepositoryEntry, RepositoryTree
from codehood.push.resource import MdData, ResourceFile, content_ref
from codehood.push.wire import Payload, time_slot_payload

KEY = CourseKey("cs101", "ada", "2026-1")
QUESTION = mdq.parse(
    "---\ntitle: Q\n---\n\nWhat is 2 + 2?\n\n- [ ] 3\n- [*] 4\n- [ ] 5\n",
    kind="question",
    ids="fill",
)


#
# diff_keyed
#
def test_diff_keyed_walks_local_keys_in_order_then_server_only_keys_sorted():
    calls = []

    def merge(key, local, server):
        calls.append((key, local, server))
        return Skip()

    list(diff_keyed({"z": 1, "a": 2}, {"a": 20, "y": 30, "b": 40}, merge))

    assert calls == [("z", 1, None), ("a", 2, 20), ("b", None, 40), ("y", None, 30)]


def test_diff_keyed_yields_what_merge_decides():
    decisions = list(diff_keyed({"a": 1}, {}, lambda k, local, server: Skip()))
    assert decisions == [Skip()]


def test_protect_skips_a_server_only_key_it_guards():
    merge = protect(lambda key, local, server: Prune(DeleteResource(key)), {"keep"})

    assert merge("keep", None, "ref") == Skip()
    assert merge("drop", None, "ref") == Prune(DeleteResource("drop"))
    assert merge("keep", object(), "ref") == Prune(DeleteResource("keep"))


#
# merge_question
#
def _question(version="v1", status="PUBLISHED") -> QuestionFile:
    return QuestionFile(
        slug="q",
        version=version,
        question=QUESTION,
        path=Path("questions/q.mdq"),
        status=status,
    )


def test_join_status_is_the_higher_one():
    assert join_status("DRAFT", "PUBLISHED") == "PUBLISHED"
    assert join_status("PUBLISHED", "DRAFT") == "PUBLISHED"
    assert join_status("PUBLISHED", "HIDDEN") == "HIDDEN"
    assert join_status("HIDDEN", "DRAFT") == "HIDDEN"


def test_a_hidden_question_still_receives_new_content_and_stays_hidden():
    decision = merge_question(
        "q", _question("v2", "DRAFT"), ServerQuestion("v1", "HIDDEN")
    )
    assert isinstance(decision, Put)
    assert decision.op.status == "HIDDEN"
    assert decision.notices == ()


def test_a_draft_file_over_a_published_question_writes_and_notices():
    decision = merge_question(
        "q", _question("v2", "DRAFT"), ServerQuestion("v1", "PUBLISHED")
    )
    assert isinstance(decision, Put)
    assert decision.op.status == "PUBLISHED"
    assert decision.notices == (
        KeptDraftPublished(slug="q", status="PUBLISHED", path=Path("questions/q.mdq")),
    )


def test_an_unchanged_draft_over_a_published_question_only_notices():
    decision = merge_question(
        "q", _question("v1", "DRAFT"), ServerQuestion("v1", "PUBLISHED")
    )
    assert isinstance(decision, Keep)
    assert isinstance(decision.notice, KeptDraftPublished)


def test_a_draft_file_over_a_hidden_question_does_not_notice():
    decision = merge_question(
        "q", _question("v1", "DRAFT"), ServerQuestion("v1", "HIDDEN")
    )
    assert decision == Skip()


def test_an_invalid_file_is_rejected_whatever_the_server_holds():
    invalid = InvalidQuestion(slug="q", path=Path("q.mdq"), reason="bad")
    for server in (None, ServerQuestion("v1", "PUBLISHED")):
        assert merge_question("q", invalid, server) == Keep(
            Rejected(slug="q", path=Path("q.mdq"), reason="bad")
        )


@given(
    local=st.sampled_from(("DRAFT", "PUBLISHED")),
    remote=st.sampled_from(STATUS_ORDER),
    same_version=st.booleans(),
)
def test_a_question_is_never_written_below_the_server_status(
    local, remote, same_version
):
    server = ServerQuestion("v1", remote)
    decision = merge_question(
        "q", _question("v1" if same_version else "v2", local), server
    )
    if isinstance(decision, Put):
        assert STATUS_ORDER.index(decision.op.status) >= STATUS_ORDER.index(remote)
    notices = decision.notices if isinstance(decision, Put) else ()
    if isinstance(decision, Keep):
        notices = (decision.notice,)
    assert bool(notices) == (local == "DRAFT" and remote == "PUBLISHED")


#
# merge_event
#
@given(
    local=st.one_of(st.none(), st.just(Event(0, "mon", "t"))),
    attendances=st.sampled_from((None, 0, 5)),
    drop=st.booleans(),
)
def test_a_cancelled_server_event_is_absorbed(local, attendances, drop):
    server = ServerEvent(ref="r", kind="CANCELLED", attendances=attendances)
    decision = merge_event((0, "mon"), local, server, drop_roll_calls=drop)
    assert decision == Keep(KeptCancelled(week=0, time_slot="mon"))


def test_an_event_with_a_roll_call_is_kept_unless_the_roll_call_is_dropped():
    server = ServerEvent(ref="r", kind="REGULAR", attendances=3)
    assert merge_event((5, "mon"), None, server, drop_roll_calls=False) == Keep(
        KeptForRollCall(week=5, time_slot="mon", attendances=3)
    )
    assert merge_event((5, "mon"), None, server, drop_roll_calls=True) == Prune(
        DeleteCalendarEvent(5, "mon"), before=(DeleteRollCall(5, "mon"),)
    )


def test_an_event_whose_marker_matches_is_skipped():
    event = Event(0, "mon", "t")
    server = ServerEvent(ref=event.ref, kind="REGULAR")
    assert merge_event((0, "mon"), event, server, drop_roll_calls=False) == Skip()


#
# plan_push properties
#
SLUGS = ("a", "b", "c")
SLOT_DAYS = {"mon": "MONDAY", "tue": "TUESDAY", "wed": "WEDNESDAY"}


def _slot(slug: str) -> TimeSlot:
    return TimeSlot(
        slug=slug,
        day=SLOT_DAYS[slug],
        start=TimeOfDay(hour=9, minute=0),
        duration=Duration(hours=1, minutes=0),
    )


def _resource(slug: str, body: str, event: EventKey | None) -> ResourceFile:
    data = MdData(content=body)
    return ResourceFile(
        slug=slug,
        title=slug,
        description=None,
        data=data,
        ref=content_ref(slug, None, data),
        path=Path(f"resources/{slug}.md"),
        event=event,
    )


def _tree(slug: str, sha: str) -> RepositoryTree:
    entry = RepositoryEntry(
        path="a.py",
        mode="100644",
        sha256="0" * 64,
        git_sha="1" * 40,
        size=1,
        source=Path("/nowhere/a.py"),
    )
    return RepositoryTree(slug=slug, entries=(entry,), tree_sha=sha * 40)


event_keys = st.tuples(st.integers(0, 2), st.sampled_from(tuple(SLOT_DAYS)))
optional_event_key = st.one_of(
    st.none(), event_keys.map(lambda k: EventKey(week=k[0], time_slot=k[1]))
)


@st.composite
def local_states(draw) -> LocalState:
    slots = tuple(
        _slot(slug)
        for slug in draw(st.lists(st.sampled_from(tuple(SLOT_DAYS)), unique=True))
    )
    keys = draw(st.lists(event_keys, unique=True, max_size=4))
    events = tuple(
        Event(
            week,
            slot,
            draw(st.sampled_from(("x", "y"))),
            kind=draw(st.sampled_from(("REGULAR", "HOLIDAY", "CANCELLED"))),
        )
        for week, slot in keys
    )
    resources = tuple(
        _resource(slug, draw(st.sampled_from(("x", "y"))), draw(optional_event_key))
        for slug in draw(st.lists(st.sampled_from(SLUGS), unique=True))
    )
    questions: list[QuestionFile | InvalidQuestion] = []
    for slug in draw(st.lists(st.sampled_from(SLUGS), unique=True)):
        if draw(st.integers(0, 5)) == 0:
            questions.append(InvalidQuestion(slug, Path(f"{slug}.mdq"), "bad"))
        else:
            questions.append(
                QuestionFile(
                    slug=slug,
                    version=draw(st.sampled_from(("v1", "v2"))),
                    question=QUESTION,
                    path=Path(f"questions/{slug}.mdq"),
                    status=draw(st.sampled_from(("DRAFT", "PUBLISHED"))),
                )
            )
    columns = draw(
        st.one_of(
            st.none(),
            st.lists(st.sampled_from(SLUGS), unique=True).map(
                lambda slugs: tuple(
                    GradeColumn(slug, slug, "number", i, (("ana", 1.0),))
                    for i, slug in enumerate(slugs)
                )
            ),
        )
    )
    repositories = tuple(
        _tree(slug, draw(st.sampled_from("ab")))
        for slug in draw(st.lists(st.sampled_from(SLUGS), unique=True))
    )
    excluded = tuple(
        ExcludedFile(kind, slug, f"{kind}s/{slug}")
        for kind in ("question", "resource")
        for slug in draw(st.lists(st.sampled_from(SLUGS), unique=True, max_size=2))
    )
    return LocalState(
        key=KEY,
        description=draw(st.sampled_from(("d", "e"))),
        start=date(2026, 1, 1),
        end=date(2026, 6, 1),
        slots=slots,
        events=events,
        resources=resources,
        questions=tuple(questions),
        grade_columns=columns,
        repositories=repositories,
        excluded=excluded,
    )


@st.composite
def server_states(draw) -> ServerState:
    slugs = st.lists(st.sampled_from(SLUGS), unique=True)
    resource_slugs = draw(slugs)
    return ServerState(
        course_exists=draw(st.booleans()),
        course=draw(st.sampled_from((None, RemoteEntry({}, rev="stale")))),
        resources={
            slug: RemoteEntry(
                {"event": _event_payload(draw(optional_event_key))},
                rev=draw(st.sampled_from(("stale", "x"))),
            )
            for slug in resource_slugs
        },
        questions={
            slug: ServerQuestion(
                draw(st.sampled_from(("v1", "v2"))), draw(st.sampled_from(STATUS_ORDER))
            )
            for slug in draw(slugs)
        },
        time_slots={
            slug: _slot_entry(draw(st.sampled_from((_stale_slot(slug), _slot(slug)))))
            for slug in draw(st.lists(st.sampled_from(tuple(SLOT_DAYS)), unique=True))
        },
        calendar_events={
            key: ServerEvent(
                ref=draw(st.sampled_from(("stale", Event(*key, "x").ref))),
                kind=draw(st.sampled_from(("REGULAR", "HOLIDAY", "CANCELLED"))),
                attendances=draw(st.sampled_from((None, 0, 4))),
            )
            for key in draw(st.lists(event_keys, unique=True, max_size=4))
        },
        grade_columns={slug: RemoteEntry({}, rev="stale") for slug in draw(slugs)},
        repositories={
            slug: draw(st.sampled_from((None, "a" * 40))) for slug in draw(slugs)
        },
    )


def _event_payload(key: EventKey | None) -> Payload | None:
    return None if key is None else {"week": key.week, "timeSlot": key.time_slot}


def _slot_entry(slot: TimeSlot) -> RemoteEntry:
    return RemoteEntry(time_slot_payload(slot))


def _stale_slot(slug: str) -> TimeSlot:
    """
    A slot no local one equals.
    """
    return replace(_slot(slug), title="stale")


def apply(server: ServerState, plan: Plan) -> ServerState:
    """
    A pure model of the server: fold the writes of `plan` into `server`.
    """
    resources = dict(server.resources)
    questions = dict(server.questions)
    time_slots = dict(server.time_slots)
    events = dict(server.calendar_events)
    columns = dict(server.grade_columns)
    repositories = dict(server.repositories)
    course, exists = server.course, server.course_exists
    for op in plan.writes:
        match op:
            case UpsertCourse():
                course, exists = RemoteEntry({}, rev=op.ref), True
            case UpsertResource():
                resources[op.slug] = RemoteEntry(
                    {"event": _event_payload(op.event)}, rev=op.ref
                )
            case DeleteResource():
                resources.pop(op.slug, None)
            case UpsertQuestion():
                questions[op.slug] = ServerQuestion(op.version, op.status)
            case DeleteQuestion():
                questions.pop(op.slug, None)
            case UpsertTimeSlot():
                time_slots[op.slot.slug] = _slot_entry(op.slot)
            case DeleteTimeSlot():
                time_slots.pop(op.slug, None)
            case UpsertCalendarEvent():
                key = (op.event.week, op.event.time_slot)
                previous = events.get(key)
                events[key] = ServerEvent(
                    ref=op.event.ref,
                    kind=op.event.kind,
                    attendances=previous.attendances if previous else None,
                )
            case DeleteRollCall():
                key = (op.week, op.time_slot)
                events[key] = replace(events[key], attendances=None)
            case DeleteCalendarEvent():
                events.pop((op.week, op.time_slot), None)
            case UpsertGradeColumn():
                columns[op.column.slug] = RemoteEntry({}, rev=op.column.rev)
            case DeleteGradeColumn():
                columns.pop(op.slug, None)
            case UpsertRepository():
                repositories[op.tree.slug] = op.tree.tree_sha
            case DeleteRepository():
                repositories.pop(op.slug, None)
    return ServerState(
        course_exists=exists,
        course=course,
        resources=resources,
        questions=questions,
        time_slots=time_slots,
        calendar_events=events,
        grade_columns=columns,
        repositories=repositories,
    )


FLAGS = {"drop_roll_calls": st.booleans(), "drop_repositories": st.booleans()}


@given(local=local_states(), server=server_states(), **FLAGS)
@settings(max_examples=300)
def test_replanning_after_applying_a_plan_writes_nothing(
    local, server, drop_roll_calls, drop_repositories
):
    flags = {"drop_roll_calls": drop_roll_calls, "drop_repositories": drop_repositories}
    plan = plan_push(local, server, **flags)

    again = plan_push(local, apply(server, plan), **flags)

    assert again.writes == ()


@given(local=local_states(), server=server_states())
@settings(max_examples=300)
def test_a_push_never_lowers_the_status_of_a_question(local, server):
    after = apply(server, plan_push(local, server))

    for slug, before in server.questions.items():
        if slug in after.questions:
            assert STATUS_ORDER.index(
                after.questions[slug].status
            ) >= STATUS_ORDER.index(before.status)


@given(local=local_states(), server=server_states(), **FLAGS)
@settings(max_examples=300)
def test_a_cancelled_server_event_is_never_written_or_pruned(
    local, server, drop_roll_calls, drop_repositories
):
    plan = plan_push(
        local,
        server,
        drop_roll_calls=drop_roll_calls,
        drop_repositories=drop_repositories,
    )
    cancelled = {
        key
        for key, event in server.calendar_events.items()
        if event.kind == "CANCELLED"
    }
    touched = set()
    for op in plan.writes:
        if isinstance(op, UpsertCalendarEvent):
            touched.add((op.event.week, op.event.time_slot))
        elif isinstance(op, DeleteCalendarEvent | DeleteRollCall):
            touched.add((op.week, op.time_slot))

    assert touched.isdisjoint(cancelled)
    assert apply(server, plan).calendar_events.keys() >= cancelled


@given(local=local_states(), server=server_states(), **FLAGS)
@settings(max_examples=300)
def test_a_pinned_slot_is_noticed_at_most_once(
    local, server, drop_roll_calls, drop_repositories
):
    plan = plan_push(
        local,
        server,
        drop_roll_calls=drop_roll_calls,
        drop_repositories=drop_repositories,
    )

    slugs = [n.slug for n in plan.notices if isinstance(n, KeptPinnedSlot)]
    assert len(slugs) == len(set(slugs))
    assert not any(isinstance(n, KeptCancelled) for n in plan.notices)
    pruned = {op.slug for op in plan.writes if isinstance(op, DeleteTimeSlot)}
    assert pruned.isdisjoint(slugs)


@given(local=local_states(), server=server_states())
@settings(max_examples=200)
def test_an_excluded_file_is_never_pruned(local, server):
    plan = plan_push(local, server)

    excluded = {(file.kind, file.slug) for file in local.excluded}
    local_resources = {r.slug for r in local.resources}
    local_questions = {q.slug for q in local.questions}
    for op in plan.writes:
        if isinstance(op, DeleteResource) and op.slug not in local_resources:
            assert ("resource", op.slug) not in excluded
        if isinstance(op, DeleteQuestion) and op.slug not in local_questions:
            assert ("question", op.slug) not in excluded
