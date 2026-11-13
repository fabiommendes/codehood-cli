"""
Tests for `codehood.push.run.apply`: how the base changes once a plan ran.
"""

from __future__ import annotations

from codehood.push.base import BaseEntry, BaseState
from codehood.push.calendar import Duration, TimeOfDay, TimeSlot
from codehood.push.plan import (
    BaseUpdate,
    Confirmation,
    DeleteResource,
    Plan,
    UpsertTimeSlot,
)
from codehood.push.run import OpResult, apply

SLOT = TimeSlot("mon", "MONDAY", TimeOfDay(14, 0), Duration(2, 0), "Lecture")
PUT = UpsertTimeSlot(SLOT)
DELETE = DeleteResource("old")

OLD = BaseEntry({"v": 0}, rev="r0", updated_at="t0")
LOCAL = BaseEntry({"v": 1})


def put_plan() -> Plan:
    update = BaseUpdate("time_slot", "mon", LOCAL)
    return Plan(writes=(PUT,), confirmations=(Confirmation(PUT, update),))


def test_a_successful_write_stores_the_local_payload_with_the_servers_stamp():
    results = [OpResult(PUT, True, "ok", rev="r1", updated_at="t1")]

    state = apply(BaseState(time_slots={"mon": OLD}), put_plan(), results)

    assert state.time_slots["mon"] == BaseEntry({"v": 1}, rev="r1", updated_at="t1")


def test_a_failed_write_keeps_the_previous_entry():
    state = apply(
        BaseState(time_slots={"mon": OLD}), put_plan(), [OpResult(PUT, False, "boom")]
    )

    assert state.time_slots["mon"] == OLD


def test_a_write_that_never_ran_keeps_the_previous_entry():
    state = apply(BaseState(time_slots={"mon": OLD}), put_plan(), [])

    assert state.time_slots["mon"] == OLD


def test_a_successful_delete_removes_the_entry():
    update = BaseUpdate("resource", "old", None)
    plan = Plan(writes=(DELETE,), confirmations=(Confirmation(DELETE, update),))

    state = apply(
        BaseState(resources={"old": OLD}), plan, [OpResult(DELETE, True, "ok")]
    )

    assert state.resources == {}


def test_a_failed_delete_keeps_the_entry():
    update = BaseUpdate("resource", "old", None)
    plan = Plan(writes=(DELETE,), confirmations=(Confirmation(DELETE, update),))

    state = apply(
        BaseState(resources={"old": OLD}), plan, [OpResult(DELETE, False, "no")]
    )

    assert state.resources == {"old": OLD}


def test_updates_without_a_write_apply_whatever_the_results():
    adopt = BaseUpdate("time_slot", "tue", BaseEntry({"v": 2}, "r2", "t2"))
    drop = BaseUpdate("resource", "old", None)
    plan = Plan(base_updates=(adopt, drop))

    state = apply(BaseState(resources={"old": OLD}), plan, [])

    assert state.time_slots == {"tue": BaseEntry({"v": 2}, "r2", "t2")}
    assert state.resources == {}


def test_conflicts_pulls_and_other_cli_leave_the_base_alone():
    from codehood.push.plan import Conflict, OtherCli, Pull

    plan = Plan(
        pulls=(Pull("time_slot", "mon", "update", ()),),
        conflicts=(Conflict("resource", "x", (), "both-changed"),),
        other_cli=(OtherCli("question", "q", ()),),
    )
    before = BaseState(time_slots={"mon": OLD}, resources={"x": OLD})

    assert apply(before, plan, []) == before


def test_apply_does_not_mutate_its_input():
    before = BaseState(time_slots={"mon": OLD})

    apply(before, put_plan(), [OpResult(PUT, True, "ok", rev="r1", updated_at="t1")])

    assert before.time_slots == {"mon": OLD}


def test_a_stamp_the_server_did_not_send_stays_empty():
    state = apply(BaseState(), put_plan(), [OpResult(PUT, True, "ok", updated_at="t1")])

    assert state.time_slots["mon"] == BaseEntry({"v": 1}, rev=None, updated_at="t1")


def test_exams_are_kept_in_the_base_through_a_push():
    from pathlib import Path

    from codehood.push.plan import UpsertExam

    op = UpsertExam("mid", {"slug": "mid"}, "DRAFT", "v1:x", Path("exams/mid.md"))
    plan = Plan(
        writes=(op,),
        confirmations=(Confirmation(op, BaseUpdate("exam", "mid", LOCAL)),),
    )
    before = BaseState(exams={"other": OLD})

    state = apply(before, plan, [OpResult(op, True, "ok", rev="r1", updated_at="t1")])

    assert state.exams == {
        "other": OLD,
        "mid": BaseEntry({"v": 1}, rev="r1", updated_at="t1"),
    }
