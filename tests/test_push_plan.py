"""
Tests for `codehood.push.plan.plan_push` and `plan_calendar`, the pure
planner. See `dev/specs/to-do/push.md`'s "Architecture" and "Proof"
sections, `dev/specs/to-do/push-calendar.handoff.md`'s `push/plan.py`
section, testing strategy and acceptance criteria, and
`docs/design/mapping-local-filesystem.md`'s "Calendar" and "Sync
preflight".

`plan_push` now takes two frozen dataclasses, `LocalState` and
`ServerState`, rather than nine positional arguments -- every test in this
file builds those directly. Resource and question behavior is unchanged
by the calendar work; only the call shape moved.

Example-based tests assert on the exact list of ops for a small fixture.
The property tests are the spec's own acceptance criteria: "Re-running
push against unchanged state plans nothing" for resources/questions, and
acceptance criterion 6, "a second `plan_push` against the state the first
one wrote yields only `UpsertCourse`", for the calendar half.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import mdq
from hypothesis import given, settings
from hypothesis import strategies as st

from codehood.models.repo import CourseKey
from codehood.push.calendar import Duration, Event, TimeOfDay, TimeSlot
from codehood.push.plan import (
    DeleteCalendarEvent,
    DeleteQuestion,
    DeleteResource,
    DeleteRollCall,
    DeleteTimeSlot,
    KeptDraftPublished,
    KeptForRollCall,
    KeptPinnedSlot,
    LocalState,
    Plan,
    Rejected,
    ServerEvent,
    ServerQuestion,
    ServerState,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertQuestion,
    UpsertResource,
    UpsertTimeSlot,
    course_ref,
    plan_calendar,
    plan_push,
)
from codehood.push.question import InvalidQuestion, QuestionFile, question_version
from codehood.push.resource import MdData, ResourceFile, content_ref

EXAMPLE_MDQ = """---
title: Example question
---

What is 2 + 2?

