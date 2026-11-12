"""
Tests for `codehood.push.ours`: settling conflicts in favour of the repository.
"""

from __future__ import annotations

from codehood.models.repo import CourseKey
from codehood.push.base import BaseEntry
from codehood.push.calendar import Duration, Event, TimeOfDay, TimeSlot
from codehood.push.ours import ours_warnings, resolve_ours
from codehood.push.plan import (
    BaseUpdate,
    Confirmation,
    Conflict,
    DeleteCalendarEvent,
    DeleteResource,
    DeleteTimeSlot,
    OtherCli,
    Plan,
    Prune,
    Pull,
    Put,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertTimeSlot,
)

SLOT = TimeSlot("lab", "MONDAY", TimeOfDay(9, 0), Duration(1, 0), "Lab")
PUT = Put(
    UpsertTimeSlot(SLOT),
    base=BaseUpdate("time_slot", "lab", BaseEntry({"slug": "lab"})),
)
OLD_SLOT = Prune(DeleteTimeSlot("old"), base=BaseUpdate("time_slot", "old", None))


def conflict(kind="time_slot", key="lab", ours=(PUT,), **extra) -> Conflict:
    return Conflict(kind, key, ("title",), "both-changed", ours=ours, **extra)


def test_a_matching_conflict_becomes_its_writes_and_confirmations():
    plan = Plan(conflicts=(conflict(),))

    resolved = resolve_ours(plan, ["time_slot/lab"])

    assert resolved.conflicts == ()
    assert resolved.writes == (PUT.op,)
    assert resolved.confirmations == (Confirmation(PUT.op, PUT.base),)


def test_a_conflict_the_glob_does_not_match_stays():
    plan = Plan(conflicts=(conflict(),))

    assert resolve_ours(plan, ["resource/*"]) == plan


def test_no_globs_leave_the_plan_as_it_is():
    plan = Plan(conflicts=(conflict(),))

    assert resolve_ours(plan, []) == plan


def test_a_glob_matches_the_kind_and_the_key_together():
    plan = Plan(
        conflicts=(
            conflict("calendar_event", "1/mon", ours=(Put(DeleteResource("x")),)),
            conflict("calendar_event", "2/mon", ours=(Put(DeleteResource("y")),)),
            conflict("resource", "1/mon", ours=(Put(DeleteResource("z")),)),
        )
    )

    resolved = resolve_ours(plan, ["calendar_event/1/*"])

    assert [c.key for c in resolved.conflicts] == ["2/mon", "1/mon"]
    assert resolved.writes == (DeleteResource("x"),)


def test_a_conflict_without_a_resolution_stays_even_when_matched():
    plan = Plan(conflicts=(conflict(ours=()),))

    assert resolve_ours(plan, ["time_slot/lab"]) == plan


def test_a_rename_brings_both_operations_in_order():
    rename = conflict(
        "resource",
        "old",
        ours=(Put(DeleteResource("new")), Prune(DeleteResource("old"))),
        renamed_to="new",
    )

    resolved = resolve_ours(Plan(conflicts=(rename,)), ["resource/old"])

    assert resolved.writes == (DeleteResource("new"), DeleteResource("old"))
    assert resolved.conflicts == ()


def test_resolving_keeps_the_writes_and_pulls_already_in_the_plan():
    pull = Pull("resource", "r", "update", ())
    plan = Plan(writes=(OLD_SLOT.op,), pulls=(pull,), conflicts=(conflict(),))

    resolved = resolve_ours(plan, ["time_slot/lab"])

    assert resolved.writes == (OLD_SLOT.op, PUT.op)
    assert resolved.pulls == (pull,)


def test_a_glob_that_matches_no_conflict_is_reported():
    plan = Plan(conflicts=(conflict(),))

    warnings = ours_warnings(plan, ["time_slot/lab", "resource/none"])

    assert len(warnings) == 1
    assert "resource/none" in warnings[0]
    assert "matches no conflict" in warnings[0]


def test_a_matched_conflict_without_a_resolution_is_reported():
    plan = Plan(conflicts=(conflict(ours=()),))

    [warning] = ours_warnings(plan, ["time_slot/*"])

    assert "time_slot/lab" in warning
    assert "no automatic resolution" in warning


def test_conflicts_resolved_together_come_out_in_dependency_order():
    event = Put(UpsertCalendarEvent(Event(1, "lab", title="x")))
    resource = Put(DeleteResource("r"))
    plan = Plan(
        conflicts=(
            conflict("calendar_event", "1/lab", ours=(event,)),
            conflict("resource", "r", ours=(resource,)),
            conflict("time_slot", "lab", ours=(PUT,)),
        )
    )

    resolved = resolve_ours(plan, ["*"])

    assert resolved.writes == (PUT.op, event.op, resource.op)


def test_removals_run_before_the_upserts_they_make_room_for():
    gone_event = Prune(DeleteCalendarEvent(1, "old"))
    plan = Plan(
        writes=(UpsertCourse(CourseKey("d", "c", "e"), "", "", "", ""),),
        conflicts=(
            conflict(ours=(PUT,)),
            conflict("time_slot", "old", ours=(OLD_SLOT,)),
            conflict("calendar_event", "1/old", ours=(gone_event,)),
        ),
    )

    resolved = resolve_ours(plan, ["*"])

    assert resolved.writes[1:] == (gone_event.op, OLD_SLOT.op, PUT.op)
    assert isinstance(resolved.writes[0], UpsertCourse)


def test_an_other_cli_entry_is_settled_like_a_conflict():
    other = OtherCli("time_slot", "lab", ("title",), ours=(PUT,))
    plan = Plan(other_cli=(other,))

    resolved = resolve_ours(plan, ["time_slot/lab"])

    assert resolved.other_cli == ()
    assert resolved.writes == (PUT.op,)
    assert resolved.confirmations == (Confirmation(PUT.op, PUT.base),)


def test_an_other_cli_entry_the_glob_misses_stays():
    other = OtherCli("time_slot", "lab", ("title",), ours=(PUT,))
    plan = Plan(other_cli=(other,))

    assert resolve_ours(plan, ["resource/*"]) == plan


def test_warnings_cover_an_other_cli_entry():
    other = OtherCli("time_slot", "lab", ("title",), ours=(PUT,))
    bare = OtherCli("time_slot", "x", ())
    plan = Plan(other_cli=(other, bare))

    assert ours_warnings(plan, ["time_slot/lab"]) == ()
    [warning] = ours_warnings(plan, ["time_slot/x"])
    assert "time_slot/x" in warning
