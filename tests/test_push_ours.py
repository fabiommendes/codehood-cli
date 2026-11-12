"""
Tests for `codehood.push.ours`: settling conflicts in favour of the repository.
"""

from __future__ import annotations

from codehood.push.base import BaseEntry
from codehood.push.calendar import Duration, TimeOfDay, TimeSlot
from codehood.push.ours import ours_warnings, resolve_ours
from codehood.push.plan import (
    BaseUpdate,
    Confirmation,
    Conflict,
    DeleteResource,
    DeleteTimeSlot,
    Plan,
    Prune,
    Pull,
    Put,
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
