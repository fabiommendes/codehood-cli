"""
`codehood push`: sync a local course repository to the server. See
`dev/specs/to-do/push.md` and `docs/design/mapping-local-filesystem.md`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Annotated, assert_never

import httpx
import typer
from pydantic import ValidationError

from ..api.base import get_client
from ..models.repo import RepoConfig
from ..push.base import BaseState, load_base, save_base
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
from ..push.ours import ours_warnings, resolve_ours
from ..push.plan import (
    DeleteCalendarEvent,
    DeleteGradeColumn,
    DeleteQuestion,
    DeleteRepository,
    DeleteResource,
    DeleteRollCall,
    DeleteTimeSlot,
    KeptCancelled,
    KeptDraftPublished,
    KeptForRollCall,
    KeptPinnedSlot,
    KeptRepository,
    LocalState,
    Notice,
    Plan,
    Rejected,
    ServerDrifted,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertGradeColumn,
    UpsertQuestion,
    UpsertRepository,
    UpsertResource,
    UpsertTimeSlot,
    Write,
    plan_sync,
)
from ..push.question import scan_questions
from ..push.report import (
    describe_server_drifted,
    sync_exit_code,
    sync_lines,
    sync_summary,
)
from ..push.repository import scan_repositories
from ..push.resource import read_course_readme, scan_resources
from ..push.run import (
    HttpRepositoryApi,
    OpResult,
    apply,
    fetch_server_state,
    run_plan,
)
from ..push.unconsumed import (
    consumed_paths,
    excluded_paths,
    find_unconsumed,
    list_files,
)
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
    ours: Annotated[
        list[str] | None,
        typer.Option(
            "--ours",
            help=(
                "Settle the conflicts matching this glob, written <kind>/<key> "
                "(e.g. resource/intro), by sending the local version. "
                "Repeatable."
            ),
        ),
    ] = None,
) -> None:
    """
    Sync the repository's course row, repositories, calendar, resources,
    questions and grade columns.
    """
    try:
        config = RepoConfig.open(path)
        local = read_local_state(path, config)
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

    for warning in local.warnings:
        typer.echo(f"warning  {warning}", err=True)

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
            ours=ours or [],
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
    ours: Sequence[str] = (),
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

    base = load_base(path)
    for warning in base.warnings:
        typer.echo(f"warning  {warning}", err=True)

    plan = plan_sync(
        local,
        base,
        server,
        drop_roll_calls=drop_roll_calls,
        drop_repositories=drop_repositories,
        message=message,
    )
    for warning in ours_warnings(plan, ours):
        typer.echo(f"warning  {warning}", err=True)
    plan = resolve_ours(plan, ours)

    for file in local.excluded:
        typer.echo(f"excluded  {file.path}")
    excluded_note = f", {len(local.excluded)} excluded" if local.excluded else ""
    for unconsumed in local.unconsumed:
        typer.echo(f"not pushed (no handler): {unconsumed}")
    # `sync_lines` renders the drift notices along with the pulls and conflicts.
    for notice in plan.notices:
        if not isinstance(notice, ServerDrifted):
            typer.echo(notice_line(notice))
    for line in sync_lines(plan):
        typer.echo(line)

    if dry_run:
        for op in plan.writes:
            typer.echo(f"planned  {describe(op)}")
        typer.echo(dry_run_summary(plan) + excluded_note)
        _echo_sync_summary(plan)
        if exit_code(plan, (), grades_failed=grades_failed):
            raise typer.Exit(code=1)
        return

    to_run: list[Write] = []
    skipped: list[Write] = []
    for op in plan.writes:
        (skipped if isinstance(op, PRUNE_OPS) and not prune else to_run).append(op)

    for op in skipped:
        typer.echo(f"skipped  {describe(op)} (--no-prune)")

    results: list[OpResult] = []
    try:
        for result in run_plan(
            to_run,
            discipline=local.discipline,
            course=local.course,
            client=client,
            repositories=repositories,
        ):
            results.append(result)
            if result.skipped:
                typer.echo(f"skipped  {describe(result.op)} ({result.message})")
                continue
            status = "ok" if result.ok else "failed"
            typer.echo(f"{status:>6}  {describe(result.op)}: {result.message}")
    finally:
        record_base(path, base, plan, results)

    failures = [result for result in results if not result.ok and not result.skipped]
    typer.echo(run_summary(plan, results, skipped=len(skipped)) + excluded_note)
    _echo_sync_summary(plan)
    if failures:
        typer.echo("failures:")
        for result in failures:
            typer.echo(f"  {describe(result.op)}: {result.message}")
    if grades_failed:
        typer.echo("grade columns were not pushed, see the errors above")
    if exit_code(plan, results, grades_failed=grades_failed):
        raise typer.Exit(code=1)


def record_base(
    path: Path, base: BaseState, plan: Plan, results: list[OpResult]
) -> None:
    """
    Write the base the push leaves behind, and say so when it cannot.

    Runs even when the push stops halfway, so what already went through is
    not forgotten. A base that cannot be written costs the next push its
    memory, not this one its result.
    """
    state = apply(base, plan, results)
    if state == base and not base.warnings:
        return
    try:
        save_base(path, state)
    except OSError as exc:
        typer.echo(f"warning  could not record the base: {exc}", err=True)


def exit_code(
    plan: Plan, results: Sequence[OpResult], *, grades_failed: bool = False
) -> int:
    """
    The exit code of a push: failed when a question was rejected, a conflict
    remains, a write failed or the grade columns could not be computed.
    """
    failed = bool(plan.rejected) or grades_failed or bool(sync_exit_code(plan))
    return int(failed or any(not result.ok for result in results))


def _echo_sync_summary(plan: Plan) -> None:
    if summary := sync_summary(plan):
        typer.echo(summary)


def dry_run_summary(plan: Plan) -> str:
    """
    The summary line of a `--dry-run`: planned writes, apart from the
    rejected questions.
    """
    return (
        f"summary: {len(plan.writes)} operation(s) planned, 0 executed (--dry-run)"
        f"{_invalid_note(plan)}"
    )


def run_summary(plan: Plan, results: Sequence[OpResult], *, skipped: int) -> str:
    """
    The summary line of a push that ran: counts only writes, never notices.

    `skipped` is the number of writes `--no-prune` held back; `results` that
    were never attempted are counted apart.
    """
    attempted = [result for result in results if not result.skipped]
    failed = sum(1 for result in attempted if not result.ok)
    not_attempted = len(results) - len(attempted)
    return (
        f"summary: {len(attempted)} operation(s) executed, {failed} failed, "
        f"{skipped} skipped"
        f"{f', {not_attempted} not attempted' if not_attempted else ''}"
        f"{_invalid_note(plan)}"
    )


def _invalid_note(plan: Plan) -> str:
    return f", {len(plan.rejected)} invalid" if plan.rejected else ""


def read_local_state(path: Path, config: RepoConfig) -> LocalState:
    """
    Read a course repository into the value `plan_sync` diffs.

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
    readme_path = path / "README.md"
    if not readme_path.exists():
        raise FileNotFoundError(
            f"no README.md at {path} -- it is the course description"
        )
    description, readme = read_course_readme(
        readme_path.read_text(encoding="utf-8"), config.course.description, readme_path
    )

    calendar_path = path / "calendar.md"
    if not calendar_path.exists():
        raise FileNotFoundError(
            f"no calendar.md at {path} -- it sets the course's start and end"
        )
    calendar = parse_calendar(calendar_path.read_text(encoding="utf-8"))
    allocation = allocate(calendar)

    key = config.key
    exclude = config.push.exclude
    tracked = tuple(scan_files(path, exclude))
    files, gitignore = list_files(path)
    trees = tuple(scan_repositories(path, exclude))
    linked = attach_repositories(allocation.events, trees)
    extras = (readme,) if readme is not None else ()
    scanned = tuple(scan_resources(path, exclude, extras))
    resources = rewrite_body_links(attach_resources(linked, scanned, path), path, key)

    return LocalState(
        key=key,
        description=description,
        start=calendar.start,
        end=calendar.end,
        slots=calendar.slots,
        events=rewrite_repository_links(
            rewrite_event_links(linked, resources, path, key), key
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
        warnings=allocation.warnings,
    )


def describe(op: Write) -> str:
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
        case UpsertGradeColumn():
            return f"grade column {op.column.slug} ({len(op.column.values)} values)"
        case DeleteGradeColumn():
            return f"delete grade column {op.slug}"
        case DeleteRollCall():
            return f"delete roll call {op.week}/{op.time_slot}"
        case UpsertRepository() | DeleteRepository():
            return describe_repository(op)


def describe_repository(op: UpsertRepository | DeleteRepository) -> str:
    """
    Render one repository operation as the line `push` prints for it.

    `UpsertRepository` reads `repository lab1: 3 files (1.2 MB), commit
    4f2a9c1`, with the first 7 hex digits of the local `tree_sha`.
    """
    match op:
        case UpsertRepository():
            count = len(op.tree.entries)
            noun = "file" if count == 1 else "files"
            return (
                f"repository {op.tree.slug}: {count} {noun} "
                f"({format_size(op.tree.size)}), commit {op.tree.tree_sha[:7]}"
            )
        case DeleteRepository():
            return f"delete repository {op.slug}"


def describe_notice(notice: Notice) -> str:
    """
    Render one notice as the text `push` prints after its `invalid` or
    `warning` prefix.
    """
    match notice:
        case Rejected():
            return f"question {notice.slug} ({notice.path.name}): {notice.reason}"
        case KeptDraftPublished():
            return (
                f"question {notice.slug} (its file marks a draft): kept "
                f"{notice.status}; hide it on the web or drop the `_`"
            )
        case KeptPinnedSlot():
            events = ", ".join(f"{week}/{notice.slug}" for week in notice.weeks)
            plural = len(notice.weeks) > 1
            return (
                f"time slot {notice.slug} kept (event{'s' if plural else ''} "
                f"{events} {'are' if plural else 'is'} CANCELLED)"
            )
        case KeptForRollCall():
            return (
                f"event {notice.week}/{notice.time_slot} kept: it has a roll call "
                f"with {notice.attendances} attendance(s); use --drop-roll-calls "
                "to delete it"
            )
        case KeptRepository():
            return (
                f"repository {notice.slug} kept: its folder is gone; "
                "use --drop-repositories to delete it"
            )
        case KeptCancelled():
            return f"event {notice.week}/{notice.time_slot} kept: it is CANCELLED"
        case ServerDrifted():
            return describe_server_drifted(notice).removeprefix("warning  ")
        case _:
            assert_never(notice)


def notice_line(notice: Notice) -> str:
    """
    The line `push` prints for a notice: `invalid` when it fails the push,
    `warning` otherwise.
    """
    prefix = "invalid" if isinstance(notice, Rejected) else "warning"
    return f"{prefix}  {describe_notice(notice)}"


def format_size(size: int) -> str:
    """
    A byte count in decimal units, e.g. `1.2 MB`.
    """
    if size < 1000:
        return f"{size} B"
    if size < 1_000_000:
        return f"{size / 1000:.1f} kB"
    return f"{size / 1_000_000:.1f} MB"
