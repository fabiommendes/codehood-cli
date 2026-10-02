"""
`codehood grades`: print the grade columns `codehood push` would send.

Also home to `read_grade_sheet`, the one place that gathers what the columns
are computed from: `codehood.toml`, `grades.csv`, `grades.py` and the
server's exam results. See `dev/specs/to-review/push-grades.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import httpx
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from ..api.base import get_client
from ..models.repo import RepoConfig
from ..push.grades import (
    ColumnSpec,
    GradeColumn,
    GradesError,
    Roster,
    build_roster,
    compute_columns,
    parse_grades_csv,
)
from ..push.hook import load_grade_function
from ..push.run import fetch_students
from .base import app

__all__ = ["GradeSheet", "grades", "read_grade_sheet", "unmatched_warnings"]

CSV_FILE = "grades.csv"
SCRIPT_FILE = "grades.py"


@dataclass(frozen=True)
class GradeSheet:
    """
    The computed grade columns, with the students they were computed for.
    """

    columns: tuple[GradeColumn, ...] = ()
    roster: Roster = Roster()


@app.command()
def grades(
    path: Annotated[
        Path,
        typer.Argument(help="Course repository. Defaults to the current directory."),
    ] = Path("."),
) -> None:
    """
    Print the grade columns a push would send. Writes nothing.
    """
    try:
        config = RepoConfig.open(path)
    except (FileNotFoundError, ValidationError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    client = get_client(config.server.url)
    try:
        sheet = read_grade_sheet(path, config, client=client)
    except GradesError as exc:
        for problem in exc.problems:
            typer.echo(f"error: {problem}", err=True)
        raise typer.Exit(code=1) from exc
    except httpx.HTTPStatusError as exc:
        typer.echo(f"error: could not read the course's grades: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for warning in unmatched_warnings(sheet.roster):
        typer.echo(f"warning  {warning}", err=True)

    if not sheet.columns:
        typer.echo("codehood.toml declares no grade column")
        return
    Console().print(render_table(sheet))


def read_grade_sheet(
    path: Path, config: RepoConfig, *, client: httpx.Client
) -> GradeSheet:
    """
    Compute the grade columns of the repository at `path`.

    Everything local is read and checked before the one network call, so a
    broken `grades.csv` or `grades.py` costs no request.

    Raises:
        GradesError: The columns cannot be computed. See `compute_columns`,
            `parse_grades_csv` and `load_grade_function`.
        httpx.HTTPStatusError: The server refused to list the students.
    """
    specs = tuple(
        ColumnSpec(slug=column.slug, title=column.title, kind=column.kind)
        for column in config.grades.column
    )
    if not specs:
        return GradeSheet()

    csv_path = path / CSV_FILE
    script_path = path / SCRIPT_FILE
    sheet = (
        parse_grades_csv(csv_path.read_text(encoding="utf-8"))
        if csv_path.exists()
        else None
    )
    grade = load_grade_function(script_path) if script_path.exists() else None
    if sheet is None and grade is None:
        raise GradesError(
            [
                "codehood.toml declares grade columns, but the repository has "
                f"neither {SCRIPT_FILE} nor {CSV_FILE}"
            ]
        )

    students = fetch_students(
        config.course.discipline,
        f"{config.course.instructor}_{config.course.edition}",
        client,
    )
    roster = build_roster(students, sheet)
    return GradeSheet(columns=compute_columns(specs, roster, grade), roster=roster)


def unmatched_warnings(roster: Roster) -> list[str]:
    """
    One line per `grades.csv` row that belongs to no enrolled student.
    """
    return [
        f"{CSV_FILE}: no enrolled student with {roster.id_field} {student_id}, "
        "row skipped"
        for student_id in roster.unmatched
    ]


#
# Utilities
#
def render_table(sheet: GradeSheet) -> Table:
    """
    The computed columns as a table: one row per student, one column per
    grade column, an empty cell where a student has no value.
    """
    table = Table()
    table.add_column("Student")
    for column in sheet.columns:
        table.add_column(
            column.title, justify="right" if column.kind == "number" else "left"
        )

    values = [dict(column.values) for column in sheet.columns]
    for student in sheet.roster.students:
        label = student.username
        if student.status == "dropped":
            label += " (dropped)"
        table.add_row(
            label,
            *(
                format_value(by_username.get(student.username))
                for by_username in values
            ),
        )
    return table


def format_value(value: float | str | None) -> str:
    """
    One cell of the table: a number without a trailing `.0`, a label as it
    is, nothing for no value.
    """
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return value
