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
    RepositoryError,
    ResourceFileError,
    ResourceLinkError,
    SlugCollisionError,
)
from ..push.exclude import scan_excluded
from ..push.grades import GradesError
from ..push.links import (
    attach_repositories,
    attach_resources,
    rewrite_body_links,
    rewrite_event_links,
    rewrite_repository_links,
)
from ..push.plan import (
    DeleteCalendarEvent,
    DeleteGradeColumn,
    DeleteQuestion,
    DeleteRepository,
    DeleteResource,
    DeleteRollCall,
    DeleteTimeSlot,
    LocalState,
    PushOp,
    RejectQuestion,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertGradeColumn,
    UpsertQuestion,
    UpsertRepository,
    UpsertResource,
    UpsertTimeSlot,
    WarnEventHasRollCall,
    WarnQuestionPublished,
    WarnRepositoryKept,
    WarnTimeSlotPinned,
    plan_push,
)
from ..push.question import scan_questions
from ..push.repository import scan_repositories
from ..push.resource import README_SLUG, read_readme, scan_resources
from ..push.run import HttpRepositoryApi, OpResult, fetch_server_state, run_plan
from ..push.unconsumed import (
    consumed_paths,
    excluded_paths,
    find_unconsumed,
    list_files,
)
from ..repo import read_course_name
from ..repo.file_tracker import scan_files
from .base import app
from .grades import read_grade_sheet, unmatched_warnings

__all__ = ["push"]

