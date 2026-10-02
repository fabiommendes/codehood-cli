"""
Tests for the pure core of pushing grade columns: `codehood.push.grades`,
the grade half of `codehood.push.plan`, and `codehood.push.hook`. See
`dev/specs/to-review/push-grades.md`, "Proof".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codehood.grades import ExamResult, Student
from codehood.push.grades import (
    ColumnSpec,
    GradeColumn,
    GradesError,
    Roster,
    ServerStudent,
    build_roster,
    compute_columns,
    parse_grades_csv,
)
from codehood.push.hook import load_grade_function
from codehood.push.plan import (
    DeleteGradeColumn,
    LocalState,
    ServerState,
    UpsertGradeColumn,
    plan_grades,
)


def _server_student(username: str, **overrides) -> ServerStudent:
    fields = {
        "username": username,
        "name": username.title(),
        "email": f"{username}@example.com",
        "school_id": f"19{username}",
        "github": f"gh-{username}",
        "status": "active",
        "exams": {},
    }
    fields.update(overrides)
    return ServerStudent(**fields)  # type: ignore[arg-type]


def _roster(*usernames: str, csv: str | None = None) -> Roster:
    students = [_server_student(username) for username in usernames]
    return build_roster(students, parse_grades_csv(csv) if csv else None)


NUMBER = ColumnSpec(slug="total", title="Total", kind="number")
LABEL = ColumnSpec(slug="final", title="Final grade", kind="label")


#
# grades.csv
#
def test_csv_reads_the_id_header_and_keeps_cells_as_text():
    sheet = parse_grades_csv("school_id,assignments,note\n190,82.5,late\n191,,\n")
    assert sheet.id_field == "school_id"
    assert sheet.headers == ("assignments", "note")
    assert sheet.rows == {
        "190": {"assignments": "82.5", "note": "late"},
        "191": {"assignments": "", "note": ""},
    }


def test_csv_takes_a_semicolon_delimiter_and_a_decimal_comma():
    roster = _roster("ana", csv="username;assignments;note\nana;7,5;ok\n")
    assert roster.students[0].scores == {"assignments": 7.5, "note": "ok"}


def test_csv_with_a_comma_delimiter_reads_a_quoted_decimal_comma():
    roster = _roster("ana", csv='username,assignments\nana,"7,5"\n')
    assert roster.students[0].scores == {"assignments": 7.5}


def test_csv_ignores_a_byte_order_mark_and_blank_rows():
    sheet = parse_grades_csv("﻿username,a\n\nana,1\n,\n")
    assert sheet.rows == {"ana": {"a": "1"}}


@pytest.mark.parametrize("header", ["school_id", "username", "github", "email"])
def test_csv_matches_students_by_each_id_header(header: str):
    ids = {
        "school_id": "19ana",
        "username": "ana",
        "github": "GH-Ana",
        "email": "ANA@example.com",
    }
    roster = _roster("ana", "bia", csv=f"{header},a\n{ids[header]},9\n")
    by_username = {student.username: student for student in roster.students}
    assert by_username["ana"].scores == {"a": 9.0}
    assert by_username["bia"].scores == {"a": None}
    assert roster.unmatched == ()


@pytest.mark.parametrize(
    "text,fragment",
    [
        ("", "empty"),
        ("matricula,a\n1,2\n", "first column"),
        ("username,a,a\nana,1,2\n", "repeated"),
        ("username,a\n,1\n", "row 2"),
        ("username,a\nana,1\nana,2\n", "twice"),
    ],
)
def test_csv_refuses_what_it_cannot_read(text: str, fragment: str):
    with pytest.raises(GradesError) as error:
        parse_grades_csv(text)
    assert fragment in str(error.value)


def test_a_row_for_nobody_enrolled_is_reported_and_skipped():
    roster = _roster("ana", csv="username,a\nana,1\nghost,2\n")
    assert roster.unmatched == ("ghost",)
    assert [student.username for student in roster.students] == ["ana"]


def test_a_student_without_the_id_the_file_uses_reads_no_score():
    students = [_server_student("ana", school_id=None)]
    roster = build_roster(students, parse_grades_csv("school_id,a\n19ana,1\n"))
    assert roster.students[0].scores == {"a": None}
    assert roster.unmatched == ("19ana",)


def test_without_a_csv_every_student_has_no_scores():
    roster = _roster("ana")
    assert roster.students[0].scores == {}
    assert roster.headers == ()


#
# Columns
#
def test_a_column_takes_the_functions_value_then_the_csv_cell():
    roster = _roster("ana", "bia", csv="username,total\nana,5\nbia,6\n")

    def grade(student: Student) -> dict[str, float | str | None]:
        return {"total": 10} if student.username == "ana" else {}

    [column] = compute_columns([NUMBER], roster, grade)
    assert column.values == (("ana", 10.0), ("bia", 6.0))


def test_none_from_the_function_is_no_value_and_does_not_fall_back_to_the_csv():
    roster = _roster("ana", csv="username,total\nana,5\n")
    [column] = compute_columns([NUMBER], roster, lambda student: {"total": None})
    assert column.values == ()


def test_a_csv_column_is_pushed_with_no_function_at_all():
    roster = _roster("ana", "bia", csv="username,total,final\nana,7.5,MS\nbia,,\n")
    number, label = compute_columns([NUMBER, LABEL], roster, None)
    assert number.values == (("ana", 7.5),)
    assert label.values == (("ana", "MS"),)
    assert (number.position, label.position) == (0, 1)


def test_a_label_column_reads_a_numeric_looking_csv_cell_as_text():
    roster = _roster("ana", csv="username,final\nana,7.50\n")
    [column] = compute_columns([LABEL], roster, None)
    assert column.values == (("ana", "7.50"),)


def test_values_are_ordered_by_username_and_numbers_become_floats():
    roster = _roster("zoe", "ana")
    [column] = compute_columns([NUMBER], roster, lambda student: {"total": 7})
    assert column.values == (("ana", 7.0), ("zoe", 7.0))
    assert all(isinstance(value, float) for _, value in column.values)


def test_the_function_gets_exams_scores_and_dropped_students():
    seen: list[Student] = []
    students = [
        _server_student(
            "ana",
            status="dropped",
            exams={"p1": ExamResult(score=80.0, state="graded")},
        )
    ]
    roster = build_roster(students, parse_grades_csv("username,work\nana,9\n"))

    def grade(student: Student) -> dict[str, float | str | None]:
        seen.append(student)
        return {"total": 1.0}

    compute_columns([NUMBER], roster, grade)
    [student] = seen
    assert student.status == "dropped"
    assert student.exams["p1"] == ExamResult(score=80.0, state="graded")
    assert student.scores == {"work": 9.0}


def test_a_function_that_raises_refuses_with_the_student_and_the_traceback():
    def grade(student: Student) -> dict[str, float | str | None]:
        raise KeyError("p9")

    with pytest.raises(GradesError) as error:
        compute_columns([NUMBER], _roster("ana"), grade)
    [problem] = error.value.problems
    assert "ana" in problem
    assert "KeyError: 'p9'" in problem


def test_a_key_that_is_not_a_declared_column_refuses():
    with pytest.raises(GradesError) as error:
        compute_columns(
            [NUMBER], _roster("ana"), lambda student: {"total": 1, "fianl": "MS"}
        )
    assert "'fianl'" in str(error.value)


def test_a_declared_column_nothing_produces_refuses():
    roster = _roster("ana", csv="username,other\nana,1\n")
    with pytest.raises(GradesError) as error:
        compute_columns([NUMBER, LABEL], roster, lambda student: {"total": 1})
    assert "'final'" in str(error.value)
    assert "'total'" not in str(error.value)


@pytest.mark.parametrize(
    "spec,value",
    [
        (NUMBER, "MS"),
        (NUMBER, True),
        (NUMBER, float("nan")),
        (NUMBER, float("inf")),
        (LABEL, 7.5),
        (LABEL, "x" * 33),
    ],
)
def test_a_value_that_does_not_fit_its_column_refuses(spec: ColumnSpec, value: object):
    with pytest.raises(GradesError) as error:
        compute_columns(
            [spec],
            _roster("ana"),
            lambda student: {spec.slug: value},  # type: ignore[dict-item]
        )
    assert "ana" in str(error.value)
    assert repr(spec.slug) in str(error.value)


def test_a_csv_cell_that_is_not_a_number_refuses_a_number_column():
    roster = _roster("ana", csv="username,total\nana,MS\n")
    with pytest.raises(GradesError) as error:
        compute_columns([NUMBER], roster, None)
    assert "'MS'" in str(error.value)


def test_every_problem_is_reported_at_once():
    roster = _roster("ana", "bia")
    with pytest.raises(GradesError) as error:
        compute_columns([NUMBER], roster, lambda student: {"total": "x", "typo": 1})
    assert len(error.value.problems) == 3


def test_a_blank_label_is_no_value_and_a_label_is_trimmed():
    roster = _roster("ana", "bia")

    def grade(student: Student) -> dict[str, float | str | None]:
        return {"final": "  " if student.username == "ana" else " MS "}

    [column] = compute_columns([LABEL], roster, grade)
    assert column.values == (("bia", "MS"),)


def test_a_course_with_no_students_pushes_its_columns_empty():
    columns = compute_columns([NUMBER, LABEL], Roster(), lambda student: {})
    assert [(column.slug, column.values) for column in columns] == [
        ("total", ()),
        ("final", ()),
    ]


#
# rev
#
def test_rev_is_stable_and_changes_with_any_field_that_is_pushed():
    column = GradeColumn(
        slug="total", title="Total", kind="number", position=0, values=(("ana", 7.0),)
    )
    same = GradeColumn(
        slug="total", title="Total", kind="number", position=0, values=(("ana", 7.0),)
    )
    assert column.rev == same.rev
    assert len(column.rev) == 64

    changed = [
        GradeColumn("total", "Sum", "number", 0, (("ana", 7.0),)),
        GradeColumn("total", "Total", "label", 0, (("ana", "7"),)),
        GradeColumn("total", "Total", "number", 1, (("ana", 7.0),)),
        GradeColumn("total", "Total", "number", 0, (("ana", 7.5),)),
        GradeColumn("total", "Total", "number", 0, ()),
    ]
    assert len({column.rev, *(other.rev for other in changed)}) == 6


#
# Plan
#
def _local(columns: tuple[GradeColumn, ...] | None) -> LocalState:
    from datetime import date

    return LocalState(
        discipline="cs101",
        course="ada_2026-1",
        description="",
        start=date(2026, 1, 1),
        end=date(2026, 6, 1),
        grade_columns=columns,
    )


def test_plan_upserts_a_new_or_changed_column_and_skips_an_unchanged_one():
    new = GradeColumn("new", "New", "number", 0, (("ana", 1.0),))
    changed = GradeColumn("changed", "Changed", "number", 1, (("ana", 2.0),))
    same = GradeColumn("same", "Same", "label", 2, (("ana", "MS"),))
    server = ServerState(
        course_exists=True, grade_columns={"changed": "stale", "same": same.rev}
    )
    ops = list(plan_grades(_local((new, changed, same)), server))
    assert ops == [UpsertGradeColumn(column=new), UpsertGradeColumn(column=changed)]


def test_plan_deletes_a_column_the_repository_no_longer_declares():
    server = ServerState(course_exists=True, grade_columns={"gone": "rev"})
    assert list(plan_grades(_local(()), server)) == [DeleteGradeColumn(slug="gone")]


def test_plan_leaves_the_server_alone_when_the_columns_were_not_computed():
    server = ServerState(course_exists=True, grade_columns={"kept": "rev"})
    assert list(plan_grades(_local(None), server)) == []


def test_a_second_plan_after_applying_the_first_is_empty():
    columns = (
        GradeColumn("a", "A", "number", 0, (("ana", 1.0),)),
        GradeColumn("b", "B", "label", 1, ()),
    )
    server = ServerState(course_exists=True, grade_columns={"old": "rev"})
    applied: dict[str, str] = dict(server.grade_columns)
    for op in plan_grades(_local(columns), server):
        if isinstance(op, UpsertGradeColumn):
            applied[op.column.slug] = op.column.rev
        elif isinstance(op, DeleteGradeColumn):
            del applied[op.slug]

    again = ServerState(course_exists=True, grade_columns=applied)
    assert list(plan_grades(_local(columns), again)) == []


#
# grades.py
#
def test_load_grade_function_returns_the_files_grade(tmp_path: Path):
    script = tmp_path / "grades.py"
    script.write_text(
        "def grade(student):\n    return {'total': len(student.username)}\n"
    )
    grade = load_grade_function(script)
    [column] = compute_columns([NUMBER], _roster("ana"), grade)
    assert column.values == (("ana", 3.0),)


def test_a_script_with_no_grade_function_refuses(tmp_path: Path):
    script = tmp_path / "grades.py"
    script.write_text("def grades(student):\n    return {}\n")
    with pytest.raises(GradesError) as error:
        load_grade_function(script)
    assert "'grade'" in str(error.value)


def test_a_script_that_fails_to_import_refuses_with_the_traceback(tmp_path: Path):
    script = tmp_path / "grades.py"
    script.write_text("import no_such_module_anywhere\n")
    with pytest.raises(GradesError) as error:
        load_grade_function(script)
    assert "ModuleNotFoundError" in str(error.value)


#
# The reference case of the spec
#
REFERENCE = """
from codehood.grades import Student

