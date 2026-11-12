"""
The text report of the decisions a three-way plan adds to a push: `Pull`,
`Conflict`, `OtherCli` and the `ServerDrifted` notice, plus the exit code
they imply.

Everything here is a pure function of a `Plan`. The report of a `Put`,
`Prune`, `Keep` and `Skip` stays with the command.
"""

from __future__ import annotations

from typing import assert_never

from .plan import (
    Conflict,
    ConflictReason,
    Decision,
    EntityKind,
    Keep,
    KeptCancelled,
    KeptDraftPublished,
    KeptForRollCall,
    KeptPinnedSlot,
    KeptRepository,
    Notice,
    OtherCli,
    Plan,
    Prune,
    Pull,
    Put,
    Rejected,
    ServerDrifted,
    Skip,
)

__all__ = [
    "describe_conflict",
    "describe_decision",
    "describe_notice_drift",
    "describe_other_cli",
    "describe_pull",
    "describe_server_drifted",
    "sync_exit_code",
    "sync_lines",
    "sync_summary",
]

#: How each kind of entity reads in a line.
KIND_LABELS: dict[EntityKind, str] = {
    "course": "course",
    "resource": "resource",
    "question": "question",
    "time_slot": "time slot",
    "calendar_event": "calendar event",
    "grade_column": "grade column",
}

#: Why each kind of conflict is one, as a clause after "conflict".
REASON_TEXTS: dict[ConflictReason, str] = {
    "both-changed": "changed both here and on the server",
    "local-edited-remote-deleted": "edited here, removed on the server",
    "local-deleted-remote-edited": "removed here, edited on the server",
    "both-new": "created both here and on the server",
    "no-base": "differs from the server and has no recorded base",
    "rename": "renamed here, changed on the server",
    "link": "its lesson link changed",
    "referenced": "removed on the server but still referenced here",
}

#: What a `Pull` did on the server, as a clause.
CHANGE_TEXTS = {
    "create": "created on the server",
    "update": "changed on the server",
    "delete": "removed from the server",
}


def describe_pull(pull: Pull) -> str:
    """
    Render a `Pull`: the server's change, left unapplied and unoverwritten.
    """
    text = (
        f"pull  {_entity(pull.kind, pull.key)} {CHANGE_TEXTS[pull.change]}; "
        "not applied here, and the server's version was not overwritten"
    )
    return text + _fields(pull.fields)


def describe_conflict(conflict: Conflict) -> str:
    """
    Render a `Conflict`, with the `--ours` hint when the repository's side
    can settle it.
    """
    name = _entity(conflict.kind, conflict.key)
    if conflict.renamed_to is not None:
        name += f" -> {conflict.renamed_to}"
    text = f"conflict  {name}: {REASON_TEXTS[conflict.reason]}"
    text += _fields(conflict.fields)
    if conflict.ours:
        text += f"; to keep the local version, push with --ours {conflict.key}"
    return text


def describe_other_cli(other: OtherCli) -> str:
    """
    Render an `OtherCli`: a change made through another CLI.
    """
    return (
        f"other cli  {_entity(other.kind, other.key)} changed on the server "
        f"through another CLI; run `git pull` before pushing{_fields(other.fields)}"
    )


def describe_server_drifted(notice: ServerDrifted) -> str:
    """
    Render a `ServerDrifted` notice: the fields of the server's copy that the
    push overwrites.
    """
    return (
        f"warning  {_entity(notice.kind, notice.key)} was changed on the server; "
        f"it will be overwritten by this push{_fields(notice.fields)}"
    )


def describe_notice_drift(notice: Notice) -> str | None:
    """
    Render a notice that belongs to this report, `None` for the others.
    """
    match notice:
        case ServerDrifted():
            return describe_server_drifted(notice)
        case (
            Rejected()
            | KeptDraftPublished()
            | KeptPinnedSlot()
            | KeptForRollCall()
            | KeptRepository()
            | KeptCancelled()
        ):
            return None
        case _:
            assert_never(notice)


def describe_decision(decision: Decision) -> str | None:
    """
    Render a decision that belongs to this report, `None` for the writes and
    the quiet ones.
    """
    match decision:
        case Pull():
            return describe_pull(decision)
        case Conflict():
            return describe_conflict(decision)
        case OtherCli():
            return describe_other_cli(decision)
        case Skip() | Put() | Prune() | Keep():
            return None
        case _:
            assert_never(decision)


def sync_lines(plan: Plan) -> list[str]:
    """
    The lines for every drift notice, `Pull`, `Conflict` and `OtherCli` of
    the plan, in that order. Empty when the plan has none.
    """
    lines = [
        line for n in plan.notices if (line := describe_notice_drift(n)) is not None
    ]
    for decisions in (plan.pulls, plan.conflicts, plan.other_cli):
        lines.extend(
            line for d in decisions if (line := describe_decision(d)) is not None
        )
    return lines


def sync_summary(plan: Plan) -> str:
    """
    The summary line with the count of each new decision, empty when there
    are none.
    """
    if not (plan.pulls or plan.conflicts or plan.other_cli):
        return ""
    return (
        f"sync: {len(plan.pulls)} pulled, {len(plan.conflicts)} conflict(s), "
        f"{len(plan.other_cli)} from another CLI"
    )


def sync_exit_code(plan: Plan) -> int:
    """
    The exit code the decisions imply: 1 while a `Conflict` remains, else 0.

    A `Pull` and an `OtherCli` leave the code to the rest of the push.
    """
    return int(bool(plan.conflicts))


#
# Utilities
#
def _entity(kind: EntityKind, key: str) -> str:
    return f"{KIND_LABELS[kind]} {key}"


def _fields(fields: tuple[str, ...]) -> str:
    return f" (fields: {', '.join(fields)})" if fields else ""
