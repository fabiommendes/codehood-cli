"""
Tests for `codehood.push.plan.plan_sync`, the three-way planner: one row of
the RFC's decision table per case, per resource type, then the special cases
and the two properties (convergence, and safety of `Put` and `Prune`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from functools import cache
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
    Prune,
    Put,
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


@cache
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
    return {"questions": {"q": ServerQuestion(version, entry, "PUBLISHED")}}


def _remote_slot(variant, payload, rev, ref):
    return {"time_slots": {"t": RemoteEntry(payload, None, "u")}}


def _remote_event(variant, payload, rev, ref):
    entry = RemoteEntry(payload, rev, "u")
    return {"calendar_events": {(1, "t"): ServerEvent(rev or "", "REGULAR", entry)}}


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
@pytest.mark.parametrize(
    ("local", "base", "remote", "ours"),
    [
        ("b", "a", "c", "put"),
        (None, "a", "b", "prune"),
        (None, None, "b", "prune"),
    ],
)
def test_other_cli_carries_the_local_side_as_ours(name, local, base, remote, ours):
    adapter = ADAPTERS[name]
    plan = _plan(adapter, local, base, remote, remote_rev="theirs")
    [other] = [o for o in plan.other_cli if o.kind == adapter.kind]
    [op] = other.ours
    assert isinstance(op, Put if ours == "put" else Prune)
    assert op.base is not None
    assert (op.base.entry is None) == (ours == "prune")
    assert plan.writes == () or not any(
        isinstance(w, adapter.writes) for w in plan.writes
    )


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
    assert [(o.key, o.renamed_to) for o in plan.other_cli] == [("old", "new")]
    assert plan.writes == () and plan.conflicts == ()
    [other] = plan.other_cli
    assert [type(c.op) for c in other.ours] == [UpsertResource, DeleteResource]


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
            "q": ServerQuestion("v", RemoteEntry(payload, "r0", "u"), remote_status)
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


def test_a_draft_file_over_a_hidden_question_does_not_notice():
    plan = _q_plan(_question("a", draft=True), "HIDDEN")
    assert plan.writes == () and plan.notices == ()


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
    return ServerEvent(rev, kind, entry, attendances)


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
    return ServerEvent("r0", "REGULAR", entry)


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
# Review findings
#
def test_a_new_invalid_question_is_rejected_as_plan_from_server_does():
    invalid = InvalidQuestion(slug="q", path=Path("questions/q.md"), reason="bad")
    local = LocalState(KEY, DESCRIPTION, START, END, questions=(invalid,))
    base = BaseState(course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)})
    server = ServerState(
        course_exists=True, course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF)
    )
    plan = plan_sync(local, base, server)
    assert [type(n) for n in plan.notices] == [Rejected]
    assert plan.writes == () and plan.conflicts == ()


def _slot_state(*, base_events=(), server_events=None, server_slot=True):
    base = BaseState(
        course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
        time_slots={"t": BaseEntry(time_slot_payload(_slot("a")), None)},
        calendar_events={
            event_key(w, s): BaseEntry(event_payload(_event("a", w, s)), "r0")
            for w, s in base_events
        },
    )
    return _cal(
        base=base,
        events=server_events or {},
        slots={"t": RemoteEntry(time_slot_payload(_slot("a")))} if server_slot else {},
    )


def _no_slot_delete(plan):
    assert not [w for w in plan.writes if isinstance(w, DeleteTimeSlot)]


def test_a_slot_is_not_deleted_under_an_event_edited_on_the_server():
    plan = _slot_state(
        base_events=[(1, "t")], server_events={(1, "t"): _server_event("b")}
    )
    _no_slot_delete(plan)
    assert [(c.kind, c.key) for c in plan.conflicts] == [
        ("calendar_event", "1/t"),
        ("time_slot", "t"),
    ]
    [slot] = [c for c in plan.conflicts if c.kind == "time_slot"]
    assert slot.fields == ("1/t",) and slot.reason == "referenced"


def test_a_slot_is_not_deleted_under_an_event_created_on_the_server():
    entry = RemoteEntry(event_payload(_event("a", 2, "t")), None, "u")
    plan = _slot_state(server_events={(2, "t"): ServerEvent("", "REGULAR", entry)})
    _no_slot_delete(plan)
    assert [c.key for c in plan.conflicts if c.kind == "time_slot"] == ["t"]


def test_a_slot_is_deleted_when_its_events_are_deleted_too():
    plan = _slot_state(
        base_events=[(1, "t")], server_events={(1, "t"): _server_event("a")}
    )
    assert [type(w) for w in plan.writes if not isinstance(w, UpsertCourse)] == [
        DeleteCalendarEvent,
        DeleteTimeSlot,
    ]


def test_a_lost_lesson_link_without_a_base_is_a_conflict():
    from codehood.push.calendar import EventKey

    file = _resource("a", event=EventKey(2, "t"))
    plan = plan_sync(
        LocalState(KEY, DESCRIPTION, START, END, resources=(file,)),
        BaseState(course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)}),
        ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            resources={
                "r": RemoteEntry(resource_payload(_resource("a")), file.ref, "u")
            },
        ),
    )
    assert [(c.kind, c.reason) for c in plan.conflicts] == [("resource", "link")]
    assert plan.pulls == ()


def test_the_question_promoted_locally_after_both_sides_edited_it_the_same_is_put():
    plan = _q_plan(_question("b"), "DRAFT", entry_variant="b", base="a")
    [write] = plan.writes
    assert isinstance(write, UpsertQuestion) and write.status == "PUBLISHED"
    [confirmation] = plan.confirmations
    assert confirmation.update.entry == BaseEntry(question_payload(_question("b")))


def _grade_state(local, base, remote, *, base_rev=COLUMN.rev, remote_rev=COLUMN.rev):
    return plan_sync(
        LocalState(KEY, DESCRIPTION, START, END, grade_columns=local),
        BaseState(
            course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
            grade_columns={
                c.slug: BaseEntry(grade_column_payload(c), base_rev, "u") for c in base
            },
        ),
        ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            grade_columns={
                c.slug: RemoteEntry(grade_column_payload(c), remote_rev, "u")
                for c in remote
            },
        ),
    )


DRIFT = (ServerDrifted("grade_column", "total", ("values",)),)


def test_a_grade_column_edited_on_the_server_keeping_its_rev_is_overwritten():
    plan = _grade_state((COLUMN,), (COLUMN,), (EDITED,))
    assert [type(w) for w in plan.writes] == [UpsertGradeColumn]
    assert plan.notices == DRIFT


def test_a_grade_column_edited_on_the_server_without_a_base_is_overwritten():
    plan = _grade_state((COLUMN,), (), (EDITED,))
    assert [type(w) for w in plan.writes] == [UpsertGradeColumn]
    assert plan.notices == DRIFT
    assert plan.base_updates == ()
    [confirmation] = plan.confirmations
    assert confirmation.update.entry == BaseEntry(grade_column_payload(COLUMN))


def test_a_grade_column_without_a_server_rev_and_a_base_is_overwritten_with_a_notice():
    plan = _grade_state((COLUMN,), (), (EDITED,), remote_rev=None)
    assert [type(w) for w in plan.writes] == [UpsertGradeColumn]
    assert plan.notices == DRIFT


def test_a_grade_column_with_another_rev_and_no_base_is_overwritten_quietly():
    plan = _grade_state((COLUMN,), (), (EDITED,), remote_rev="other")
    assert [type(w) for w in plan.writes] == [UpsertGradeColumn]
    assert plan.notices == ()


def test_a_grade_column_the_server_holds_as_the_file_is_adopted_into_the_base():
    plan = _grade_state((COLUMN,), (), (COLUMN,))
    assert plan.writes == () and plan.notices == ()
    [update] = plan.base_updates
    assert update.entry == BaseEntry(grade_column_payload(COLUMN), COLUMN.rev, "u")


def test_a_grade_column_that_exists_only_on_the_server_is_pruned_with_a_notice():
    plan = _grade_state((), (), (COLUMN,))
    assert [type(w) for w in plan.writes] == [DeleteGradeColumn]
    [notice] = plan.notices
    assert notice == ServerDrifted(
        "grade_column", "total", diff_fields(None, grade_column_payload(COLUMN))
    )


#
# Properties
#
VARIANTS = (None, "a", "b", "c")
BASE_REVS = ("r0", None)
REMOTE_REVS = ("r0", "other", None, "local-ref")


def _grade(variant: str) -> GradeColumn:
    value = {"a": 7.0, "b": 8.0, "c": 9.0}[variant]
    return GradeColumn("total", "Total", "number", 0, (("ana", value),))


def _remote_grade(variant, payload, rev, ref):
    return {"grade_columns": {"total": RemoteEntry(payload, rev, "u")}}


#: One-way: only the properties run over it, the decision table does not hold.
GRADE = Adapter(
    "grade_column",
    "total",
    True,
    _grade,
    lambda v: grade_column_payload(_grade(v)),
    lambda v: _grade(v).rev,
    lambda e: {"grade_columns": (e,)},
    _remote_grade,
    "grade_columns",
    (UpsertGradeColumn, DeleteGradeColumn),
    UpsertGradeColumn,
    DeleteGradeColumn,
)
EVERY_ADAPTER = {**ADAPTERS, "grade_column": GRADE}


def _space(adapters):
    """
    Every `(name, local, base, remote, base_rev, remote_rev)`; a type without
    a `rev` has one point per revision, not eight.
    """
    return [
        (name, local, base, remote, base_rev, remote_rev)
        for name in adapters
        for local in VARIANTS
        for base in VARIANTS
        for remote in VARIANTS
        for base_rev in (BASE_REVS if adapters[name].has_rev else BASE_REVS[:1])
        for remote_rev in (REMOTE_REVS if adapters[name].has_rev else REMOTE_REVS[:1])
    ]


SPACE = _space(EVERY_ADAPTER)
SPACE_WITHOUT_GRADES = _space(ADAPTERS)


def _exhaustive(adapter, local, base, remote, base_rev, remote_rev) -> Plan:
    """
    Plan one point of `SPACE`, where "local-ref" is the hash of the local
    side, the one a server `rev` equals when this checkout sent the entity.
    """
    ref = adapter.ref(local) if local is not None else None
    state = _scenario(
        adapter,
        local,
        base,
        remote,
        base_rev=base_rev,
        remote_rev=ref if remote_rev == "local-ref" else remote_rev,
        remote_ref=ref if remote_rev == "local-ref" else None,
    )
    if adapter is GRADE and local is None:
        state = (replace(state[0], grade_columns=()), *state[1:])
    return plan_sync(*state)


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


@pytest.mark.parametrize(
    ("name", "local", "base", "remote", "base_rev", "remote_rev"), SPACE
)
def test_applying_a_plan_without_conflicts_converges(
    name, local, base, remote, base_rev, remote_rev
):
    adapter = EVERY_ADAPTER[name]
    plan = _exhaustive(adapter, local, base, remote, base_rev, remote_rev)
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


@pytest.mark.parametrize(
    ("name", "local", "base", "remote", "base_rev", "remote_rev"),
    SPACE_WITHOUT_GRADES,
)
def test_no_write_goes_over_a_server_entity_that_differs_from_the_base(
    name, local, base, remote, base_rev, remote_rev
):
    adapter = ADAPTERS[name]
    plan = _exhaustive(adapter, local, base, remote, base_rev, remote_rev)
    if [w for w in plan.writes if isinstance(w, adapter.writes)]:
        assert remote is None or remote == base or remote == local


@pytest.mark.parametrize(
    ("name", "local", "base", "remote", "base_rev", "remote_rev"), SPACE
)
def test_the_base_never_adopts_a_payload_the_server_does_not_hold(
    name, local, base, remote, base_rev, remote_rev
):
    adapter = EVERY_ADAPTER[name]
    plan = _exhaustive(adapter, local, base, remote, base_rev, remote_rev)
    for update in plan.base_updates:
        if update.kind == adapter.kind and update.entry is not None:
            assert remote is not None
            assert update.entry.payload == adapter.payload(remote)


@pytest.mark.parametrize(
    ("local", "base", "remote", "base_rev", "remote_rev"),
    [point[1:] for point in SPACE if point[0] == "grade_column"],
)
def test_a_grade_column_is_overwritten_whenever_the_server_differs(
    local, base, remote, base_rev, remote_rev
):
    plan = _exhaustive(GRADE, local, base, remote, base_rev, remote_rev)
    deleted = [w for w in plan.writes if isinstance(w, DeleteGradeColumn)]
    put = [w for w in plan.writes if isinstance(w, UpsertGradeColumn)]
    if local is None:
        assert bool(deleted) == (remote is not None)
    elif remote != local:
        assert put
    else:
        assert not put


#
# Calendar, slots and events together
#
SLOTS = ("t", "u")
EVENT_KEYS = [(week, slot) for week in (1, 2) for slot in SLOTS]
SLOT_SIDE = st.dictionaries(st.sampled_from(SLOTS), st.sampled_from("abc"))
EVENT_SIDE = st.dictionaries(st.sampled_from(EVENT_KEYS), st.sampled_from("abc"))
SERVER_EVENT = st.tuples(
    st.sampled_from("abc"),
    st.sampled_from(["REGULAR", "REGULAR", "CANCELLED"]),
    st.sampled_from([None, None, 3]),
    st.sampled_from(["r0", "other", None]),
)
#: A resource side: for each slug, `None` (no lesson) or the lesson it links to.
RESOURCE_SIDE = st.dictionaries(
    st.sampled_from(["r1", "r2"]), st.sampled_from([None, *EVENT_KEYS])
)


@settings(max_examples=400, deadline=None)
@given(
    local_slots=SLOT_SIDE,
    local_events=EVENT_SIDE,
    base_slots=SLOT_SIDE,
    base_events=EVENT_SIDE,
    server_slots=SLOT_SIDE,
    server_events=st.dictionaries(st.sampled_from(EVENT_KEYS), SERVER_EVENT),
    drop_roll_calls=st.booleans(),
    local_resources=RESOURCE_SIDE,
    base_resources=RESOURCE_SIDE,
    server_resources=RESOURCE_SIDE,
)
def test_no_slot_is_deleted_while_an_event_still_holds_it(
    local_slots,
    local_events,
    base_slots,
    base_events,
    server_slots,
    server_events,
    drop_roll_calls,
    local_resources,
    base_resources,
    server_resources,
):
    from codehood.push.calendar import EventKey

    def file(slug, lesson):
        return _resource("a", slug, EventKey(*lesson) if lesson else None)

    events = {}
    for (week, slot), (variant, kind, attendances, rev) in server_events.items():
        entry = RemoteEntry(event_payload(_event(variant, week, slot)), rev, "u")
        events[(week, slot)] = ServerEvent(rev or "", kind, entry, attendances)
    plan = plan_sync(
        LocalState(
            KEY,
            DESCRIPTION,
            START,
            END,
            slots=tuple(_slot(v, s) for s, v in local_slots.items()),
            events=tuple(_event(v, w, s) for (w, s), v in local_events.items()),
            resources=tuple(file(k, v) for k, v in local_resources.items()),
        ),
        BaseState(
            course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
            time_slots={
                s: BaseEntry(time_slot_payload(_slot(v, s)))
                for s, v in base_slots.items()
            },
            calendar_events={
                event_key(w, s): BaseEntry(event_payload(_event(v, w, s)), "r0")
                for (w, s), v in base_events.items()
            },
            resources={
                k: BaseEntry(resource_payload(file(k, v)), "r0")
                for k, v in base_resources.items()
            },
        ),
        ServerState(
            course_exists=True,
            course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
            time_slots={
                s: RemoteEntry(time_slot_payload(_slot(v, s)))
                for s, v in server_slots.items()
            },
            calendar_events=events,
            resources={
                k: RemoteEntry(resource_payload(file(k, v)), "r0")
                for k, v in server_resources.items()
            },
        ),
        drop_roll_calls=drop_roll_calls,
    )
    linked = dict(server_resources)
    for write in plan.writes:
        if isinstance(write, DeleteResource):
            linked.pop(write.slug, None)
        elif isinstance(write, UpsertResource) and write.slug in linked:
            linked[write.slug] = (
                (write.event.week, write.event.time_slot) if write.event else None
            )
    for write in plan.writes:
        if isinstance(write, DeleteCalendarEvent):
            assert (write.week, write.time_slot) not in set(linked.values())
    after = set(events)
    for write in plan.writes:
        if isinstance(write, DeleteCalendarEvent):
            after.discard((write.week, write.time_slot))
        elif isinstance(write, UpsertCalendarEvent):
            after.add((write.event.week, write.event.time_slot))
    for write in plan.writes:
        if isinstance(write, DeleteTimeSlot):
            assert write.slug not in {slot for _, slot in after}


#
# Events a server resource is still linked to
#
def _linked_state(
    *, local_link=None, base_link=None, server_link, event_local=False, drop=False
):
    """
    One resource `r` and the lesson `1/thu`, gone from the checkout, with the
    resource linked on the server as `server_link` says.
    """
    from codehood.push.calendar import EventKey

    def file(link):
        return _resource("a", event=EventKey(*link) if link else None)

    local = LocalState(
        KEY,
        DESCRIPTION,
        START,
        END,
        resources=(file(local_link),),
        events=(_event("a", 1, "thu"),) if event_local else (),
    )
    base = BaseState(
        course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
        resources={"r": BaseEntry(resource_payload(file(base_link)), "r0")},
        calendar_events={
            "1/thu": BaseEntry(event_payload(_event("a", 1, "thu")), "r0")
        },
    )
    server = ServerState(
        course_exists=True,
        course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
        resources={"r": RemoteEntry(resource_payload(file(server_link)), "r0")},
        calendar_events={(1, "thu"): _server_event_for(1, "thu")},
    )
    return local, base, server


def _apply_base_updates(base: BaseState, plan: Plan) -> BaseState:
    fields = {
        "resource": "resources",
        "time_slot": "time_slots",
        "calendar_event": "calendar_events",
    }
    changes = {}
    for update in plan.base_updates:
        name = fields[update.kind]
        entries = dict(changes.get(name, getattr(base, name)))
        if update.entry is None:
            entries.pop(update.key, None)
        else:
            entries[update.key] = update.entry
        changes[name] = entries
    return replace(base, **changes)


def test_an_event_a_server_resource_links_to_is_not_pruned():
    local, base, server = _linked_state(server_link=(1, "thu"))
    plan = plan_sync(local, base, server)
    assert not [w for w in plan.writes if isinstance(w, DeleteCalendarEvent)]
    [conflict] = [c for c in plan.conflicts if c.kind == "calendar_event"]
    assert (conflict.key, conflict.reason, conflict.fields) == (
        "1/thu",
        "referenced",
        ("r",),
    )
    assert not [d for d in conflict.ours if isinstance(d, Prune)]


def test_an_event_is_pruned_when_the_plan_moves_the_linked_resource_away():
    local, base, server = _linked_state(base_link=(1, "thu"), server_link=(1, "thu"))
    plan = plan_sync(local, base, server)
    assert [type(w) for w in plan.writes if not isinstance(w, UpsertCourse)] == [
        DeleteCalendarEvent,
        UpsertResource,
    ]
    assert plan.conflicts == ()


def test_an_event_is_pruned_when_the_plan_deletes_the_linked_resource():
    local, base, server = _linked_state(base_link=(1, "thu"), server_link=(1, "thu"))
    local = replace(local, resources=())
    plan = plan_sync(local, base, server)
    assert {type(w) for w in plan.writes} >= {DeleteCalendarEvent, DeleteResource}


def test_a_referenced_event_edited_by_another_cli_does_not_offer_its_prune():
    local, base, server = _linked_state(server_link=(1, "thu"))
    entry = RemoteEntry(event_payload(_event("b", 1, "thu")), "other", "u")
    server = replace(
        server, calendar_events={(1, "thu"): ServerEvent("other", "REGULAR", entry)}
    )
    plan = plan_sync(local, base, server)
    [other] = [o for o in plan.other_cli if o.kind == "calendar_event"]
    assert not [d for d in other.ours if isinstance(d, Prune)]


def test_the_reference_conflict_of_an_event_is_stable_across_pushes():
    local, base, server = _linked_state(server_link=(1, "thu"))
    first = plan_sync(local, base, server)
    again = plan_sync(local, _apply_base_updates(base, first), server)
    assert again == first
    assert [c.reason for c in again.conflicts if c.kind == "calendar_event"] == [
        "referenced"
    ]


#
# Events kept for their roll call
#
def _rollcall_state(*, with_base: bool, rev: str | None = "r0", slot=True):
    base = BaseState(
        course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
        calendar_events={"1/t": BaseEntry(event_payload(_event("a")), "r0")}
        if with_base
        else {},
        time_slots={"t": BaseEntry(time_slot_payload(_slot("a")))}
        if with_base and slot
        else {},
    )
    server = ServerState(
        course_exists=True,
        course=RemoteEntry(COURSE_PAYLOAD, COURSE_REF),
        calendar_events={(1, "t"): _server_event(attendances=3, rev=rev)},
        time_slots={"t": RemoteEntry(time_slot_payload(_slot("a")))} if slot else {},
    )
    return LocalState(KEY, DESCRIPTION, START, END), base, server


def _quiet(plan: Plan) -> bool:
    return (
        plan.writes == ()
        and plan.pulls == ()
        and plan.other_cli == ()
        and plan.conflicts == ()
    )


@pytest.mark.parametrize("with_base", [True, False])
@pytest.mark.parametrize("rev", ["r0", "other", None])
def test_an_event_with_a_roll_call_is_kept_with_or_without_a_base(with_base, rev):
    local, base, server = _rollcall_state(with_base=with_base, rev=rev)
    plan = plan_sync(local, base, server)
    assert [type(n) for n in plan.notices] == [KeptForRollCall]
    assert _quiet(plan)


@pytest.mark.parametrize("with_base", [True, False])
def test_a_kept_event_is_stable_and_its_slot_is_left_alone(with_base):
    local, base, server = _rollcall_state(with_base=with_base, rev="other")
    first = plan_sync(local, base, server)
    base = _apply_base_updates(base, first)
    assert base.calendar_events["1/t"].rev == "other"
    again = plan_sync(local, base, server)
    assert [type(n) for n in again.notices] == [KeptForRollCall]
    assert _quiet(again) and again.base_updates == ()


def test_a_slot_only_the_server_has_for_a_kept_event_is_not_pulled():
    local, base, server = _rollcall_state(with_base=False, rev="other")
    assert _quiet(plan_sync(local, base, server))


def test_dropping_roll_calls_prunes_the_event_the_base_agrees_with():
    local, base, server = _rollcall_state(with_base=True)
    plan = plan_sync(local, base, server, drop_roll_calls=True)
    assert [type(w) for w in plan.writes if not isinstance(w, UpsertCourse)][:2] == [
        DeleteRollCall,
        DeleteCalendarEvent,
    ]
    assert plan.notices == ()


def test_dropping_roll_calls_of_an_event_without_a_base_offers_the_prune_as_ours():
    local, base, server = _rollcall_state(with_base=False, rev="other")
    plan = plan_sync(local, base, server, drop_roll_calls=True)
    assert plan.writes == ()
    [other] = plan.other_cli
    assert [type(d.op) for d in other.ours if isinstance(d, Prune)] == [
        DeleteCalendarEvent
    ]
    assert not [p for p in plan.pulls if p.kind == "time_slot"]


#
# A slot deleted locally and edited on the server, still in use
#
def test_a_slot_deleted_locally_and_edited_on_the_server_does_not_offer_its_prune():
    entry = RemoteEntry(event_payload(_event("a", 2, "t")), None, "u")
    base = BaseState(
        course={"course": BaseEntry(COURSE_PAYLOAD, COURSE_REF)},
        time_slots={"t": BaseEntry(time_slot_payload(_slot("a")), None)},
    )
    plan = _cal(
        base=base,
        events={(2, "t"): ServerEvent("", "REGULAR", entry)},
        slots={"t": RemoteEntry(time_slot_payload(_slot("b")))},
    )
    [conflict] = [c for c in plan.conflicts if c.kind == "time_slot"]
    assert conflict.reason == "local-deleted-remote-edited"
    assert not [d for d in conflict.ours if isinstance(d, Prune)]
    _no_slot_delete(plan)


#
# The hash covers every field of the payload
#
def _mutations(payload: Payload, changes: dict[str, Any]) -> list[Payload]:
    return [{**payload, key: value} for key, value in changes.items()]


def test_the_event_hash_changes_with_every_field_of_its_payload():
    base = Event(1, "t", title="a", description="d", kind="REGULAR")
    variants = [
        replace(base, title="b"),
        replace(base, description="e"),
        replace(base, kind="HOLIDAY"),
        replace(base, repositories=("x",)),
    ]
    assert len({v.ref for v in variants} | {base.ref}) == len(variants) + 1
    for variant in variants:
        assert event_payload(variant) != event_payload(base)
    assert set(event_payload(base)) - {"week", "timeSlot"} == {
        "kind",
        "title",
        "description",
        "repositories",
    }


def test_the_resource_hash_changes_with_every_field_of_its_payload():
    from codehood.push.calendar import EventKey
    from codehood.push.resource import CodeData, LinkData

    def ref(title="t", description=None, data=None, event=None):
        return content_ref(title, description, data or MdData("c"), event)

    base = ref()
    others = [
        ref(title="u"),
        ref(description="d"),
        ref(data=MdData("d")),
        ref(data=CodeData("c", "python")),
        ref(data=CodeData("c", "ruby")),
        ref(data=LinkData("http://x")),
        ref(event=EventKey(1, "t")),
        ref(event=EventKey(2, "t")),
        ref(event=EventKey(1, "u")),
    ]
    assert len({base, *others}) == len(others) + 1


def test_the_course_hash_changes_with_every_field_of_its_payload():
    base = course_ref("d", "s", "e")
    assert len({base, course_ref("x", "s", "e"), course_ref("d", "x", "e")}) == 3
    assert course_ref("d", "s", "x") != base


def test_the_grade_column_hash_changes_with_every_field_of_its_payload():
    base = GradeColumn("g", "T", "number", 0, (("ada", 1.0),))
    variants = [
        replace(base, title="U"),
        replace(base, kind="text"),
        replace(base, position=1),
        replace(base, values=(("ada", 2.0),)),
        replace(base, values=(("bob", 1.0),)),
    ]
    assert len({v.rev for v in variants} | {base.rev}) == len(variants) + 1
    assert set(grade_column_payload(base)) - {"slug"} == {
        "title",
        "kind",
        "position",
        "values",
    }


def test_a_kind_changed_on_the_server_without_a_base_is_a_conflict_not_a_pull():
    local = _event("a")
    holiday = replace(local, kind="HOLIDAY")
    entry = RemoteEntry(event_payload(holiday), holiday.ref, "u")
    plan = _cal((local,), events={(1, "t"): ServerEvent(holiday.ref, "HOLIDAY", entry)})
    assert [(c.key, c.reason) for c in plan.conflicts] == [("1/t", "no-base")]
    assert plan.pulls == ()


def test_a_kind_changed_locally_without_a_base_is_a_conflict_not_a_pull():
    server = _event("a")
    holiday = replace(server, kind="HOLIDAY")
    entry = RemoteEntry(event_payload(server), server.ref, "u")
    plan = _cal(
        (holiday,), events={(1, "t"): ServerEvent(server.ref, "REGULAR", entry)}
    )
    assert [(c.key, c.reason) for c in plan.conflicts] == [("1/t", "no-base")]
    assert plan.pulls == ()
