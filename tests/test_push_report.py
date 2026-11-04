"""
The pure half of what `codehood push` reports: the exit code, the summary
lines and the notice texts are functions of a `Plan` and the results, so
none of them needs a server or a `CliRunner`.
"""

from __future__ import annotations

from pathlib import Path

from codehood.cli.push import (
    describe_notice,
    dry_run_summary,
    exit_code,
    notice_line,
    run_summary,
)
from codehood.push.plan import (
    DeleteResource,
    KeptDraftPublished,
    KeptForRollCall,
    KeptPinnedSlot,
    KeptRepository,
    Plan,
    Rejected,
)
from codehood.push.run import OpResult

REJECTED = Rejected(slug="broken", path=Path("questions/broken.mdq"), reason="bad stem")
KEPT = KeptRepository(slug="old")
WRITE = DeleteResource(slug="a")


def _result(ok: bool, *, skipped: bool = False) -> OpResult:
    return OpResult(op=WRITE, ok=ok, message="", skipped=skipped)


def test_an_empty_plan_exits_zero():
    assert exit_code(Plan(), ()) == 0


def test_a_rejected_question_fails_the_push_even_when_every_write_succeeds():
    plan = Plan(writes=(WRITE,), notices=(REJECTED,))
    assert exit_code(plan, [_result(True)]) == 1


def test_a_kept_notice_does_not_fail_the_push():
    assert exit_code(Plan(notices=(KEPT,)), ()) == 0


def test_a_failed_write_fails_the_push():
    assert exit_code(Plan(writes=(WRITE,)), [_result(False)]) == 1


def test_failed_grade_columns_fail_the_push():
    assert exit_code(Plan(), (), grades_failed=True) == 1


def test_the_dry_run_summary_counts_writes_and_apart_the_invalid():
    plan = Plan(writes=(WRITE, WRITE), notices=(REJECTED, KEPT))
    assert dry_run_summary(plan) == (
        "summary: 2 operation(s) planned, 0 executed (--dry-run), 1 invalid"
    )


def test_the_dry_run_summary_without_rejections_has_no_invalid_count():
    assert "invalid" not in dry_run_summary(Plan(writes=(WRITE,), notices=(KEPT,)))


def test_the_run_summary_counts_only_writes():
    plan = Plan(writes=(WRITE, WRITE, WRITE), notices=(KEPT, KEPT))
    results = [_result(True), _result(False)]
    assert run_summary(plan, results, skipped=1) == (
        "summary: 2 operation(s) executed, 1 failed, 1 skipped"
    )


def test_writes_never_attempted_are_counted_apart_and_not_as_failed():
    results = [_result(False), _result(False, skipped=True)]
    assert run_summary(Plan(), results, skipped=0) == (
        "summary: 1 operation(s) executed, 1 failed, 0 skipped, 1 not attempted"
    )


def test_a_rejected_question_shows_in_the_run_summary_as_invalid_not_failed():
    summary = run_summary(Plan(notices=(REJECTED,)), [], skipped=0)
    assert summary.endswith("0 failed, 0 skipped, 1 invalid")


def test_only_a_rejection_is_printed_as_invalid():
    assert notice_line(REJECTED).startswith("invalid  question broken (broken.mdq): ")
    assert notice_line(KEPT).startswith("warning  ")


def test_notice_texts_keep_naming_the_flag_that_resolves_them():
    assert "--drop-repositories" in describe_notice(KEPT)
    assert "--drop-roll-calls" in describe_notice(KeptForRollCall(5, "mon", 32))
    assert "5/mon" in describe_notice(KeptForRollCall(5, "mon", 32))


def test_a_kept_draft_names_the_status_the_server_holds():
    notice = KeptDraftPublished(slug="q", status="PUBLISHED", path=Path("_q.mdq"))
    assert "kept PUBLISHED" in describe_notice(notice)


def test_a_pinned_slot_names_each_cancelled_week():
    assert describe_notice(KeptPinnedSlot("wed", (2,))) == (
        "time slot wed kept (event 2/wed is CANCELLED)"
    )
    assert describe_notice(KeptPinnedSlot("wed", (2, 4))) == (
        "time slot wed kept (events 2/wed, 4/wed are CANCELLED)"
    )