- [ ] 3
- [*] 4
- [ ] 5
"""

DESCRIPTION = "Course description."
START = date(2026, 1, 1)
END = date(2026, 6, 1)
DISCIPLINE = "cs101"
COURSE = "ada_2026-1"
KEY = CourseKey(DISCIPLINE, "ada", "2026-1")


def _local(
    resources=(),
    *,
    questions=(),
    slots=(),
    events=(),
    description=DESCRIPTION,
    start=START,
    end=END,
) -> LocalState:
    return LocalState(
        key=KEY,
        description=description,
        start=start,
        end=end,
        slots=tuple(slots),
        events=tuple(events),
        resources=tuple(resources),
        questions=tuple(questions),
    )


def _server(
    *,
    course_exists=True,
    course_rev=None,
    resources=None,
    questions=None,
    time_slots=None,
    calendar_events=None,
) -> ServerState:
    return ServerState(
        course_exists=course_exists,
        course_rev=course_rev,
        resources=resources or {},
        # A bare version is a published question, as an unmarked file is.
        questions={
            slug: v if isinstance(v, ServerQuestion) else ServerQuestion(v, "PUBLISHED")
            for slug, v in (questions or {}).items()
        },
        time_slots=time_slots or {},
        calendar_events=calendar_events or {},
    )


def _writes(plan: Plan) -> list:
    return list(plan.writes)


def _push(*args, **kwargs) -> list:
    """The writes of `plan_push`."""
    return _writes(plan_push(*args, **kwargs))


def _calendar(*args, **kwargs) -> list:
    """The writes of `plan_calendar`."""
    return _writes(plan_calendar(*args, **kwargs))


def _full_plan(resources, server_course_exists, server_resources, **kwargs) -> Plan:
    """
    Every call below builds the two `plan_push` inputs directly. `**kwargs`
    forwards `questions`/`server_questions`, matching every caller from
    before the calendar half landed.
    """
    questions = kwargs.pop("questions", ())
    server_questions = kwargs.pop("server_questions", None)
    return plan_push(
        _local(resources, questions=questions),
        _server(
            course_exists=server_course_exists,
            resources=server_resources,
            questions=server_questions,
        ),
    )


def _plan(*args, **kwargs) -> list:
    return _writes(_full_plan(*args, **kwargs))


def _resource(slug: str, data: str = "body") -> ResourceFile:
    content = MdData(content=data)
    return ResourceFile(
        slug=slug,
        title=slug,
        description=None,
        data=content,
        ref=content_ref(slug, None, content),
        path=Path(f"resources/{slug}.md"),
    )


def _course_op(*, plan) -> UpsertCourse:
    [course_op] = [op for op in plan if isinstance(op, UpsertCourse)]
    return course_op


def _question(
    slug: str, body: str = EXAMPLE_MDQ, *, draft: bool = False
) -> QuestionFile:
    raw = body.encode("utf-8")
    return QuestionFile(
        slug=slug,
        version=question_version(raw),
        question=mdq.parse(body, kind="question", ids="fill"),
        path=Path(f"questions/{'_' if draft else ''}{slug}.md"),
        status="DRAFT" if draft else "PUBLISHED",
    )


#
# UpsertCourse: when the course is new or its rev is stale; dates come from
# `calendar.md`.
#
def test_plan_always_upserts_the_course():
    """
    "Every write is a PUT" -- the course row is upserted whether or not it
    already exists server-side; `plan_push` never branches on
    create-versus-update.
    """
    for exists in (False, True):
        plan = list(_plan([], exists, {}))
        course_op = _course_op(plan=plan)
        assert course_op.discipline == DISCIPLINE
        assert course_op.course == COURSE
        assert course_op.description == "Course description."
        assert course_op.start_at == "2026-01-01T00:00:00.000Z"
        assert course_op.end_at == "2026-06-01T00:00:00.000Z"


#
# Resources: added, unchanged, changed, removed.
#
def test_new_resource_is_upserted():
    resource = _resource("week1-slides")
    plan = list(_plan([resource], True, {}))
    resource_ops = [op for op in plan if isinstance(op, UpsertResource)]
    assert [op.slug for op in resource_ops] == ["week1-slides"]
    assert resource_ops[0].ref == resource.ref


def test_unchanged_resource_produces_no_op():
    resource = _resource("week1-slides")
    server_resources = {"week1-slides": resource.ref}
    plan = list(_plan([resource], True, server_resources))
    resource_ops = [
        op for op in plan if isinstance(op, (UpsertResource, DeleteResource))
    ]
    assert resource_ops == []


def test_changed_resource_is_upserted():
    resource = _resource("week1-slides", data="new body")
    server_resources = {"week1-slides": "stale-hash"}
    plan = list(_plan([resource], True, server_resources))
    resource_ops = [op for op in plan if isinstance(op, UpsertResource)]
    assert [op.slug for op in resource_ops] == ["week1-slides"]


def test_resource_missing_locally_is_deleted():
    server_resources = {"week1-slides": "some-hash"}
    plan = list(_plan([], True, server_resources))
    delete_ops = [op for op in plan if isinstance(op, DeleteResource)]
    assert [op.slug for op in delete_ops] == ["week1-slides"]


def test_add_change_and_delete_together_map_one_to_one():
    unchanged = _resource("unchanged")
    changed = _resource("changed", data="new body")
    added = _resource("added")
    server_resources = {
        "unchanged": unchanged.ref,
        "changed": "stale-hash",
        "removed": "some-hash",
    }
    plan = list(_plan([unchanged, changed, added], True, server_resources))
    upserts = {op.slug for op in plan if isinstance(op, UpsertResource)}
    deletes = {op.slug for op in plan if isinstance(op, DeleteResource)}
    assert upserts == {"changed", "added"}
    assert deletes == {"removed"}


#
# Convergence: apply the plan to a fake server, re-plan, resource ops empty.
#
def _apply(plan, server_course_exists: bool, server_resources: dict[str, str]):
    """
    A minimal fake server: `UpsertResource` sets the slug's hash,
    `DeleteResource` removes it, `UpsertCourse` marks the course as
    existing. No HTTP, no ids -- exactly what the ops themselves carry.
    """
    server_resources = dict(server_resources)
    for op in plan:
        if isinstance(op, UpsertCourse):
            server_course_exists = True
        elif isinstance(op, UpsertResource):
            server_resources[op.slug] = op.ref
        elif isinstance(op, DeleteResource):
            server_resources.pop(op.slug, None)
    return server_course_exists, server_resources


_SLUGS = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=8
)
_BODIES = st.text(min_size=0, max_size=40)


@st.composite
def _resource_lists(draw):
    slugs = draw(st.lists(_SLUGS, min_size=0, max_size=6, unique=True))
    return [_resource(slug, data=draw(_BODIES)) for slug in slugs]


@given(resources=_resource_lists(), server_course_exists=st.booleans())
@settings(max_examples=100)
def test_replanning_after_applying_converges_to_no_resource_ops(
    resources, server_course_exists
):
    """
    A sync converges when re-run: once a plan's ops have been
    applied, planning again against the same repository yields no more
    `UpsertResource`/`DeleteResource` ops.

    `UpsertCourse` is not part of this invariant: the design decision
    "every write is a PUT... push never branches on create-versus-update"
    means the course op is unconditional on every push.
    """
    first_plan = list(_plan(resources, server_course_exists, {}))
    new_exists, new_resources = _apply(first_plan, server_course_exists, {})

    second_plan = list(_plan(resources, new_exists, new_resources))
    resource_ops = [
        op for op in second_plan if isinstance(op, (UpsertResource, DeleteResource))
    ]
    assert resource_ops == []


#
# Questions: added, unchanged, changed, removed -- see
# `dev/specs/to-do/push-questions.md`, `plan_push`'s contract: "A
# question whose `version` equals `server_questions[slug]` is skipped."
#
def test_new_question_is_upserted():
    question = _question("week1-big-o")
    plan = list(_plan([], True, {}, questions=[question], server_questions={}))
    question_ops = [op for op in plan if isinstance(op, UpsertQuestion)]
    assert [op.slug for op in question_ops] == ["week1-big-o"]
    assert question_ops[0].version == question.version
    assert question_ops[0].question is question.question
    assert question_ops[0].path == question.path


def test_unchanged_question_produces_no_op():
    question = _question("week1-big-o")
    server_questions = {"week1-big-o": question.version}
    plan = list(
        _plan([], True, {}, questions=[question], server_questions=server_questions)
    )
    question_ops = [
        op for op in plan if isinstance(op, (UpsertQuestion, DeleteQuestion))
    ]
    assert question_ops == []


def test_changed_question_is_upserted():
    question = _question(
        "week1-big-o",
        body=EXAMPLE_MDQ.replace("2 + 2", "3 + 3"),
    )
    server_questions = {"week1-big-o": "md5:stale"}
    plan = list(
        _plan([], True, {}, questions=[question], server_questions=server_questions)
    )
    question_ops = [op for op in plan if isinstance(op, UpsertQuestion)]
    assert [op.slug for op in question_ops] == ["week1-big-o"]


#
# Status: a push moves a question forward through DRAFT, PUBLISHED, HIDDEN,
# never back, so what the web did survives the next push.
#
def _status_plan(question: QuestionFile, server: ServerQuestion | None) -> Plan:
    server_questions = {} if server is None else {question.slug: server}
    return _full_plan(
        [], True, {}, questions=[question], server_questions=server_questions
    )


def _question_writes(plan: Plan) -> list:
    return [op for op in plan.writes if isinstance(op, UpsertQuestion)]


def test_new_question_takes_the_status_of_its_file():
    for draft, status in [(True, "DRAFT"), (False, "PUBLISHED")]:
        [op] = _question_writes(_status_plan(_question("q", draft=draft), None))
        assert isinstance(op, UpsertQuestion)
        assert op.status == status


def test_dropping_the_draft_mark_publishes_an_unchanged_question():
    question = _question("q")
    [op] = _question_writes(
        _status_plan(question, ServerQuestion(question.version, "DRAFT"))
    )
    assert op.status == "PUBLISHED"


def test_hidden_question_stays_hidden_whatever_its_file_says():
    for draft in (True, False):
        question = _question("q", draft=draft)
        plan = _status_plan(question, ServerQuestion(question.version, "HIDDEN"))
        assert plan.notices == ()
        assert _question_writes(plan) == []

        changed = _question("q", EXAMPLE_MDQ.replace("2 + 2", "3 + 3"), draft=draft)
        [op] = _question_writes(
            _status_plan(changed, ServerQuestion(question.version, "HIDDEN"))
        )
        assert op.status == "HIDDEN"


def test_draft_file_keeps_a_published_question_published_and_warns():
    question = _question("q", draft=True)
    plan = _status_plan(question, ServerQuestion(question.version, "PUBLISHED"))
    assert plan.notices == (
        KeptDraftPublished(slug="q", status="PUBLISHED", path=question.path),
    )
    assert _question_writes(plan) == []

    changed = _question("q", EXAMPLE_MDQ.replace("2 + 2", "3 + 3"), draft=True)
    plan = _status_plan(changed, ServerQuestion(question.version, "PUBLISHED"))
    [upsert] = _question_writes(plan)
    assert upsert.status == "PUBLISHED"
    assert [type(n) for n in plan.notices] == [KeptDraftPublished]


def test_draft_on_both_sides_is_left_alone():
    question = _question("q", draft=True)
    plan = _status_plan(question, ServerQuestion(question.version, "DRAFT"))
    assert _question_writes(plan) == []
    assert plan.notices == ()


def test_invalid_question_is_rejected_and_its_server_copy_kept():
    invalid = InvalidQuestion(
        slug="broken", path=Path("questions/broken.md"), reason="bad stem"
    )
    plan = _full_plan(
        [], True, {}, questions=[invalid], server_questions={"broken": "md5:old"}
    )
    assert plan.notices == (
        Rejected(slug="broken", path=invalid.path, reason="bad stem"),
    )
    assert [op for op in plan.writes if not isinstance(op, UpsertCourse)] == []


def test_question_missing_locally_is_deleted():
    server_questions = {"stale-warmup": "md5:some-hash"}
    plan = list(_plan([], True, {}, questions=[], server_questions=server_questions))
    delete_ops = [op for op in plan if isinstance(op, DeleteQuestion)]
    assert [op.slug for op in delete_ops] == ["stale-warmup"]


def test_add_change_and_delete_questions_together_map_one_to_one():
    unchanged = _question("unchanged")
    changed = _question("changed", body=EXAMPLE_MDQ.replace("2 + 2", "5 + 5"))
    added = _question("added")
    server_questions = {
        "unchanged": unchanged.version,
        "changed": "md5:stale",
        "removed": "md5:some-hash",
    }
    plan = list(
        _plan(
            [],
            True,
            {},
            questions=[unchanged, changed, added],
            server_questions=server_questions,
        )
    )
    upserts = {op.slug for op in plan if isinstance(op, UpsertQuestion)}
    deletes = {op.slug for op in plan if isinstance(op, DeleteQuestion)}
    assert upserts == {"changed", "added"}
    assert deletes == {"removed"}


def test_plan_op_order_is_course_then_resource_upserts_then_deletes_then_question_upserts_then_deletes():
    """
    The contract's documented order: "Yields, in order: UpsertCourse, then
    resource upserts, then resource deletes, then question upserts, then
    question deletes" -- and only then the calendar half (see the ordering
    tests below).
    """
    kept_resource = _resource("kept")
    new_resource = _resource("new-resource")
    server_resources = {
        "kept": kept_resource.ref,
        "gone-resource": "stale-ref",
    }
    kept_question = _question("kept-question")
    new_question = _question("new-question", body=EXAMPLE_MDQ.replace("2 + 2", "9 + 9"))
    server_questions = {
        "kept-question": kept_question.version,
        "gone-question": "md5:stale",
    }

    plan = list(
        _plan(
            [kept_resource, new_resource],
            True,
            server_resources,
            questions=[kept_question, new_question],
            server_questions=server_questions,
        )
    )
    kinds = [type(op).__name__ for op in plan]
    assert kinds == [
        "UpsertCourse",
        "UpsertResource",
        "DeleteResource",
        "UpsertQuestion",
        "DeleteQuestion",
    ]


def test_resources_still_planned_when_no_questions_are_passed():
    """
    `questions`/`server_questions` default to empty -- resource-only
    callers (and every existing test above) keep working unchanged.
    """
    resource = _resource("week1-slides")
    plan = list(_plan([resource], True, {}))
    assert not any(isinstance(op, (UpsertQuestion, DeleteQuestion)) for op in plan)


#
# Calendar: time slots and calendar events -- see the mapping's "Sync
# preflight" and `push-calendar.handoff.md`'s diff rules.
#
MON = TimeSlot(
    slug="mon",
    day="MONDAY",
    start=TimeOfDay(hour=14, minute=0),
    duration=Duration(hours=2, minutes=0),
    title="Lecture",
)
REGULAR_EVENT = Event(week=0, time_slot="mon", title="Intro", description="Welcome.")


def test_new_time_slot_is_upserted():
    plan = list(_calendar(_local(slots=[MON]), _server()))
    [op] = [o for o in plan if isinstance(o, UpsertTimeSlot)]
    assert op.slot == MON


def test_unchanged_time_slot_produces_no_op():
    plan = list(_calendar(_local(slots=[MON]), _server(time_slots={"mon": MON.ref})))
    assert not any(isinstance(o, (UpsertTimeSlot, DeleteTimeSlot)) for o in plan)


def test_changed_time_slot_is_upserted():
    plan = list(
        _calendar(_local(slots=[MON]), _server(time_slots={"mon": "stale-ref"}))
    )
    upserts = [o for o in plan if isinstance(o, UpsertTimeSlot)]
    assert [op.slot.slug for op in upserts] == ["mon"]


def test_time_slot_missing_locally_is_deleted():
    plan = list(_calendar(_local(slots=[]), _server(time_slots={"tue": "some-ref"})))
    [op] = [o for o in plan if isinstance(o, DeleteTimeSlot)]
    assert op.slug == "tue"


def test_new_calendar_event_is_upserted():
    plan = list(_calendar(_local(slots=[MON], events=[REGULAR_EVENT]), _server()))
    [op] = [o for o in plan if isinstance(o, UpsertCalendarEvent)]
    assert op.event == REGULAR_EVENT


def test_unchanged_calendar_event_produces_no_op():
    server = _server(
        calendar_events={(0, "mon"): ServerEvent(ref=REGULAR_EVENT.ref, kind="REGULAR")}
    )
    plan = list(_calendar(_local(slots=[MON], events=[REGULAR_EVENT]), server))
    assert not any(
        isinstance(o, (UpsertCalendarEvent, DeleteCalendarEvent)) for o in plan
    )


def test_calendar_event_ref_match_but_different_kind_is_upserted():
    """
    Acceptance criterion 4: an event whose title/description (and
    therefore `ref`) are unchanged but whose `kind` flipped between
    `REGULAR` and `HOLIDAY` is still upserted -- `ref` alone cannot see a
    class that became a holiday, or the reverse.
    """
    server = _server(
        calendar_events={(0, "mon"): ServerEvent(ref=REGULAR_EVENT.ref, kind="HOLIDAY")}
    )
    plan = list(_calendar(_local(slots=[MON], events=[REGULAR_EVENT]), server))
    [op] = [o for o in plan if isinstance(o, UpsertCalendarEvent)]
    assert op.event == REGULAR_EVENT


def test_cancelled_calendar_event_is_neither_upserted_nor_pruned():
    """
    Acceptance criterion 5: "A CANCELLED server event at a key the local
    file also fills produces neither an upsert nor a delete."
    """
    server = _server(
        calendar_events={
            (0, "mon"): ServerEvent(ref="whatever-the-instructor-set", kind="CANCELLED")
        }
    )
    plan = list(_calendar(_local(slots=[MON], events=[REGULAR_EVENT]), server))
    assert not any(
        isinstance(o, (UpsertCalendarEvent, DeleteCalendarEvent)) for o in plan
    )


def test_struck_through_lesson_cancels_a_regular_server_event():
    cancelled = Event(
        week=0, time_slot="mon", title="Intro", description="Welcome.", kind="CANCELLED"
    )
    server = _server(
        time_slots={"mon": MON.ref},
        calendar_events={
            (0, "mon"): ServerEvent(ref=REGULAR_EVENT.ref, kind="REGULAR")
        },
    )
    plan = list(_calendar(_local(slots=[MON], events=[cancelled]), server))
    assert [o for o in plan if isinstance(o, UpsertCalendarEvent)] == [
        UpsertCalendarEvent(event=cancelled)
    ]

    # Once cancelled, it stays so: restoring the title does not undo it.
    server = _server(
        time_slots={"mon": MON.ref},
        calendar_events={(0, "mon"): ServerEvent(ref=cancelled.ref, kind="CANCELLED")},
    )
    plan = list(_calendar(_local(slots=[MON], events=[REGULAR_EVENT]), server))
    assert [o for o in plan if isinstance(o, UpsertCalendarEvent)] == []


def test_calendar_event_missing_locally_is_deleted():
    server = _server(
        calendar_events={(3, "mon"): ServerEvent(ref="some-ref", kind="REGULAR")}
    )
    plan = list(_calendar(_local(slots=[MON], events=[]), server))
    [op] = [o for o in plan if isinstance(o, DeleteCalendarEvent)]
    assert (op.week, op.time_slot) == (3, "mon")


def test_cancelled_calendar_event_missing_locally_is_not_pruned():
    """
    Same rule as above, from the other side: a `CANCELLED` event the local
    file no longer fills is still never pruned -- "whatever the local file
    says."
    """
    server = _server(
        calendar_events={(3, "mon"): ServerEvent(ref="some-ref", kind="CANCELLED")}
    )
    plan = list(_calendar(_local(slots=[MON], events=[]), server))
    assert not any(isinstance(o, DeleteCalendarEvent) for o in plan)


def _group_positions(plan) -> list[list[int]]:
    """
    Index positions of each of the four calendar op kinds, in the order
    the mapping's "Deletion and pruning" now requires: delete events,
    delete slots, upsert slots, upsert events.
    """
    kinds = [type(op).__name__ for op in plan]
    ordered_kinds = (
        "DeleteCalendarEvent",
        "DeleteTimeSlot",
        "UpsertTimeSlot",
        "UpsertCalendarEvent",
    )
    return [[i for i, k in enumerate(kinds) if k == kind] for kind in ordered_kinds]


def _assert_group_order(plan) -> None:
    groups = [positions for positions in _group_positions(plan) if positions]
    for earlier, later in zip(groups, groups[1:]):
        assert max(earlier) < min(later)


def test_plan_calendar_renaming_a_slot_deletes_its_events_and_the_old_slot_before_creating_the_new_one():
    """
    (Corrected 2026-09-24.) Live proof from the mapping's "Deletion and
    pruning": two Monday slots, `mon-14_00`/`mon-18_00`, each with an
    event; `calendar.md` now declares a single `Mon 14:00 2h` entry, so the
    slug collapses back to the bare `mon`. The old order (slots before
    events) let the create of `mon` race the still-live `mon-14_00`, which
    the server refuses (`"This slot overlaps ... on MONDAY"`) since two
    slots may not overlap on one weekday. The corrected order -- delete
    events, delete slots, upsert slots, upsert events -- clears both old
    slots before the new one is created, and only then rewrites the event.
    """
    old_1400 = TimeSlot(
        slug="mon-14_00",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
    )
    old_1800 = TimeSlot(
        slug="mon-18_00",
        day="MONDAY",
        start=TimeOfDay(hour=18, minute=0),
        duration=Duration(hours=1, minutes=0),
    )
    new_mon = TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
    )
    local_event = Event(week=0, time_slot="mon", title="Intro", description="")

    local = _local(slots=[new_mon], events=[local_event])
    server = _server(
        time_slots={"mon-14_00": old_1400.ref, "mon-18_00": old_1800.ref},
        calendar_events={
            (0, "mon-14_00"): ServerEvent(ref="ref-a", kind="REGULAR"),
            (0, "mon-18_00"): ServerEvent(ref="ref-b", kind="REGULAR"),
        },
    )
    plan = list(_calendar(local, server))

    delete_events, delete_slots, upsert_slots, upsert_events = _group_positions(plan)
    assert delete_events and delete_slots and upsert_slots and upsert_events
    _assert_group_order(plan)

    deleted_event_keys = {
        (op.week, op.time_slot) for op in plan if isinstance(op, DeleteCalendarEvent)
    }
    assert deleted_event_keys == {(0, "mon-14_00"), (0, "mon-18_00")}
    deleted_slot_slugs = {op.slug for op in plan if isinstance(op, DeleteTimeSlot)}
    assert deleted_slot_slugs == {"mon-14_00", "mon-18_00"}
    [upserted_slot] = [op for op in plan if isinstance(op, UpsertTimeSlot)]
    assert upserted_slot.slot.slug == "mon"
    [upserted_event] = [op for op in plan if isinstance(op, UpsertCalendarEvent)]
    assert upserted_event.event == local_event


def test_plan_push_places_the_calendar_half_after_questions():
    plan = list(_push(_local(slots=[MON], events=[REGULAR_EVENT]), _server()))
    kinds = [type(op).__name__ for op in plan]
    assert kinds == ["UpsertCourse", "UpsertTimeSlot", "UpsertCalendarEvent"]


#
# A CANCELLED event pins its slot -- the mapping's "Deletion and pruning":
# "A slot the preflight shows carrying a CANCELLED event is therefore left
# in place... The instructor resolves it... the CLI does not get to decide
# that a cancellation is stale." The plan carries a `KeptPinnedSlot` notice
# in place of the `DeleteTimeSlot` that would otherwise have been planned.
#
def test_cancelled_events_slot_is_not_deleted_even_when_local_no_longer_declares_it():
    server = _server(
        time_slots={"wed": "some-ref"},
        calendar_events={(2, "wed"): ServerEvent(ref="whatever", kind="CANCELLED")},
    )
    plan = plan_calendar(_local(slots=[], events=[]), server)

    assert not any(
        isinstance(op, DeleteTimeSlot) and op.slug == "wed" for op in plan.writes
    )
    assert plan.notices == (KeptPinnedSlot(slug="wed", weeks=(2,)),)


def test_a_slot_pinned_by_several_cancelled_events_is_noticed_once():
    server = _server(
        time_slots={"wed": "some-ref"},
        calendar_events={
            (4, "wed"): ServerEvent(ref="b", kind="CANCELLED"),
            (2, "wed"): ServerEvent(ref="a", kind="CANCELLED"),
        },
    )
    plan = plan_calendar(_local(slots=[], events=[]), server)
    assert plan.notices == (KeptPinnedSlot(slug="wed", weeks=(2, 4)),)


def test_a_regular_events_slot_is_still_deleted_when_local_no_longer_declares_it():
    """Control case: the guard above is specific to `CANCELLED`."""
    server = _server(
        time_slots={"wed": "some-ref"},
        calendar_events={(2, "wed"): ServerEvent(ref="whatever", kind="REGULAR")},
    )
    plan = plan_calendar(_local(slots=[], events=[]), server)
    [op] = [o for o in plan.writes if isinstance(o, DeleteTimeSlot)]
    assert op.slug == "wed"
    assert plan.notices == ()


#
# Convergence: acceptance criterion 6, applied to the calendar half.
#
WEEKDAY_BY_SLUG = {"mon": "MONDAY", "tue": "TUESDAY", "wed": "WEDNESDAY"}


@st.composite
def _calendar_states(draw):
    num_slots = draw(st.integers(min_value=1, max_value=2))
    slot_names = draw(
        st.lists(
            st.sampled_from(list(WEEKDAY_BY_SLUG)),
            min_size=num_slots,
            max_size=num_slots,
            unique=True,
        )
    )
    slots = tuple(
        TimeSlot(
            slug=name,
            day=WEEKDAY_BY_SLUG[name],
            start=TimeOfDay(hour=9, minute=0),
            duration=Duration(hours=1, minutes=0),
        )
        for name in slot_names
    )

    num_events = draw(st.integers(min_value=0, max_value=4))
    raw_events = [
        Event(
            week=draw(st.integers(0, 3)),
            time_slot=draw(st.sampled_from(slot_names)),
            title=f"event-{i}",
            description="",
        )
        for i in range(num_events)
    ]
    # A real `allocate()` output never repeats a (week, timeSlot) key --
    # collapse any the strategy happened to draw twice.
    by_key: dict[tuple[int, str], Event] = {}
    for event in raw_events:
        by_key[(event.week, event.time_slot)] = event
    return slots, tuple(by_key.values())


@given(local_state=_calendar_states(), server_state=_calendar_states())
@settings(max_examples=100)
def test_plan_calendar_op_order_is_delete_events_delete_slots_upsert_slots_upsert_events(
    local_state, server_state
):
    """
    The mapping's "Deletion and pruning": whatever the local repository and
    server disagree on, the four calendar op kinds -- when present at all
    -- always come out grouped in this order: delete events, delete slots,
    upsert slots, upsert events.
    """
    local_slots, local_events = local_state
    server_slots, server_events = server_state

    local = _local(slots=local_slots, events=local_events)
    server = _server(
        time_slots={slot.slug: slot.ref for slot in server_slots},
        calendar_events={
            (event.week, event.time_slot): ServerEvent(ref=event.ref, kind=event.kind)
            for event in server_events
        },
    )
    plan = list(_calendar(local, server))
    _assert_group_order(plan)


def _apply_calendar(plan, server_time_slots, server_calendar_events):
    server_time_slots = dict(server_time_slots)
    server_calendar_events = dict(server_calendar_events)
    for op in plan:
        if isinstance(op, UpsertTimeSlot):
            server_time_slots[op.slot.slug] = op.slot.ref
        elif isinstance(op, DeleteTimeSlot):
            server_time_slots.pop(op.slug, None)
        elif isinstance(op, UpsertCalendarEvent):
            server_calendar_events[(op.event.week, op.event.time_slot)] = ServerEvent(
                ref=op.event.ref, kind=op.event.kind
            )
        elif isinstance(op, DeleteCalendarEvent):
            server_calendar_events.pop((op.week, op.time_slot), None)
    return server_time_slots, server_calendar_events


@given(calendar_state=_calendar_states())
@settings(max_examples=50)
def test_replanning_the_calendar_after_applying_converges_to_no_calendar_ops(
    calendar_state,
):
    slots, events = calendar_state
    local = _local(slots=slots, events=events)

    first_plan = list(_calendar(local, _server()))
    new_time_slots, new_calendar_events = _apply_calendar(first_plan, {}, {})

    second_plan = list(
        _calendar(
            local,
            _server(time_slots=new_time_slots, calendar_events=new_calendar_events),
        )
    )
    calendar_ops = [
        op
        for op in second_plan
        if isinstance(
            op,
            (UpsertTimeSlot, DeleteTimeSlot, UpsertCalendarEvent, DeleteCalendarEvent),
        )
    ]
    assert calendar_ops == []


def test_plan_push_after_applying_its_own_plan_yields_nothing():
    """
    A second `plan_push` against the state the first one wrote yields
    nothing, the course row included. Exercised with resources, questions
    and the calendar all present at once.
    """
    resource = _resource("week1-slides")
    question = _question("week1-big-o")
    local = _local(
        [resource], questions=[question], slots=[MON], events=[REGULAR_EVENT]
    )

    first_plan = list(_push(local, _server()))

    course_rev: str | None = None
    server_resources: dict[str, str] = {}
    server_questions: dict[str, str] = {}
    server_time_slots: dict[str, str] = {}
    server_calendar_events: dict[tuple[int, str], ServerEvent] = {}
    for op in first_plan:
        if isinstance(op, UpsertCourse):
            course_rev = op.ref
        elif isinstance(op, UpsertResource):
            server_resources[op.slug] = op.ref
        elif isinstance(op, UpsertQuestion):
            server_questions[op.slug] = ServerQuestion(op.version, op.status)
        elif isinstance(op, UpsertTimeSlot):
            server_time_slots[op.slot.slug] = op.slot.ref
        elif isinstance(op, UpsertCalendarEvent):
            server_calendar_events[(op.event.week, op.event.time_slot)] = ServerEvent(
                ref=op.event.ref, kind=op.event.kind
            )

    second_plan = list(
        _push(
            local,
            _server(
                course_exists=True,
                course_rev=course_rev,
                resources=server_resources,
                questions=server_questions,
                time_slots=server_time_slots,
                calendar_events=server_calendar_events,
            ),
        )
    )
    assert second_plan == []


#
# An event with a roll call is not pruned silently: it is kept with a warning
# unless the caller asks to drop the roll calls too.
#
def _server_with_roll_call(attendances: int | None) -> ServerState:
    """
    A server holding the `mon` slot and event `(5, mon)`, with a roll call of
    `attendances` presences (`None` for an event without a roll call).
    """
    return _server(
        time_slots={"mon": MON.ref},
        calendar_events={
            (5, "mon"): ServerEvent(ref="ref", kind="REGULAR", attendances=attendances)
        },
    )


def test_event_with_a_roll_call_removed_locally_is_kept_with_a_warning():
    plan = plan_push(_local(slots=[MON]), _server_with_roll_call(32))

    assert not any(isinstance(op, DeleteCalendarEvent) for op in plan.writes)
    assert KeptForRollCall(5, "mon", 32) in plan.notices


def test_event_with_an_empty_roll_call_removed_locally_is_still_kept_with_a_warning():
    plan = plan_push(_local(slots=[MON]), _server_with_roll_call(0))

    assert not any(isinstance(op, DeleteCalendarEvent) for op in plan.writes)
    assert KeptForRollCall(5, "mon", 0) in plan.notices


def test_slot_of_an_event_kept_for_its_roll_call_is_not_deleted():
    plan = list(_push(_local(slots=[]), _server_with_roll_call(32)))

    assert DeleteTimeSlot("mon") not in plan


def test_event_without_a_roll_call_removed_locally_is_deleted_without_a_warning():
    plan = plan_push(
        _local(slots=[MON]), _server_with_roll_call(None), drop_roll_calls=True
    )

    assert DeleteCalendarEvent(5, "mon") in plan.writes
    assert plan.notices == ()
    assert not any(isinstance(op, DeleteRollCall) for op in plan.writes)


def test_dropping_roll_calls_deletes_roll_call_then_event_then_slot():
    plan = plan_push(_local(slots=[]), _server_with_roll_call(32), drop_roll_calls=True)
    assert plan.notices == ()

    plan = list(plan.writes)
    roll_call = plan.index(DeleteRollCall(5, "mon"))
    event = plan.index(DeleteCalendarEvent(5, "mon"))
    slot = plan.index(DeleteTimeSlot("mon"))
    assert roll_call < event < slot


def test_event_with_a_roll_call_still_local_with_new_content_is_upserted_without_a_warning():
    server = _server(
        time_slots={"mon": MON.ref},
        calendar_events={
            (0, "mon"): ServerEvent(ref="stale", kind="REGULAR", attendances=32)
        },
    )
    plan = plan_push(_local(slots=[MON], events=[REGULAR_EVENT]), server)

    assert UpsertCalendarEvent(event=REGULAR_EVENT) in plan.writes
    assert plan.notices == ()
    assert not any(isinstance(op, DeleteRollCall) for op in plan.writes)


def test_course_with_a_matching_rev_is_not_upserted():
    [course] = [op for op in _push(_local(), _server()) if isinstance(op, UpsertCourse)]
    assert course.ref == course_ref(DESCRIPTION, course.start_at, course.end_at)

    again = _push(_local(), _server(course_rev=course.ref))
    assert [op for op in again if isinstance(op, UpsertCourse)] == []


def test_course_with_a_new_description_is_upserted_again():
    [course] = [op for op in _push(_local(), _server()) if isinstance(op, UpsertCourse)]
    changed = _push(_local(description="Other."), _server(course_rev=course.ref))
    assert [type(op) for op in changed if isinstance(op, UpsertCourse)] == [
        UpsertCourse
    ]
