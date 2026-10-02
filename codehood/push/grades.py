"""
The pure core of pushing grade columns: `grades.csv`, the students the
function is called with, and the columns that come out.

Nothing here reads a file, imports the instructor's script or touches HTTP.
`cli/grades.py` gathers the inputs and `run.py` sends the result. See
`dev/specs/to-review/push-grades.md`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from ..grades import ExamResult, GradeFunction, GradeValue, Student

__all__ = [
    "GradeColumn",
    "ColumnSpec",
    "GradesCsv",
    "GradesError",
    "Roster",
    "ServerStudent",
    "build_roster",
    "compute_columns",
    "parse_grades_csv",
]

type GradeKind = Literal["number", "label"]
type IdField = Literal["school_id", "username", "github", "email"]

ID_FIELDS: tuple[IdField, ...] = ("school_id", "username", "github", "email")

#: The longest label the server stores.
MAX_LABEL = 32

NUMBER_RE = re.compile(r"^[+-]?\d+([.,]\d+)?$")


class GradesError(Exception):
    """
    The grade columns cannot be computed: `grades.csv`, `grades.py` or the
    declared columns disagree.

    Refuses the grades part of a push and nothing else. `problems` lists
    every cause found, one line each.
    """

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("; ".join(self.problems))


#
# Inputs
#
@dataclass(frozen=True)
class ColumnSpec:
    """
    One grade column as `codehood.toml` declares it.
    """

    slug: str
    title: str
    kind: GradeKind


@dataclass(frozen=True)
class GradesCsv:
    """
    `grades.csv`, parsed but not yet matched to students.

    `rows` maps a student's id, as written in the file, to the raw cell of
    each score column. Cells stay text here: whether `7.5` is a number or a
    label depends on who reads it.
    """

    id_field: IdField
    headers: tuple[str, ...]
    rows: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class ServerStudent:
    """
    One enrolled student as the server reports them, before `grades.csv`
    is matched in.
    """

    username: str
    name: str
    email: str
    school_id: str | None
    github: str | None
    status: Literal["active", "dropped"]
    exams: Mapping[str, ExamResult] = field(default_factory=dict)


@dataclass(frozen=True)
class Roster:
    """
    The students `grade` is called with, and what `grades.csv` held for
    each.

    `cells` maps a username to the raw cells of that student's row.
    `unmatched` lists the ids of the file that belong to no enrolled
    student, which are reported and skipped.
    """

    students: tuple[Student, ...] = ()
    headers: tuple[str, ...] = ()
    cells: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    id_field: IdField = "school_id"
    unmatched: tuple[str, ...] = ()


#
# Output
#
@dataclass(frozen=True)
class GradeColumn:
    """
    One grade column ready to push, whole.

    `values` holds one `(username, value)` pair per student with a value,
    ordered by username.
    """

    slug: str
    title: str
    kind: GradeKind
    position: int
    values: tuple[tuple[str, float | str], ...]

    @property
    def rev(self) -> str:
        """
        The digest the server hands back on the next read, which is what
        makes a second push of an unchanged column a no-op.
        """
        payload = {
            "title": self.title,
            "kind": self.kind.upper(),
            "position": self.position,
            "values": [[username, value] for username, value in self.values],
        }
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


#
# grades.csv
#
def parse_grades_csv(text: str) -> GradesCsv:
    """
    Parse `grades.csv`: one row per student, the first column their id.

    The header of the first column says which id it is. The delimiter is
    `;` when the header line has one, `,` otherwise.

    Raises:
        GradesError: The file is empty, the id header is not one of
            `school_id`, `username`, `github`, `email`, a header repeats, a
            row has no id, or an id appears twice.
    """
    lines = text.removeprefix("﻿").splitlines()
    if not lines or not lines[0].strip():
        raise GradesError(["grades.csv is empty"])

    delimiter = ";" if ";" in lines[0] else ","
    reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    header = [cell.strip() for cell in next(reader)]
    id_header, score_headers = header[0], tuple(header[1:])

    problems: list[str] = []
    if id_header not in ID_FIELDS:
        problems.append(
            f"grades.csv: the first column is {id_header!r}, "
            f"expected one of {', '.join(ID_FIELDS)}"
        )
    repeated = sorted({name for name in score_headers if header.count(name) > 1})
    if repeated:
        problems.append(f"grades.csv: repeated column(s) {', '.join(repeated)}")
    if problems:
        raise GradesError(problems)

    rows: dict[str, dict[str, str]] = {}
    for number, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        student_id = row[0].strip()
        if not student_id:
            problems.append(f"grades.csv: row {number} has no {id_header}")
            continue
        if student_id in rows:
            problems.append(f"grades.csv: {id_header} {student_id} appears twice")
            continue
        cells = [cell.strip() for cell in row[1:]]
        rows[student_id] = dict(zip(score_headers, cells, strict=False))
    if problems:
        raise GradesError(problems)

    # `IdField` narrowed by the membership test above.
    id_field: IdField = next(name for name in ID_FIELDS if name == id_header)
    return GradesCsv(id_field=id_field, headers=score_headers, rows=rows)


def build_roster(students: Sequence[ServerStudent], sheet: GradesCsv | None) -> Roster:
    """
    Match `grades.csv` to the enrolled students and build what `grade`
    receives.

    A student with no row reads `None` for every score. A row whose id
    belongs to no student is listed in `unmatched` rather than refused: a
    class list has students who never joined the course.
    """
    if sheet is None:
        return Roster(students=tuple(to_student(student, {}) for student in students))

    by_id = {
        normalize_id(sheet.id_field, student_id): cells
        for student_id, cells in sheet.rows.items()
    }
    matched: set[str] = set()
    cells_by_username: dict[str, Mapping[str, str]] = {}
    result: list[Student] = []
    for student in students:
        key = student_key(student, sheet.id_field)
        cells = by_id.get(key, {}) if key is not None else {}
        if key is not None and key in by_id:
            matched.add(key)
            cells_by_username[student.username] = cells
        scores = {
            header: guess_score(cells.get(header, "")) for header in sheet.headers
        }
        result.append(to_student(student, scores))

    unmatched = tuple(
        student_id
        for student_id in sheet.rows
        if normalize_id(sheet.id_field, student_id) not in matched
    )
    return Roster(
        students=tuple(result),
        headers=sheet.headers,
        cells=cells_by_username,
        id_field=sheet.id_field,
        unmatched=unmatched,
    )


#
# Columns
#
def compute_columns(
    specs: Sequence[ColumnSpec], roster: Roster, grade: GradeFunction | None
) -> tuple[GradeColumn, ...]:
    """
    Compute every declared column for every student.

    A column takes the value `grade` returned for its slug, and for a
    student where `grade` returned none, the `grades.csv` cell under the
    same header.

    Raises:
        GradesError: `grade` raised, returned something that is not a
            mapping, returned a key that is not a declared column or a
            value that does not fit its column, a `grades.csv` cell does
            not fit its column, or nothing produces a declared column.
    """
    declared = {spec.slug for spec in specs}
    results: dict[str, Mapping[str, GradeValue]] = {}
    problems: list[str] = []
    returned: set[str] = set()

    if grade is not None:
        for student in roster.students:
            try:
                result = grade(student)
            except Exception:
                raise GradesError(
                    [
                        f"grades.py raised for {student.username}:\n"
                        f"{traceback.format_exc().rstrip()}"
                    ]
                ) from None
            if not isinstance(result, Mapping):
                raise GradesError(
                    [
                        f"grades.py returned {type(result).__name__} for "
                        f"{student.username}, expected a dict of column slugs"
                    ]
                )
            results[student.username] = result
            returned.update(str(key) for key in result)

        for key in sorted(returned - declared):
            problems.append(
                f"grades.py returned {key!r}, which is not a column of codehood.toml"
            )

    if roster.students:
        for spec in specs:
            if spec.slug not in returned and spec.slug not in roster.headers:
                problems.append(
                    f"column {spec.slug!r} has no value: grades.py does not "
                    "return it and grades.csv has no such column"
                )

    columns: list[GradeColumn] = []
    for position, spec in enumerate(specs):
        values: list[tuple[str, float | str]] = []
        for student in roster.students:
            result = results.get(student.username, {})
            try:
                if spec.slug in result:
                    value = fit_value(spec, result[spec.slug])
                else:
                    cells = roster.cells.get(student.username, {})
                    value = fit_cell(spec, cells.get(spec.slug, ""))
            except ValueError as exc:
                problems.append(f"{student.username}, column {spec.slug!r}: {exc}")
                continue
            if value is not None:
                values.append((student.username, value))
        columns.append(
            GradeColumn(
                slug=spec.slug,
                title=spec.title,
                kind=spec.kind,
                position=position,
                values=tuple(sorted(values)),
            )
        )

    if problems:
        raise GradesError(problems)
    return tuple(columns)


#
# Utilities
#
def to_student(student: ServerStudent, scores: Mapping[str, GradeValue]) -> Student:
    """
    The `Student` the instructor's function receives for one server
    student.
    """
    return Student(
        username=student.username,
        name=student.name,
        email=student.email,
        school_id=student.school_id,
        github=student.github,
        status=student.status,
        exams=student.exams,
        scores=scores,
    )


def student_key(student: ServerStudent, id_field: IdField) -> str | None:
    """
    The id `grades.csv` would list this student under, normalized, or
    `None` when the student has no such id.
    """
    raw = {
        "school_id": student.school_id,
        "username": student.username,
        "github": student.github,
        "email": student.email,
    }[id_field]
    return normalize_id(id_field, raw) if raw else None


def normalize_id(id_field: IdField, value: str) -> str:
    """
    An id as it is compared: trimmed, and without regard to case for the
    two kinds of id that have none.
    """
    value = value.strip()
    return value.casefold() if id_field in ("email", "github") else value


def guess_score(cell: str) -> GradeValue:
    """
    A `grades.csv` cell as `Student.scores` holds it: `None` when empty, a
    `float` when it reads as a number, the text otherwise.

    `,` is accepted as the decimal separator, which is what a spreadsheet
    in a comma-decimal locale exports.
    """
    if not cell:
        return None
    if NUMBER_RE.fullmatch(cell):
        return float(cell.replace(",", "."))
    return cell


def fit_value(spec: ColumnSpec, value: object) -> float | str | None:
    """
    A value `grade` returned, checked against its column.

    Raises:
        ValueError: The value is not what the column's kind takes.
    """
    if value is None:
        return None
    if spec.kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{value!r} is not a number")
        if not math.isfinite(value):
            raise ValueError(f"{value!r} is not a finite number")
        return float(value)
    if not isinstance(value, str):
        raise ValueError(f"{value!r} is not a label")
    return fit_label(value)


def fit_cell(spec: ColumnSpec, cell: str) -> float | str | None:
    """
    A `grades.csv` cell, read as its column's kind.

    Raises:
        ValueError: The cell is not what the column's kind takes.
    """
    if not cell:
        return None
    if spec.kind == "number":
        if not NUMBER_RE.fullmatch(cell):
            raise ValueError(f"{cell!r} in grades.csv is not a number")
        return float(cell.replace(",", "."))
    return fit_label(cell)


def fit_label(value: str) -> str | None:
    """
    A label, trimmed, or `None` when nothing is left of it.

    Raises:
        ValueError: The label is longer than the server stores.
    """
    label = value.strip()
    if not label:
        return None
    if len(label) > MAX_LABEL:
        raise ValueError(f"label {label!r} is longer than {MAX_LABEL} characters")
    return label
