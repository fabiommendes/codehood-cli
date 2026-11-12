"""
Tests for `codehood.push.plan.plan_sync`, the three-way planner: one row of
the RFC's decision table per case, per resource type, then the special cases
and the two properties (convergence, and safety of `Put` and `Prune`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import mdq
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from codehood.models.repo import CourseKey
from codehood.push.base import BaseEntry, BaseState
from codehood.push.calendar import Duration, Event, TimeOfDay, TimeSlot
from codehood.push.exclude import ExcludedFile
from codehood.push.grades import GradeColumn
from codehood.push.plan import (
    DeleteCalendarEvent,
    DeleteGradeColumn,
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
    ServerDrifted,
    ServerEvent,
    ServerQuestion,
    ServerState,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertGradeColumn,
    UpsertQuestion,
    UpsertResource,
    UpsertTimeSlot,
    course_ref,
    diff_fields,
    event_key,
    parse_event_key,
    plan_sync,
)
from codehood.push.project import RemoteEntry
from codehood.push.question import InvalidQuestion, QuestionFile, question_version
from codehood.push.resource import MdData, ResourceFile, content_ref
from codehood.push.wire import (
    Payload,
    course_payload,
    event_payload,
    grade_column_payload,
    instant,
    question_payload,
    resource_payload,
    time_slot_payload,
)

KEY = CourseKey("cs101", "ada", "2026-1")
START, END = date(2026, 1, 1), date(2026, 6, 1)
DESCRIPTION = "Course description."
COURSE_PAYLOAD = course_payload(KEY, DESCRIPTION, START, END)
COURSE_REF = course_ref(DESCRIPTION, instant(START), instant(END))

QUESTION = """---
title: Example question
---

What is {x}?

