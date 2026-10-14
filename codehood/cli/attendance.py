"""
`codehood attendance`: show a course's attendance report, or write it as CSV.

The CSV mirrors the server's download (`attendanceCsvRows` in
`src/services/attendance-table.ts`), so both produce the same bytes.
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Annotated

import httpx
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from ..api import generated
from ..api.base import get_client
from ..models.repo import RepoConfig
from .base import app

__all__ = ["attendance", "csv_text", "render_table"]

#: How a cell shows in the CSV: present, absent and anything else.
_CSV_CELLS = {"present": "1", "absent": "0"}


@app.command()
def attendance(
    path: Annotated[
        Path,
        typer.Argument(help="Course repository. Defaults to the current directory."),
    ] = Path("."),
    csv_path: Annotated[
        Path | None,
        typer.Option("--csv", help="Write the report to this CSV file."),
    ] = None,
) -> None:
    """
    Print the course's attendance table, or write it to a CSV file.
    """
    try:
        config = RepoConfig.open(path)
    except (FileNotFoundError, ValidationError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    client = get_client(config.server.url)
    try:
        report = generated.course_attendance(
            discipline=config.course.discipline,
            course=f"{config.course.instructor}_{config.course.edition}",
            client=client,
        )
    except httpx.HTTPStatusError as exc:
        typer.echo(f"error: could not read the course's attendance: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if csv_path is not None:
        with csv_path.open("w", encoding="utf-8", newline="") as file:
            file.write(csv_text(report))
        typer.echo(f"wrote {csv_path}")
        return

    if not report.events:
        typer.echo("The course has no roll call yet")
        return
    Console().print(render_table(report))


def csv_text(report: generated.CourseAttendanceResponse) -> str:
    """
    The report as CSV: `\\r\\n` between lines, quoting only where needed, and
    no trailing newline.
    """
    keys = [f"{event.week}/{event.time_slot}" for event in report.events]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(
        ["username", "name", "schoolId", "status", *keys, "present", "total", "%"]
    )
    for student in report.students:
        writer.writerow(
            [
                student.username,
                student.name,
                student.school_id or "",
                student.status.lower(),
                *(_CSV_CELLS.get(student.cells.get(key, ""), "-") for key in keys),
                student.present,
                student.total,
                _percent(student.present, student.total),
            ]
        )
    return buffer.getvalue().removesuffix("\r\n")


def render_table(report: generated.CourseAttendanceResponse) -> Table:
    """
    The report as a table: one row per student, one column per roll call.
    """
    keys = [f"{event.week}/{event.time_slot}" for event in report.events]
    table = Table()
    table.add_column("Student")
    table.add_column("Status")
    for key in keys:
        table.add_column(key, justify="center")
    table.add_column("Present", justify="right")
    table.add_column("%", justify="right")

    for student in report.students:
        table.add_row(
            student.username,
            student.status,
            *(_CSV_CELLS.get(student.cells.get(key, ""), "-") for key in keys),
            f"{student.present}/{student.total}",
            _percent(student.present, student.total),
        )
    return table


def _percent(present: int, total: int) -> str:
    """
    Attendance percentage with two decimals, empty without a roll call.

    Rounds half up, like the server.
    """
    if total == 0:
        return ""
    return f"{math.floor(present / total * 10000 + 0.5) / 100:.2f}"