#: Ops a `--no-prune` run reports instead of running.
PRUNE_OPS = (
    DeleteResource,
    DeleteQuestion,
    DeleteTimeSlot,
    DeleteCalendarEvent,
    DeleteRollCall,
    DeleteGradeColumn,
    DeleteRepository,
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
    drop_roll_calls: Annotated[
        bool,
        typer.Option(
            "--drop-roll-calls",
            help="Also delete the roll call of an event removed from the calendar.",
        ),
    ] = False,
    drop_repositories: Annotated[
        bool,
        typer.Option(
            "--drop-repositories",
            help="Delete server repositories whose folder is gone from repositories/.",
        ),
    ] = False,
    message: Annotated[
        str | None,
        typer.Option(
            "-m",
            "--message",
            help="Commit message for every repository this push changes.",
        ),
    ] = None,
) -> None:
    """
    Sync the repository's course row, repositories, calendar, resources,
    questions and grade columns.
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
        ResourceFileError,
        RepositoryError,
    ) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        sync(
            path,
            config,
            local,
            dry_run=dry_run,
            prune=prune,
            drop_roll_calls=drop_roll_calls,
            drop_repositories=drop_repositories,
            message=message,
        )
    except httpx.TransportError as exc:
        typer.echo(f"error: could not reach {config.server.url}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def sync(
    path: Path,
    config: RepoConfig,
    local: LocalState,
    *,
    dry_run: bool,
    prune: bool,
    drop_roll_calls: bool,
    drop_repositories: bool = False,
    message: str | None = None,
) -> None:
    """
    Read the server's state, plan the push, and run it or print it.

    Raises:
        typer.Exit: With code 1 when an operation or the grade columns failed.
        httpx.TransportError: When the server cannot be reached.
    """
    client = get_client(config.server.url)
    repositories = HttpRepositoryApi(client, local.discipline, local.course)
    try:
        server = fetch_server_state(
            local.discipline, local.course, client, repositories
        )
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

    ops = list(
        plan_push(
            local,
            server,
            drop_roll_calls=drop_roll_calls,
            drop_repositories=drop_repositories,
            message=message,
        )
    )

    for file in local.excluded:
        typer.echo(f"excluded  {file.path}")
    excluded_note = f", {len(local.excluded)} excluded" if local.excluded else ""
    for unconsumed in local.unconsumed:
        typer.echo(f"not pushed (no handler): {unconsumed}")

    if dry_run:
        rejected = [op for op in ops if isinstance(op, RejectQuestion)]
        for op in ops:
            if isinstance(op, RejectQuestion):
                typer.echo(f"invalid  {describe(op)}: {op.reason}")
            else:
                typer.echo(f"planned  {describe(op)}")
        typer.echo(
            f"summary: {len(ops) - len(rejected)} operation(s) planned, "
            f"0 executed (--dry-run){f', {len(rejected)} invalid' if rejected else ''}"
            f"{excluded_note}"
        )
        if grades_failed or rejected:
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
    not_attempted = 0
    for result in run_plan(
        to_run,
        discipline=local.discipline,
        course=local.course,
        client=client,
        repositories=repositories,
    ):
        if result.skipped:
            not_attempted += 1
            typer.echo(f"skipped  {describe(result.op)} ({result.message})")
            continue
        executed += 1
        status = "ok" if result.ok else "failed"
        typer.echo(f"{status:>6}  {describe(result.op)}: {result.message}")
        if not result.ok:
            failures.append(result)

    typer.echo(
        f"summary: {executed} operation(s) executed, {len(failures)} failed, "
        f"{len(skipped)} skipped"
        f"{f', {not_attempted} not attempted' if not_attempted else ''}"
        f"{excluded_note}"
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
        RepositoryError: A folder under `repositories/` cannot be pushed.
        ResourceLinkError: A lesson links a missing resource or repository.
        ResourceFileError: An `info.yaml` or a `.url` file is malformed.
    """
    config = RepoConfig.open(path)

    readme_path = path / "README.md"
    if not readme_path.exists():
        raise FileNotFoundError(
            f"no README.md at {path} -- it is the course description"
        )
    parsed = read_course_name(readme_path.read_text(encoding="utf-8"))
    description = config.course.description or (parsed[1] if parsed else "")

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
    exclude = config.push.exclude
    tracked = tuple(scan_files(path, exclude))
    files, gitignore = list_files(path)
    trees = tuple(scan_repositories(path, exclude))
    linked = attach_repositories(allocation.events, trees)
    scanned = tuple(scan_resources(path, exclude))
    readme = read_readme(readme_path, describes_course=not config.course.description)
    if readme is not None:
        clash = [file.path for file in scanned if file.slug == README_SLUG]
        if clash:
            raise SlugCollisionError({README_SLUG: [readme_path, *clash]})
        scanned = (readme, *scanned)
    resources = rewrite_body_links(
        attach_resources(linked, scanned, path),
        path,
        discipline,
        course,
    )

    return LocalState(
        discipline=discipline,
        course=course,
        description=description,
        start=calendar.start,
        end=calendar.end,
        slots=calendar.slots,
        events=rewrite_repository_links(
            rewrite_event_links(linked, resources, path, discipline, course),
            discipline,
            course,
        ),
        resources=resources,
        repositories=trees,
        questions=tuple(scan_questions(path, exclude)),
        excluded=tuple(scan_excluded(path, exclude)),
        unconsumed=find_unconsumed(
            files,
            consumed=consumed_paths(tracked),
            excluded=excluded_paths(tracked),
            gitignore=gitignore,
        ),
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
        case RejectQuestion():
            return f"question {op.slug} ({op.path.name})"
        case WarnQuestionPublished():
            return f"question {op.slug} (its file marks a draft)"
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
        case WarnEventHasRollCall():
            return (
                f"event {op.week}/{op.time_slot} kept: it has a roll call with "
                f"{op.attendances} attendance(s); use --drop-roll-calls to delete it"
            )
        case DeleteRollCall():
            return f"delete roll call {op.week}/{op.time_slot}"
        case UpsertRepository() | WarnRepositoryKept() | DeleteRepository():
            return describe_repository(op)


def describe_repository(
    op: UpsertRepository | WarnRepositoryKept | DeleteRepository,
) -> str:
    """
    Render one repository operation as the line `push` prints for it.

    `UpsertRepository` reads `repository lab1: 3 files (1.2 MB), commit
    4f2a9c1`, with the first 7 hex digits of the local `tree_sha`.
    `WarnRepositoryKept` names `--drop-repositories`.
    """
    match op:
        case UpsertRepository():
            count = len(op.tree.entries)
            noun = "file" if count == 1 else "files"
            return (
                f"repository {op.tree.slug}: {count} {noun} "
                f"({format_size(op.tree.size)}), commit {op.tree.tree_sha[:7]}"
            )
        case WarnRepositoryKept():
            return (
                f"repository {op.slug} kept: its folder is gone; "
                "use --drop-repositories to delete it"
            )
        case DeleteRepository():
            return f"delete repository {op.slug}"


def format_size(size: int) -> str:
    """
    A byte count in decimal units, e.g. `1.2 MB`.
    """
    if size < 1000:
        return f"{size} B"
    if size < 1_000_000:
        return f"{size / 1000:.1f} kB"
    return f"{size / 1_000_000:.1f} MB"
