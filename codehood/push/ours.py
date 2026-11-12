"""
`--ours`: settle `Conflict`s of a plan in favour of the repository.

Pure functions on a `Plan` and the globs the user passed. A glob is matched
against `"<kind>/<key>"`, for example `resource/intro` or
`calendar_event/1/mon`.
"""

from __future__ import annotations

from collections.abc import Sequence
from fnmatch import fnmatchcase

from .plan import Conflict, OtherCli, Plan, order_writes

__all__ = ["conflict_name", "ours_warnings", "resolve_ours"]


def conflict_name(conflict: Conflict | OtherCli) -> str:
    """
    The string `--ours` globs are matched against: `<kind>/<key>`.
    """
    return f"{conflict.kind}/{conflict.key}"


def resolve_ours(plan: Plan, globs: Sequence[str]) -> Plan:
    """
    Replace every conflict and other-CLI entry a glob matches by the
    operations that keep the repository's version.

    The operations join the writes in the order a plan runs them, with their
    base confirmations. A match that has no operations stays where it is.
    """
    conflicts = [
        c for c in plan.conflicts if c.ours and _matches(conflict_name(c), globs)
    ]
    others = [o for o in plan.other_cli if o.ours and _matches(conflict_name(o), globs)]
    if not conflicts and not others:
        return plan
    matched: list[Conflict | OtherCli] = [*conflicts, *others]
    ours = Plan.of(op for c in matched for op in c.ours)
    merged = Plan(
        order_writes((*plan.writes, *ours.writes)),
        plan.notices + ours.notices,
        plan.pulls,
        tuple(c for c in plan.conflicts if c not in conflicts),
        tuple(o for o in plan.other_cli if o not in others),
        plan.base_updates,
        plan.confirmations + ours.confirmations,
    )
    return merged


def ours_warnings(plan: Plan, globs: Sequence[str]) -> tuple[str, ...]:
    """
    The warnings `--ours` earns on `plan`: a glob that matches no conflict,
    and a matched conflict that has no automatic resolution.
    """
    entries: tuple[Conflict | OtherCli, ...] = (*plan.conflicts, *plan.other_cli)
    names = [conflict_name(c) for c in entries]
    warnings = [
        f"--ours {glob} matches no conflict"
        for glob in globs
        if not any(fnmatchcase(name, glob) for name in names)
    ]
    warnings.extend(
        f"conflict {conflict_name(c)} has no automatic resolution; reconcile it by hand"
        for c in entries
        if not c.ours and _matches(conflict_name(c), globs)
    )
    return tuple(warnings)


#
# Utilities
#
def _matches(name: str, globs: Sequence[str]) -> bool:
    return any(fnmatchcase(name, glob) for glob in globs)
