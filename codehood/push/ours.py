"""
`--ours`: settle `Conflict`s of a plan in favour of the repository.

Pure functions on a `Plan` and the globs the user passed. A glob is matched
against `"<kind>/<key>"`, for example `resource/intro` or
`calendar_event/1/mon`.
"""

from __future__ import annotations

from collections.abc import Sequence
from fnmatch import fnmatchcase

from .plan import Conflict, Plan

__all__ = ["conflict_name", "ours_warnings", "resolve_ours"]


def conflict_name(conflict: Conflict) -> str:
    """
    The string `--ours` globs are matched against: `<kind>/<key>`.
    """
    return f"{conflict.kind}/{conflict.key}"


def resolve_ours(plan: Plan, globs: Sequence[str]) -> Plan:
    """
    Replace every conflict a glob matches by the operations that keep the
    repository's version.

    The operations join the end of the writes, with their base confirmations.
    A matching conflict that has no operations stays a conflict.
    """
    resolved = [
        c for c in plan.conflicts if c.ours and _matches(conflict_name(c), globs)
    ]
    if not resolved:
        return plan
    kept = tuple(c for c in plan.conflicts if c not in resolved)
    ours = Plan.of(op for c in resolved for op in c.ours)
    return (
        Plan(
            plan.writes,
            plan.notices,
            plan.pulls,
            kept,
            plan.other_cli,
            plan.base_updates,
            plan.confirmations,
        )
        + ours
    )


def ours_warnings(plan: Plan, globs: Sequence[str]) -> tuple[str, ...]:
    """
    The warnings `--ours` earns on `plan`: a glob that matches no conflict,
    and a matched conflict that has no automatic resolution.
    """
    names = [conflict_name(c) for c in plan.conflicts]
    warnings = [
        f"--ours {glob} matches no conflict"
        for glob in globs
        if not any(fnmatchcase(name, glob) for name in names)
    ]
    warnings.extend(
        f"conflict {conflict_name(c)} has no automatic resolution; reconcile it by hand"
        for c in plan.conflicts
        if not c.ours and _matches(conflict_name(c), globs)
    )
    return tuple(warnings)


#
# Utilities
#
def _matches(name: str, globs: Sequence[str]) -> bool:
    return any(fnmatchcase(name, glob) for glob in globs)