WEIGHTS = {"p1": 0.3, "p2": 0.3, "p3": 0.2}
BANDS = [(90, "SS"), (70, "MS"), (50, "MM"), (30, "MI"), (0.1, "II")]
ORDER = ["SR", "II", "MI", "MM", "MS", "SS"]


def grade(student: Student) -> dict[str, float | str | None]:
    exams = {slug: student.exams[slug].score or 0.0 for slug in WEIGHTS}

    # The substitute exam replaces the lowest score when it beats it.
    substitute = student.exams["sub"].score
    if substitute is not None:
        lowest = min(exams, key=lambda slug: exams[slug])
        exams[lowest] = max(exams[lowest], substitute)

    assignments = student.scores["assignments"] or 0.0
    total = 0.2 * assignments + sum(
        exams[slug] * weight for slug, weight in WEIGHTS.items()
    )

    letter = next((label for floor, label in BANDS if total >= floor), "SR")
    project = student.scores["final-project"] or 0.0
    if project >= 70 and ORDER.index(letter) < ORDER.index("MM"):
        letter = "MM"

    return {"total": round(total, 1), "final": letter}
"""


def _exams(p1, p2, p3, sub=None) -> dict[str, ExamResult]:
    def result(score: float | None) -> ExamResult:
        return ExamResult(
            score=score, state="graded" if score is not None else "missed"
        )

    return {"p1": result(p1), "p2": result(p2), "p3": result(p3), "sub": result(sub)}


def test_the_reference_function_of_the_spec(tmp_path: Path):
    script = tmp_path / "grades.py"
    script.write_text(REFERENCE)
    students = [
        # 0.3*80 + 0.3*90 + 0.2*70 + 0.2*100 = 85
        _server_student("plain", exams=_exams(80.0, 90.0, 70.0)),
        # The substitute (90) replaces the missed p2: 0.3*80 + 0.3*90 + 0.2*70 + 0.2*50 = 75
        _server_student("subbed", exams=_exams(80.0, None, 70.0, sub=90.0)),
        # 0.3*20 + 0.3*20 + 0.2*20 + 0.2*80 = 32, MI, raised to MM by the project.
        _server_student("raised", exams=_exams(20.0, 20.0, 20.0)),
        # Nothing at all.
        _server_student("absent", exams=_exams(None, None, None)),
    ]
    sheet = parse_grades_csv(
        "username,assignments,final-project\nplain,100,0\nsubbed,50,0\nraised,80,75\n"
    )
    total, final = compute_columns(
        [NUMBER, LABEL], build_roster(students, sheet), load_grade_function(script)
    )
    assert dict(total.values) == {
        "plain": 85.0,
        "subbed": 75.0,
        "raised": 32.0,
        "absent": 0.0,
    }
    assert dict(final.values) == {
        "plain": "MS",
        "subbed": "MS",
        "raised": "MM",
        "absent": "SR",
    }
