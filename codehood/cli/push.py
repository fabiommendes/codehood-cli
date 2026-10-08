"""
`codehood push`: sync a local course repository to the server. See
`dev/specs/to-do/push.md` and `docs/design/mapping-local-filesystem.md`.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Annotated

import httpx
import typer
from pydantic import ValidationError

from ..api.base import get_client
from ..models.repo import RepoConfig
from ..push.calendar import allocate, parse_calendar
from ..push.errors import (
    CalendarError,
    QuestionParseError,
    ResourceLinkError,
    SlugCollisionError,
)
from ..push.grades import GradesError
from ..push.links import attach_resources, rewrite_event_links
from ..push.plan import (
    DeleteCalendarEvent,
    DeleteGradeColumn,
    DeleteQuestion,
    DeleteResource,
    DeleteTimeSlot,
    LocalState,
    PushOp,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertGradeColumn,
    UpsertQuestion,
    UpsertResource,
    UpsertTimeSlot,
    WarnTimeSlotPinned,
    plan_push,
)
from ..push.question import scan_questions
from ..push.resource import scan_resources
from ..push.run import OpResult, fetch_server_state, run_plan
from ..repo import read_course_name
from .base import app
from .grades import read_grade_sheet, unmatched_warnings

__all__ = ["push"]

#: Ops a `--no-prune` run reports instead of running.
PRUNE_OPS = (
    DeleteResource,
    DeleteQuestion,
    DeleteTimeSlot,
    DeleteCalendarEvent,
    DeleteGradeColumn,
)


@app.command()
def push(
    path: Annotated[
        Path,
        typer.Argument(
            help="Course repository to push. Defaults to the current directory."
        ),
    ] = Path("."),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the plan; write nothing."),
    ] = False,
    prune: Annotated[
        bool,
        typer.Option(
            "--prune/--no-prune",
            help="Delete server entities whose local source is gone (default: on).",
        ),
    ] = True,
) -> None:
    """
    Sync the repository's course row, calendar, resources, questions and
    grade columns.
    """
    try:
        config = RepoConfig.open(path)
        local = read_local_state(path)
    except (
        FileNotFoundError,
        ValidationError,
        CalendarError,
        SlugCollisionError,
        ResourceLinkError,
        QuestionParseError,
    ) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    client = get_client(config.server.url)
    try:
        server = fetch_server_state(local.discipline, local.course, client)
    except httpx.HTTPStatusError as exc:
        typer.echo(f"error: could not read the server's current state: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    grades_failed = False
    try:
        sheet = read_grade_sheet(path, config, client=client)
    except GradesError as exc:
        for problem in exc.problems:
            typer.echo(f"error: grades: {problem}", err=True)
        grades_failed = True
        local = replace(local, grade_columns=None)
    except httpx.HTTPStatusError as exc:
        typer.echo(
            f"error: grades: could not read the course's grades: {exc}", err=True
        )
        grades_failed = True
        local = replace(local, grade_columns=None)
    else:
        for warning in unmatched_warnings(sheet.roster):
            typer.echo(f"warning  {warning}", err=True)
        local = replace(local, grade_columns=sheet.columns)

    ops = list(plan_push(local, server))

    if dry_run:
        for op in ops:
            typer.echo(f"planned  {describe(op)}")
        typer.echo(f"summary: {len(ops)} operation(s) planned, 0 executed (--dry-run)")
        if grades_failed:
            raise typer.Exit(code=1)
        return

    to_run: list[PushOp] = []
    skipped: list[PushOp] = []
    for op in ops:
        (skipped if isinstance(op, PRUNE_OPS) and not prune else to_run).append(op)

    for op in skipped:
        typer.echo(f"skipped  {describe(op)} (--no-prune)")

    failures: list[OpResult] = []
    executed = 0
    for result in run_plan(
        to_run, discipline=local.discipline, course=local.course, client=client
    ):
        executed += 1
        status = "ok" if result.ok else "failed"
        typer.echo(f"{status:>6}  {describe(result.op)}: {result.message}")
        if not result.ok:
            failures.append(result)

    typer.echo(
        f"summary: {executed} operation(s) executed, {len(failures)} failed, "
        f"{len(skipped)} skipped"
    )
    if failures:
        typer.echo("failures:")
        for result in failures:
            typer.echo(f"  {describe(result.op)}: {result.message}")
    if grades_failed:
        typer.echo("grade columns were not pushed, see the errors above")
    if failures or grades_failed:
        raise typer.Exit(code=1)


def read_local_state(path: Path) -> LocalState:
    """
    Read a course repository into the value `plan_push` diffs.

    Every read and every parse happens here, before the first network
    call, so a malformed repository costs nothing and writes nothing.

    Raises:
        FileNotFoundError: `codehood.toml`, `README.md` or `calendar.md` is
            missing. The mapping makes all three mandatory: the last two
            are the only source of the course's description and dates.
        CalendarError: `calendar.md` does not parse.
        SlugCollisionError: Two resources or two questions want one slug.
        QuestionParseError: `mdq` refused a file under `questions/`.
    """
    config = RepoConfig.open(path)

    readme_path = path / "README.md"
    if not readme_path.exists():
        raise FileNotFoundError(
            f"no README.md at {path} -- it is the course description"
        )
    parsed = read_course_name(readme_path.read_text(encoding="utf-8"))
    description = parsed[1] if parsed is not None else ""

    calendar_path = path / "calendar.md"
    if not calendar_path.exists():
        raise FileNotFoundError(
            f"no calendar.md at {path} -- it sets the course's start and end"
        )
    calendar = parse_calendar(calendar_path.read_text(encoding="utf-8"))
    allocation = allocate(calendar)
    for warning in allocation.warnings:
        typer.echo(f"warning  {warning}", err=True)

    discipline = config.course.discipline
    course = f"{config.course.instructor}_{config.course.edition}"
    resources = attach_resources(allocation.events, tuple(scan_resources(path)), path)

    return LocalState(
        discipline=discipline,
        course=course,
        description=description,
        start=calendar.start,
        end=calendar.end,
        slots=calendar.slots,
        events=rewrite_event_links(
            allocation.events, resources, path, discipline, course
        ),
        resources=resources,
        questions=tuple(scan_questions(path)),
    )


def describe(op: PushOp) -> str:
    """
    Render one operation as the line `push` prints for it.
    """
    match op:
        case UpsertCourse():
            return f"course {op.discipline}/{op.course}"
        case UpsertResource():
            return f"resource {op.slug} ({op.data.type})"
        case DeleteResource():
            return f"delete resource {op.slug}"
        case UpsertQuestion():
            return f"question {op.slug}"
        case DeleteQuestion():
            return f"delete question {op.slug}"
        case UpsertTimeSlot():
            return f"time slot {op.slot.slug}"
        case DeleteTimeSlot():
            return f"delete time slot {op.slug}"
        case UpsertCalendarEvent():
            return f"event {op.event.week}/{op.event.time_slot} ({op.event.kind})"
        case DeleteCalendarEvent():
            return f"delete event {op.week}/{op.time_slot}"
        case WarnTimeSlotPinned():
            return f"time slot {op.slug} kept (event {op.week}/{op.slug} is CANCELLED)"
        case UpsertGradeColumn():
            return f"grade column {op.column.slug} ({len(op.column.values)} values)"
        case DeleteGradeColumn():
            return f"delete grade column {op.slug}"
