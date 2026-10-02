"""
Tests for grade columns through the commands: `codehood push` with a
`[[grades.column]]` table, and `codehood grades`. See
`dev/specs/to-review/push-grades.md`, "CLI surface".

HTTP is answered by `FakeServer`, an in-memory course behind an `httpx`
mock transport, injected by monkeypatching `get_client` on both command
modules (see `test_cli_push.py` for why the modules are fetched with
`importlib`).
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field

import httpx
import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.cli.base import app

push_module = importlib.import_module("codehood.cli.push")
grades_module = importlib.import_module("codehood.cli.grades")

runner = CliRunner()

SERVER = "http://localhost:4321"
BASE = "/api/course/cs101/ada_2026-1"
STAMP = "2026-01-01T00:00:00Z"

TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    f'\n[server]\nurl = "{SERVER}"\n'
)

COLUMNS = """
[[grades.column]]
slug = "assignments"
title = "Assignments"

[[grades.column]]
slug = "final"
title = "Final grade"
kind = "label"
"""

CALENDAR_MD = """---
start: 2026-01-01
end:   2026-06-01
days:
  - Mon 14:00 2h, Lecture
holidays: []
---

# Schedule

## Course overview

What we will cover.
"""

GRADES_PY = """
def grade(student):
    midterm = student.exams["midterm"].score
    return {"final": "MS" if (midterm or 0) >= 70 else "MI"}