- [ ] 3
- [*] 4
- [ ] 5
"""


#
# Entities
#
def _resource(variant: str, slug: str = "r", event=None) -> ResourceFile:
    data = MdData(content=variant)
    return ResourceFile(
        slug=slug,
        title="title",
        description=None,
        data=data,
        ref=content_ref("title", None, data, event),
        path=Path(f"resources/{slug}.md"),
        event=event,
    )


def _question(variant: str, slug: str = "q", *, draft: bool = False) -> QuestionFile:
    body = QUESTION.format(x=variant)
    return QuestionFile(
        slug=slug,
        version=question_version(body.encode()),
        question=mdq.parse(body, kind="question", ids="fill"),
        path=Path(f"questions/{slug}.md"),
        status="DRAFT" if draft else "PUBLISHED",
    )


def _slot(variant: str, slug: str = "t") -> TimeSlot:
    return TimeSlot(slug, "MONDAY", TimeOfDay(8, 0), Duration(1, 0), title=variant)


def _event(variant: str, week: int = 1, slot: str = "t") -> Event:
    return Event(week, slot, title=variant)


@dataclass(frozen=True)
class Adapter:
    """
    How one resource type enters a `LocalState` and a `ServerState`.
    """

    kind: str
    key: str
    has_rev: bool
    entity: Callable[[str], Any]
    payload: Callable[[str], Payload]
    ref: Callable[[str], str | None]
    local: Callable[[Any], dict[str, Any]]
    remote: Callable[[str, Payload, str | None, str | None], dict[str, Any]]
    base_field: str
    writes: tuple[type, ...]
    put: type
    prune: type


def _remote_resource(variant, payload, rev, ref):
    return {"resources": {"r": RemoteEntry(payload, rev, "u")}}


def _remote_question(variant, payload, rev, ref):
    version = ref or "other"
    entry = RemoteEntry(payload, rev, "u")
    return {"questions": {"q": ServerQuestion(version, "PUBLISHED", entry)}}


def _remote_slot(variant, payload, rev, ref):
    return {"time_slots": {"t": RemoteEntry(payload, None, "u")}}


def _remote_event(variant, payload, rev, ref):
    entry = RemoteEntry(payload, rev, "u")
    return {
        "calendar_events": {(1, "t"): ServerEvent(rev or "", "REGULAR", None, entry)}
    }


ADAPTERS = {
    "resource": Adapter(
        "resource",
        "r",
        True,
        _resource,
        lambda v: resource_payload(_resource(v)),
        lambda v: _resource(v).ref,
        lambda e: {"resources": (e,)},
        _remote_resource,
        "resources",
        (UpsertResource, DeleteResource),
        UpsertResource,
        DeleteResource,
    ),
    "question": Adapter(
        "question",
        "q",
        True,
        _question,
        lambda v: question_payload(_question(v)),
        lambda v: _question(v).version,
        lambda e: {"questions": (e,)},
        _remote_question,
        "questions",
        (UpsertQuestion, DeleteQuestion),
        UpsertQuestion,
        DeleteQuestion,
    ),
    "time_slot": Adapter(
        "time_slot",
        "t",
        False,
        _slot,
        lambda v: time_slot_payload(_slot(v)),
        lambda v: None,
        lambda e: {"slots": (e,)},
        _remote_slot,
        "time_slots",
        (UpsertTimeSlot, DeleteTimeSlot),
        UpsertTimeSlot,
        DeleteTimeSlot,
    ),
    "calendar_event": Adapter(
        "calendar_event",
        "1/t",
        True,
        _event,
        lambda v: event_payload(_event(v)),
        lambda v: _event(v).ref,
        lambda e: {"events": (e,)},
        _remote_event,
        "calendar_events",
        (UpsertCalendarEvent, DeleteCalendarEvent),
        UpsertCalendarEvent,
        DeleteCalendarEvent,
    ),
}


def _scenario(
    adapter: Adapter,
    local: str | None,
    base: str | None,
    remote: str | None,
    *,
    base_rev: str | None = "r0",
    remote_rev: str | None = "r0",
    remote_ref: str | None = None,
) -> tuple[LocalState, BaseState, ServerState]:
    """
    The three states of one entity, each a variant (`None` for absent) and
    the course in agreement everywhere.
    """
    state = LocalState(
        KEY,
        DESCRIPTION,
        START,
        END,
        **(adapter.local(adapter.entity(local)) if local is not None else {}),
    )
    stored = BaseState(course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)})
    if base is not None:
        entry = BaseEntry(
            adapter.payload(base), base_rev if adapter.has_rev else None, "u"
        )
        getattr(stored, adapter.base_field)[adapter.key] = entry
    server = ServerState(
        course_exists=True,
        course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF, "u"),
        **(
            adapter.remote(remote, adapter.payload(remote), remote_rev, remote_ref)
            if remote is not None
            else {}
        ),
    )
    return state, stored, server


def _classify(plan: Plan, adapter: Adapter) -> str:
    """
    One word for what the plan does with the entity, ignoring the course.
    """
    writes = [w for w in plan.writes if isinstance(w, adapter.writes)]
    if writes:
        return "put" if isinstance(writes[0], adapter.put) else "prune"
    if pulls := [p for p in plan.pulls if p.kind == adapter.kind]:
        return f"pull-{pulls[0].change}"
    if conflicts := [c for c in plan.conflicts if c.kind == adapter.kind]:
        return f"conflict:{conflicts[0].reason}"
    if [o for o in plan.other_cli if o.kind == adapter.kind]:
        return "other-cli"
    if updates := [u for u in plan.base_updates if u.kind == adapter.kind]:
        return "drop-base" if updates[0].entry is None else "adopt"
    return "skip"


def _plan(adapter: Adapter, *args, **kwargs) -> Plan:
    return plan_sync(*_scenario(adapter, *args, **kwargs))


#
# The decision table, per resource type. Same rev everywhere: nothing here
# is another CLI's doing.
#
TABLE = [
    # local, base, remote, expected
    ("a", "a", "a", "skip"),
    ("b", "a", "a", "put"),
    ("a", "a", "b", "pull-update"),
    ("b", "a", "b", "adopt"),
    ("b", "a", "c", "conflict:both-changed"),
    (None, "a", "a", "prune"),
    ("a", "a", None, "pull-delete"),
    (None, "a", "b", "conflict:local-deleted-remote-edited"),
    ("b", "a", None, "conflict:local-edited-remote-deleted"),
    ("a", None, None, "put"),
    (None, "a", None, "drop-base"),
    ("a", None, "a", "adopt"),
    ("a", None, "b", "conflict:no-base"),
]


@pytest.mark.parametrize("name", ADAPTERS)
@pytest.mark.parametrize(("local", "base", "remote", "expected"), TABLE)
def test_decision_table(name, local, base, remote, expected):
    adapter = ADAPTERS[name]
    assert _classify(_plan(adapter, local, base, remote), adapter) == expected


@pytest.mark.parametrize("name", ADAPTERS)
def test_new_on_the_server_is_a_pull_when_it_has_no_rev_and_other_cli_otherwise(name):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, None, None, "a", remote_rev=None)
    assert _classify(plan, adapter) == "pull-create"
    assert plan.writes == ()
    expected = "other-cli" if adapter.has_rev else "pull-create"
    plan = _plan(adapter, None, None, "a", remote_rev="theirs")
    assert _classify(plan, adapter) == expected
    assert not any(isinstance(w, adapter.writes) for w in plan.writes)


@pytest.mark.parametrize("name", [n for n, a in ADAPTERS.items() if a.has_rev])
@pytest.mark.parametrize(
    ("local", "base", "remote", "expected"),
    [
        ("a", "a", "b", "other-cli"),
        ("b", "a", "c", "other-cli"),
        (None, "a", "b", "other-cli"),
        ("b", "a", "b", "adopt"),
        ("b", "a", "a", "put"),
    ],
)
def test_other_cli_wins_over_conflict_and_pull(name, local, base, remote, expected):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, local, base, remote, remote_rev="theirs")
    assert _classify(plan, adapter) == expected


@pytest.mark.parametrize("name", [n for n, a in ADAPTERS.items() if a.has_rev])
def test_equal_payloads_adopt_the_server_rev(name):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, "b", "a", "b", remote_rev="theirs")
    [update] = plan.base_updates
    assert update.entry == BaseEntry(adapter.payload("b"), "theirs", "u")


@pytest.mark.parametrize("name", [n for n, a in ADAPTERS.items() if a.has_rev])
def test_without_a_base_the_server_rev_equal_to_the_local_hash_means_pull(name):
    adapter = ADAPTERS[name]
    ref = adapter.ref("a")
    plan = _plan(adapter, "a", None, "b", remote_rev=ref, remote_ref=ref)
    assert _classify(plan, adapter) == "pull-update"
    plan = _plan(adapter, "a", None, "a", remote_rev=ref, remote_ref=ref)
    assert _classify(plan, adapter) == "adopt"


@pytest.mark.parametrize("name", [n for n, a in ADAPTERS.items() if a.has_rev])
def test_without_a_base_another_rev_is_a_conflict_never_a_win(name):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, "a", None, "b", remote_rev="theirs", remote_ref="x")
    assert _classify(plan, adapter) == "conflict:no-base"
    assert plan.writes == ()


def test_a_time_slot_without_a_base_never_matches_by_hash():
    adapter = ADAPTERS["time_slot"]
    assert _classify(_plan(adapter, "a", None, "b"), adapter) == "conflict:no-base"
    assert _classify(_plan(adapter, "a", None, "a"), adapter) == "adopt"


#
# What the decisions carry
#
@pytest.mark.parametrize("name", ADAPTERS)
def test_a_put_says_which_base_entry_to_record(name):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, "b", "a", "a")
    [confirmation] = [c for c in plan.confirmations if c.update.kind == name]
    assert confirmation.write in plan.writes
    assert confirmation.update.key == adapter.key
    assert confirmation.update.entry == BaseEntry(adapter.payload("b"))


@pytest.mark.parametrize("name", ADAPTERS)
def test_a_prune_says_to_drop_the_base_entry(name):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, None, "a", "a")
    [confirmation] = [c for c in plan.confirmations if c.update.kind == name]
    assert confirmation.update.entry is None


@pytest.mark.parametrize("name", ADAPTERS)
def test_a_conflict_carries_the_operation_that_settles_it_for_the_local_side(name):
    adapter = ADAPTERS[name]
    [conflict] = _plan(adapter, "b", "a", "c").conflicts
    [ours] = conflict.ours
    assert isinstance(ours.op, adapter.put)
    [conflict] = _plan(adapter, None, "a", "b").conflicts
    [ours] = conflict.ours
    assert isinstance(ours.op, adapter.prune)
    assert _plan(adapter, "a", "a", None).conflicts == ()
    [conflict] = _plan(adapter, "b", "a", None).conflicts
    assert isinstance(conflict.ours[0].op, adapter.put)


@pytest.mark.parametrize("name", ADAPTERS)
def test_fields_are_the_top_level_payload_keys_that_differ(name):
    adapter = ADAPTERS[name]
    [pull] = _plan(adapter, "a", "a", "b").pulls
    assert pull.fields
    assert set(pull.fields) == set(
        diff_fields(adapter.payload("a"), adapter.payload("b"))
    )
    assert pull.remote is not None and pull.remote.payload == adapter.payload("b")


def test_diff_fields():
    assert diff_fields({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4}) == ("b", "c")
    assert diff_fields(None, {"b": 1, "a": 1}) == ("a", "b")
    assert diff_fields({"a": None}, {}) == ("a",)


def test_event_keys_round_trip():
    assert event_key(3, "tue-am") == "3/tue-am"
    assert parse_event_key("3/tue-am") == (3, "tue-am")
    with pytest.raises(ValueError):
        parse_event_key("nonsense")


#
# Renames
#
def _rename(*, remote_title: str, remote_rev: str = "r0") -> Plan:
    old = _resource("body", "old")
    new = _resource("body", "new")
    remote_old = _resource("body", "old")
    payload = resource_payload(remote_old) | {"title": remote_title}
    local = LocalState(KEY, DESCRIPTION, START, END, resources=(new,))
    base = BaseState(
        course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
        resources={"old": BaseEntry(resource_payload(old), "r0", "u")},
    )
    server = ServerState(
        course_exists=True,
        course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
        resources={"old": RemoteEntry(payload, remote_rev, "u")},
    )
    return plan_sync(local, base, server)


def test_rename_with_an_edit_on_the_server_is_one_conflict():
    plan = _rename(remote_title="edited")
    [conflict] = plan.conflicts
    assert (conflict.reason, conflict.key, conflict.renamed_to) == (
        "rename",
        "old",
        "new",
    )
    assert [type(c.op) for c in conflict.ours] == [UpsertResource, DeleteResource]
    assert plan.writes == ()


def test_rename_with_the_server_unchanged_is_a_put_and_a_prune():
    plan = _rename(remote_title="title")
    assert [type(w) for w in plan.writes if not isinstance(w, UpsertCourse)] == [
        UpsertResource,
        DeleteResource,
    ]
    assert plan.conflicts == ()


def test_rename_edited_by_another_cli_asks_for_a_git_pull():
    plan = _rename(remote_title="edited", remote_rev="theirs")
    assert [o.key for o in plan.other_cli] == ["old"]
    assert plan.writes == () and plan.conflicts == ()


#
# Questions
#
def _q_plan(local, remote_status, *, entry_variant="a", base="a") -> Plan:
    payload = question_payload(_question(entry_variant))
    state = LocalState(KEY, DESCRIPTION, START, END, questions=(local,))
    stored = BaseState(
        course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
        questions={"q": BaseEntry(question_payload(_question(base)), "r0", "u")},
    )
    server = ServerState(
        course_exists=True,
        course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
        questions={
            "q": ServerQuestion("v", remote_status, RemoteEntry(payload, "r0", "u"))
        },
    )
    return plan_sync(state, stored, server)


def test_the_question_status_stays_out_of_the_comparison():
    plan = _q_plan(_question("a"), "HIDDEN")
    assert plan.writes == () and plan.notices == () and plan.base_updates == ()


def test_a_draft_file_over_a_published_question_keeps_it_with_a_notice():
    plan = _q_plan(_question("a", draft=True), "PUBLISHED")
    assert plan.writes == ()
    assert [type(n) for n in plan.notices] == [KeptDraftPublished]


def test_publishing_a_draft_is_a_put_with_the_new_status():
    plan = _q_plan(_question("a"), "DRAFT")
    [write] = plan.writes
    assert isinstance(write, UpsertQuestion) and write.status == "PUBLISHED"


def test_an_edited_question_is_put_with_the_joined_status():
    plan = _q_plan(_question("b"), "HIDDEN")
    [write] = plan.writes
    assert isinstance(write, UpsertQuestion) and write.status == "HIDDEN"


def test_an_invalid_question_is_kept_and_rejected():
    invalid = InvalidQuestion(slug="q", path=Path("questions/q.md"), reason="bad")
    plan = _q_plan(invalid, "PUBLISHED")
    assert [type(n) for n in plan.notices] == [Rejected]
    assert plan.writes == () and plan.conflicts == ()


#
# Excluded files
#
def test_an_excluded_file_is_left_alone_in_both_directions():
    excluded = (ExcludedFile("resource", "r", "resources/r.md"),)
    local = LocalState(KEY, DESCRIPTION, START, END, excluded=excluded)
    for remote_variant, base_variant in (("a", "a"), ("b", "a"), (None, "a")):
        base = BaseState(
            course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
            resources={"r": BaseEntry(resource_payload(_resource(base_variant)), "r0")},
        )
        remote = (
            {"r": RemoteEntry(resource_payload(_resource(remote_variant)), "r0")}
            if remote_variant
            else {}
        )
        server = ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            resources=remote,
        )
        assert plan_sync(local, base, server) == Plan()


#
# Resources and their lessons
#
def _link_state(local_event, base_event, remote_event, *, local_present=True):
    local = _resource("a", event=local_event)
    base_payload = resource_payload(_resource("a", event=base_event))
    remote_payload = (
        resource_payload(_resource("a", event=remote_event))
        if remote_event != "gone"
        else {}
    )
    return plan_sync(
        LocalState(
            KEY,
            DESCRIPTION,
            START,
            END,
            resources=(local,) if local_present else (),
        ),
        BaseState(
            course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
            resources={"r": BaseEntry(base_payload, "r0")},
        ),
        ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            resources=(
                {"r": RemoteEntry(remote_payload, "r0")}
                if remote_event != "gone"
                else {}
            ),
        ),
    )


def test_a_lesson_link_changed_on_the_server_is_a_conflict_not_a_pull():
    from codehood.push.calendar import EventKey

    lesson = EventKey(2, "t")
    plan = _link_state(None, None, lesson)
    [conflict] = plan.conflicts
    assert conflict.reason == "link" and conflict.fields == ("event",)
    assert plan.pulls == ()


def test_a_resource_deleted_on_the_server_but_still_linked_is_a_conflict():
    from codehood.push.calendar import EventKey

    lesson = EventKey(2, "t")
    [conflict] = _link_state(lesson, lesson, "gone").conflicts
    assert conflict.reason == "referenced"
    assert isinstance(conflict.ours[0].op, UpsertResource)


def test_a_resource_deleted_on_the_server_and_not_linked_is_a_pull():
    plan = _link_state(None, None, "gone")
    assert [(p.kind, p.change) for p in plan.pulls] == [("resource", "delete")]


def test_a_resource_created_on_the_server_with_a_lesson_is_a_conflict():
    from codehood.push.calendar import EventKey

    lesson = EventKey(2, "t")
    plan = plan_sync(
        LocalState(KEY, DESCRIPTION, START, END),
        BaseState(course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)}),
        ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            resources={
                "r": RemoteEntry(resource_payload(_resource("a", event=lesson)))
            },
        ),
    )
    assert [c.reason for c in plan.conflicts] == ["link"]
    assert plan.pulls == ()


#
# Calendar
#
def _cal(local_events=(), local_slots=(), base=None, events=None, slots=None):
    return plan_sync(
        LocalState(
            KEY, DESCRIPTION, START, END, slots=local_slots, events=local_events
        ),
        base or BaseState(course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)}),
        ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            calendar_events=events or {},
            time_slots=slots or {},
        ),
    )


def _server_event(variant="a", kind="REGULAR", attendances=None, rev="r0"):
    entry = RemoteEntry(event_payload(_event(variant)), rev, "u")
    return ServerEvent(rev, kind, attendances, entry)


def _event_base(variant="a"):
    return BaseState(
        course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
        calendar_events={"1/t": BaseEntry(event_payload(_event(variant)), "r0")},
    )


def test_a_cancelled_server_event_is_kept_whatever_the_repository_says():
    for local in ((), (_event("b"),)):
        plan = _cal(
            local,
            base=_event_base(),
            events={(1, "t"): _server_event(kind="CANCELLED")},
        )
        assert plan.writes == ()
        assert all(type(n) is KeptPinnedSlot for n in plan.notices)


def test_an_event_with_a_roll_call_gone_locally_is_kept():
    plan = _cal(base=_event_base(), events={(1, "t"): _server_event(attendances=3)})
    assert [type(n) for n in plan.notices] == [KeptForRollCall]
    assert plan.writes == ()


def test_dropping_roll_calls_deletes_the_roll_call_before_the_event():
    plan = plan_sync(
        LocalState(KEY, DESCRIPTION, START, END),
        _event_base(),
        ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            calendar_events={(1, "t"): _server_event(attendances=3)},
        ),
        drop_roll_calls=True,
    )
    assert [type(w) for w in plan.writes] == [DeleteRollCall, DeleteCalendarEvent]


def test_a_slot_pinned_by_a_cancelled_event_is_not_pruned():
    base = _event_base()
    base.time_slots["t"] = BaseEntry(time_slot_payload(_slot("a")), None)
    plan = _cal(
        base=base,
        events={(1, "t"): _server_event(kind="CANCELLED")},
        slots={"t": RemoteEntry(time_slot_payload(_slot("a")))},
    )
    assert not [w for w in plan.writes if isinstance(w, DeleteTimeSlot)]


def test_calendar_writes_keep_the_order_deletes_then_slots_then_events():
    base = BaseState(
        course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
        calendar_events={
            "2/old": BaseEntry(event_payload(_event("a", 2, "old")), "r0")
        },
        time_slots={"old": BaseEntry(time_slot_payload(_slot("a", "old")))},
    )
    plan = _cal(
        (_event("a", 1, "t"),),
        (_slot("a", "t"),),
        base=base,
        events={(2, "old"): _server_event_for(2, "old")},
        slots={"old": RemoteEntry(time_slot_payload(_slot("a", "old")))},
    )
    assert [type(w) for w in plan.writes] == [
        DeleteCalendarEvent,
        DeleteTimeSlot,
        UpsertTimeSlot,
        UpsertCalendarEvent,
    ]


def _server_event_for(week, slot):
    entry = RemoteEntry(event_payload(_event("a", week, slot)), "r0", "u")
    return ServerEvent("r0", "REGULAR", None, entry)


#
# Course
#
def _course(
    description=DESCRIPTION, base_description=DESCRIPTION, remote="same", rev=COURSE_REF
):
    base_payload = course_payload(KEY, base_description, START, END)
    remote_payload = (
        course_payload(KEY, "web edit", START, END)
        if remote == "edited"
        else course_payload(KEY, base_description, START, END)
    )
    return plan_sync(
        LocalState(KEY, description, START, END),
        BaseState(course={"course": BaseEntry(base_payload, COURSE_REF, "u")}),
        ServerState(
            course_exists=remote != "missing",
            course=RemoteEntry(remote_payload, rev, "u")
            if remote != "missing"
            else None,
        ),
    )


def test_course_in_agreement_plans_nothing():
    assert _course() == Plan()


def test_a_local_course_edit_is_an_upsert_with_the_base_to_record():
    plan = _course(description="new")
    [write] = plan.writes
    assert isinstance(write, UpsertCourse) and write.description == "new"
    [confirmation] = plan.confirmations
    assert confirmation.update.entry == BaseEntry(
        course_payload(KEY, "new", START, END)
    )


def test_a_course_edited_on_the_web_is_pulled():
    plan = _course(remote="edited")
    [pull] = plan.pulls
    assert (pull.kind, pull.change, pull.fields) == (
        "course",
        "update",
        ("description",),
    )


def test_a_course_edited_by_another_cli_asks_for_a_git_pull():
    plan = _course(remote="edited", rev="theirs")
    assert [o.fields for o in plan.other_cli] == [("description",)]


def test_a_course_missing_on_the_server_is_written_back():
    plan = _course(remote="missing")
    assert [type(w) for w in plan.writes] == [UpsertCourse]
    assert plan.pulls == ()


#
# One-way kinds
#
def _grades(local_columns, base_columns, remote_columns):
    return plan_sync(
        LocalState(KEY, DESCRIPTION, START, END, grade_columns=local_columns),
        BaseState(
            course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
            grade_columns={
                c.slug: BaseEntry(grade_column_payload(c), c.rev, "u")
                for c in base_columns
            },
        ),
        ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            grade_columns={
                c.slug: RemoteEntry(grade_column_payload(c), c.rev, "u")
                for c in remote_columns
            },
        ),
    )


COLUMN = GradeColumn("total", "Total", "number", 0, (("ana", 7.0),))
EDITED = GradeColumn("total", "Total", "number", 0, (("ana", 9.0),))


def test_a_grade_column_the_server_changed_is_overwritten_with_a_notice():
    plan = _grades((COLUMN,), (COLUMN,), (EDITED,))
    assert [type(w) for w in plan.writes] == [UpsertGradeColumn]
    assert plan.notices == (ServerDrifted("grade_column", "total", ("values",)),)
    assert plan.conflicts == () and plan.pulls == ()


def test_a_grade_column_in_agreement_plans_nothing():
    assert _grades((COLUMN,), (COLUMN,), (COLUMN,)) == Plan()


def test_a_grade_column_gone_locally_is_deleted_and_dropped_from_the_base():
    plan = _grades((), (COLUMN,), (COLUMN,))
    assert [type(w) for w in plan.writes] == [DeleteGradeColumn]
    [confirmation] = plan.confirmations
    assert confirmation.update.entry is None


def test_grade_columns_that_could_not_be_computed_are_left_alone():
    assert _grades(None, (COLUMN,), (COLUMN,)) == Plan()


def test_a_new_grade_column_is_put_and_recorded():
    plan = _grades((COLUMN,), (), ())
    [confirmation] = plan.confirmations
    assert confirmation.update.entry == BaseEntry(grade_column_payload(COLUMN))


#
# Properties
#
VARIANT = st.sampled_from(["a", "b", "c"])
MAYBE = st.none() | VARIANT


def _apply(adapter: Adapter, plan: Plan, local, base, remote):
    """
    The in-memory effect of running `plan` on one entity's variants.
    """
    for confirmation in plan.confirmations:
        if confirmation.update.kind != adapter.kind:
            continue
        if confirmation.update.entry is None:
            remote = base = None
        else:
            remote = base = local
    for pull in plan.pulls:
        if pull.kind != adapter.kind:
            continue
        local = base = None if pull.remote is None else remote
    for update in plan.base_updates:
        if update.kind == adapter.kind:
            base = None if update.entry is None else local
    return local, base, remote


@pytest.mark.parametrize("name", ADAPTERS)
@settings(max_examples=60, deadline=None)
@given(local=MAYBE, base=MAYBE, remote=MAYBE)
def test_applying_a_plan_without_conflicts_converges(name, local, base, remote):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, local, base, remote)
    if plan.conflicts or plan.other_cli:
        return
    state = _apply(adapter, plan, local, base, remote)
    again = _plan(adapter, *state)
    assert (again.writes, again.pulls, again.conflicts, again.other_cli) == (
        (),
        (),
        (),
        (),
    )
    assert again.base_updates == ()


@pytest.mark.parametrize("name", ADAPTERS)
@settings(max_examples=60, deadline=None)
@given(local=MAYBE, base=MAYBE, remote=MAYBE, theirs=st.booleans())
def test_no_write_goes_over_a_server_entity_that_differs_from_the_base(
    name, local, base, remote, theirs
):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, local, base, remote, remote_rev="theirs" if theirs else "r0")
    if [w for w in plan.writes if isinstance(w, adapter.writes)]:
        assert remote is None or remote == base
