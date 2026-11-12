"""
The text report of the decisions a three-way plan adds, and its exit code.
"""

from __future__ import annotations

from codehood.push.plan import (
    Conflict,
    DeleteResource,
    OtherCli,
    Plan,
    Prune,
    Pull,
    Put,
    ServerDrifted,
)
from codehood.push.report import (
    describe_conflict,
    describe_other_cli,
    describe_pull,
    describe_server_drifted,
    sync_exit_code,
    sync_lines,
    sync_summary,
)


def _put() -> Put:
    return Put(DeleteResource("a"))


def test_a_pull_of_a_creation_says_created_on_the_server_and_untouched_here():
    text = describe_pull(Pull("resource", "intro", "create", ("title",)))
    assert "resource intro" in text
    assert "created" in text
    assert "server" in text
    assert "not applied" in text


def test_a_pull_of_an_update_lists_the_fields():
    text = describe_pull(Pull("time_slot", "lab", "update", ("start", "end")))
    assert "time slot lab" in text
    assert "changed" in text
    assert "start, end" in text


def test_a_pull_of_a_removal_says_removed_on_the_server():
    text = describe_pull(Pull("question", "q1", "delete", ()))
    assert "question q1" in text
    assert "removed" in text


def test_a_conflict_with_ours_hints_the_glob():
    text = describe_conflict(
        Conflict("resource", "intro", ("title",), "both-changed", ours=(_put(),))
    )
    assert "resource intro" in text
    assert "title" in text
    assert "both" in text
    assert "--ours" in text
    assert "intro" in text.split("--ours")[1]


def test_a_conflict_without_ours_has_no_hint():
    text = describe_conflict(Conflict("resource", "intro", (), "link"))
    assert "--ours" not in text


def test_a_rename_conflict_shows_both_keys():
    text = describe_conflict(
        Conflict(
            "resource",
            "old",
            ("slug",),
            "rename",
            ours=(_put(), Prune(DeleteResource("old"))),
            renamed_to="new",
        )
    )
    assert "old" in text
    assert "new" in text
    assert "--ours" in text


def test_every_reason_has_a_text():
    reasons = [
        "both-changed",
        "local-edited-remote-deleted",
        "local-deleted-remote-edited",
        "no-base",
        "rename",
        "link",
        "referenced",
    ]
    texts = {
        describe_conflict(Conflict("course", "c", (), reason))  # type: ignore[arg-type]
        for reason in reasons
    }
    assert len(texts) == len(reasons)


def test_other_cli_suggests_git_pull():
    text = describe_other_cli(OtherCli("resource", "intro", ("body", "title")))
    assert "resource intro" in text
    assert "body, title" in text
    assert "git pull" in text


def test_server_drifted_says_the_server_value_is_overwritten():
    text = describe_server_drifted(ServerDrifted("grade_column", "p1", ("note",)))
    assert "grade column p1" in text
    assert "note" in text
    assert "overwritten" in text


def test_lines_carry_every_new_decision_and_the_drifted_notice():
    plan = Plan(
        notices=(ServerDrifted("grade_column", "p1", ("note",)),),
        pulls=(Pull("resource", "a", "create", ()),),
        conflicts=(Conflict("resource", "b", (), "no-base"),),
        other_cli=(OtherCli("resource", "c", ("title",)),),
    )
    lines = sync_lines(plan)
    joined = "\n".join(lines)
    for key in ("p1", "resource a", "resource b", "resource c"):
        assert key in joined


def test_a_plan_without_new_decisions_renders_nothing():
    assert sync_lines(Plan(writes=(DeleteResource("a"),))) == []
    assert sync_summary(Plan()) == ""


def test_the_summary_counts_each_decision():
    plan = Plan(
        pulls=(Pull("resource", "a", "create", ()),) * 2,
        conflicts=(Conflict("resource", "b", (), "no-base"),),
        other_cli=(OtherCli("resource", "c", ()),) * 3,
    )
    assert sync_summary(plan) == ("sync: 2 pulled, 1 conflict(s), 3 from another CLI")


def test_exit_code_is_zero_for_a_clean_plan():
    assert sync_exit_code(Plan()) == 0


def test_exit_code_is_zero_with_only_pulls_or_other_cli():
    assert sync_exit_code(Plan(pulls=(Pull("resource", "a", "update", ()),))) == 0
    assert sync_exit_code(Plan(other_cli=(OtherCli("resource", "a", ()),))) == 0


def test_exit_code_fails_when_a_conflict_remains():
    plan = Plan(conflicts=(Conflict("resource", "a", (), "both-changed"),))
    assert sync_exit_code(plan) == 1