"""

GRADES_CSV = "school_id,assignments\n190,82.5\n191,60\n999,10\n"


def _student(username: str, school_id: str, midterm: dict, **overrides) -> dict:
    body = {
        "username": username,
        "name": username.title(),
        "email": f"{username}@example.com",
        "schoolId": school_id,
        "githubId": None,
        "status": "ACTIVE",
        "results": {"midterm": midterm},
    }
    body.update(overrides)
    return body


@dataclass
class FakeServer:
    """
    One course on a server: its grade columns, its students, and a log of
    every write it received.
    """

    columns: dict[str, dict] = field(default_factory=dict)
    students: list[dict] = field(
        default_factory=lambda: [
            _student("hopper", "190", {"kind": "total", "total": 0.8}),
            _student("liskov", "191", {"kind": "missed"}, status="DROPPED"),
        ]
    )
    writes: list[tuple[str, str]] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        if method != "GET":
            self.writes.append((method, path))

        if path == f"{BASE}/grade-column":
            if method == "GET":
                return httpx.Response(200, json=list(self.columns.values()))
            body = json.loads(request.content)
            self.columns[body["slug"]] = {
                **body,
                "releasedAt": None,
                "createdAt": STAMP,
                "updatedAt": STAMP,
            }
            return httpx.Response(200, json=self.columns[body["slug"]])
        if path.startswith(f"{BASE}/grade-column/") and method == "DELETE":
            del self.columns[path.rsplit("/", 1)[1]]
            return httpx.Response(
                200, json={"success": True, "message": "deleted", "deleted": True}
            )
        if path == f"{BASE}/grades":
            exams = [{"slug": "midterm", "title": "Midterm", "scheduledAt": None}]
            return httpx.Response(200, json={"exams": exams, "students": self.students})

        if method == "GET" and path == BASE:
            return httpx.Response(200, json=_course_json())
        if method == "GET":
            return httpx.Response(200, json=[])
        if path == "/api/course":
            return httpx.Response(200, json=_course_json())
        if path == f"{BASE}/time-slot":
            return httpx.Response(200, json=_timeslot_json())
        if path == f"{BASE}/calendar-event":
            return httpx.Response(200, json=_calendar_event_json())
        raise AssertionError(f"unexpected request: {method} {request.url}")


def _course_json() -> dict:
    return {
        "description": "A description.",
        "discipline": {"slug": "cs101", "name": "Intro to CS"},
        "edition": {
            "slug": "2026-1",
            "name": "2026-1",
            "startAt": STAMP,
            "endAt": STAMP,
            "createdAt": STAMP,
        },
        "instructor": {"name": "Ada Lovelace", "username": "ada"},
        "enrollmentCount": 2,
        "rev": None,
        "startAt": STAMP,
        "endAt": STAMP,
        "createdAt": STAMP,
        "updatedAt": STAMP,
        "joinedAt": STAMP,
    }


def _timeslot_json() -> dict:
    return {
        "id": 1,
        "courseId": 1,
        "slug": "mon",
        "title": "Lecture",
        "day": "MONDAY",
        "start": {"hour": 14, "minute": 0},
        "duration": {"hours": 2, "minutes": 0},
        "createdAt": STAMP,
        "updatedAt": STAMP,
    }


def _calendar_event_json() -> dict:
    return {
        "kind": "REGULAR",
        "title": "Course overview",
        "description": "What we will cover.",
        "startAt": STAMP,
        "week": 0,
        "timeSlot": {
            "slug": "mon",
            "day": "MONDAY",
            "start": {"hour": 14, "minute": 0},
            "duration": {"hours": 2, "minutes": 0},
        },
        "rev": "ref-event",
        "createdAt": STAMP,
        "updatedAt": STAMP,
    }


@pytest.fixture(autouse=True)
def credentials_path(tmp_path_factory, monkeypatch):
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)
    base_module.save_token(SERVER, "test-token")


@pytest.fixture
def server(monkeypatch) -> FakeServer:
    fake = FakeServer()

    def _get_client(base_url=None):
        return httpx.Client(
            base_url=base_url or SERVER, transport=httpx.MockTransport(fake)
        )

    monkeypatch.setattr(push_module, "get_client", _get_client)
    monkeypatch.setattr(grades_module, "get_client", _get_client)
    return fake


@pytest.fixture
def repo(tmp_path):
    """
    A course repository with two grade columns, a `grades.csv` holding one
    of them and a `grades.py` computing the other.
    """
    (tmp_path / "codehood.toml").write_text(TOML + COLUMNS, encoding="utf-8")
    (tmp_path / "README.md").write_text("# CS101\n\nA description.\n", encoding="utf-8")
    (tmp_path / "calendar.md").write_text(CALENDAR_MD, encoding="utf-8")
    (tmp_path / "grades.csv").write_text(GRADES_CSV, encoding="utf-8")
    (tmp_path / "grades.py").write_text(GRADES_PY, encoding="utf-8")
    return tmp_path


def _grade_writes(server: FakeServer) -> list[tuple[str, str]]:
    return [write for write in server.writes if "grade-column" in write[1]]


#
# codehood push
#
def test_push_sends_each_column_whole_in_file_order(repo, server):
    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 0, result.output

    assignments, final = server.columns["assignments"], server.columns["final"]
    assert (assignments["title"], assignments["kind"], assignments["position"]) == (
        "Assignments",
        "NUMBER",
        0,
    )
    assert assignments["values"] == [
        {"username": "hopper", "value": 82.5},
        {"username": "liskov", "value": 60.0},
    ]
    assert (final["kind"], final["position"]) == ("LABEL", 1)
    assert final["values"] == [
        {"username": "hopper", "value": "MS"},
        {"username": "liskov", "value": "MI"},
    ]
    assert "grade column assignments (2 values)" in result.output
    assert "grade column final (2 values)" in result.output


def test_push_warns_about_a_csv_row_for_nobody_enrolled(repo, server):
    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 0, result.output
    assert "no enrolled student with school_id 999" in result.output


def test_a_second_push_sends_no_grade_column(repo, server):
    runner.invoke(app, ["push", str(repo)])
    server.writes.clear()

    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 0, result.output
    assert _grade_writes(server) == []


def test_push_sends_only_the_column_whose_values_changed(repo, server):
    runner.invoke(app, ["push", str(repo)])
    server.writes.clear()
    (repo / "grades.csv").write_text(
        "school_id,assignments\n190,90\n191,60\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 0, result.output
    assert _grade_writes(server) == [("PUT", f"{BASE}/grade-column")]
    assert server.columns["assignments"]["values"][0]["value"] == 90.0


def test_push_deletes_a_column_the_file_no_longer_declares(repo, server):
    runner.invoke(app, ["push", str(repo)])
    server.writes.clear()
    only_first = COLUMNS.split("[[grades.column]]")[1]
    (repo / "codehood.toml").write_text(
        TOML + "\n[[grades.column]]" + only_first, encoding="utf-8"
    )
    # The function stops returning the column too: a key that is not
    # declared would refuse the grades part.
    (repo / "grades.py").unlink()

    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 0, result.output
    assert set(server.columns) == {"assignments"}
    assert "delete grade column final" in result.output


def test_no_prune_reports_a_column_deletion_without_executing_it(repo, server):
    runner.invoke(app, ["push", str(repo)])
    (repo / "codehood.toml").write_text(TOML, encoding="utf-8")

    result = runner.invoke(app, ["push", str(repo), "--no-prune"])
    assert result.exit_code == 0, result.output
    assert set(server.columns) == {"assignments", "final"}
    assert "skipped  delete grade column final (--no-prune)" in result.output


def test_dry_run_plans_the_columns_and_writes_nothing(repo, server):
    result = runner.invoke(app, ["push", str(repo), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "planned  grade column assignments (2 values)" in result.output
    assert server.writes == []


def test_a_broken_function_refuses_the_grades_and_pushes_the_rest(repo, server):
    (repo / "grades.py").write_text(
        "def grade(student):\n    return {'final': student.exams['p9'].score}\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["push", str(repo)])

    assert result.exit_code == 1
    assert "error: grades: grades.py raised for hopper" in result.output
    assert "KeyError: 'p9'" in result.output
    assert _grade_writes(server) == []
    assert ("PUT", "/api/course") in server.writes


def test_a_refused_grades_part_leaves_the_servers_columns_alone(repo, server):
    runner.invoke(app, ["push", str(repo)])
    (repo / "grades.csv").write_text("matricula,assignments\n190,1\n", encoding="utf-8")

    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 1
    assert "the first column is 'matricula'" in result.output
    assert set(server.columns) == {"assignments", "final"}


def test_columns_declared_with_nothing_to_compute_them_from_refuse(repo, server):
    (repo / "grades.csv").unlink()
    (repo / "grades.py").unlink()

    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 1
    assert "neither grades.py nor grades.csv" in result.output


def test_a_repository_with_no_column_table_touches_no_grade_column(repo, server):
    (repo / "codehood.toml").write_text(TOML, encoding="utf-8")
    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 0, result.output
    assert _grade_writes(server) == []


def test_a_bad_column_table_is_a_clean_error(repo, server):
    (repo / "codehood.toml").write_text(
        TOML + '\n[[grades.column]]\nslug = "Not A Slug"\n', encoding="utf-8"
    )
    result = runner.invoke(app, ["push", str(repo)])
    assert result.exit_code == 1
    assert "error:" in result.output
    assert server.writes == []


#
# codehood grades
#
def test_grades_prints_the_table_and_writes_nothing(repo, server):
    result = runner.invoke(app, ["grades", str(repo)])
    assert result.exit_code == 0, result.output

    lines = result.output.splitlines()
    header = next(line for line in lines if "Assignments" in line)
    assert "Final grade" in header
    hopper = next(line for line in lines if "hopper" in line)
    assert "82.5" in hopper and "MS" in hopper
    liskov = next(line for line in lines if "liskov" in line)
    assert "(dropped)" in liskov and "60" in liskov and "MI" in liskov
    assert "no enrolled student with school_id 999" in result.output
    assert server.writes == []


def test_grades_reports_a_broken_function_and_exits_nonzero(repo, server):
    (repo / "grades.py").write_text(
        "def grade(student):\n    return {'typo': 1}\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["grades", str(repo)])
    assert result.exit_code == 1
    assert "'typo'" in result.output


def test_grades_says_so_when_no_column_is_declared(repo, server):
    (repo / "codehood.toml").write_text(TOML, encoding="utf-8")
    result = runner.invoke(app, ["grades", str(repo)])
    assert result.exit_code == 0, result.output
    assert "declares no grade column" in result.output
