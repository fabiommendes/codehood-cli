"""
Tests for `codehood attendance`, the Typer command in
`codehood.cli.attendance`: it downloads the course's attendance report and
either prints it as a table or writes it as CSV.

HTTP is answered by an `httpx` mock transport injected by monkeypatching
`get_client` on the command module (see `test_cli_push.py` for why the module
is fetched with `importlib`).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.cli.base import app

attendance_module = importlib.import_module("codehood.cli.attendance")

runner = CliRunner()

SERVER = "http://localhost:4321"
BASE = "/api/course/cs101/ada_2026-1"

TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    f'\n[server]\nurl = "{SERVER}"\n'
)

#: Wide enough that Rich never truncates a cell of the table.
WIDE_TERMINAL = {"COLUMNS": "200"}


def _event(week: int, time_slot: str) -> dict:
    return {
        "week": week,
        "title": f"Aula {week}",
        "startAt": "2026-03-02T14:00:00.000Z",
        "timeSlot": time_slot,
    }


def _student(username: str, name: str, status: str, cells: dict, **overrides) -> dict:
    present = sum(1 for cell in cells.values() if cell == "present")
    total = sum(1 for cell in cells.values() if cell != "before-enrollment")
    body = {
        "username": username,
        "name": name,
        "email": f"{username}@example.com",
        "schoolId": "2026001",
        "status": status,
        "cells": cells,
        "present": present,
        "total": total,
    }
    body.update(overrides)
    return body


REPORT = {
    "events": [_event(1, "manha"), _event(2, "tarde")],
    "students": [
        _student(
            "ada",
            "Ada Lovelace",
            "ACTIVE",
            {"1/manha": "present", "2/tarde": "absent"},
        ),
        _student(
            "bob",
            "Bob Dropped",
            "DROPPED",
            {"1/manha": "before-enrollment", "2/tarde": "present"},
            schoolId="2026002",
        ),
        _student(
            "carol",
            'Hopper, Grace "Amazing"',
            "ACTIVE",
            {"1/manha": "before-enrollment", "2/tarde": "before-enrollment"},
            schoolId=None,
        ),
    ],
}

#: What the server's CSV download produces for `REPORT`: quoted only when a
#: cell needs it, `\r\n` between lines, no trailing newline, a percentage with
#: two decimals and an empty one when the student has no roll call to attend.
REPORT_CSV = (
    "username,name,schoolId,status,1/manha,2/tarde,present,total,%\r\n"
    "ada,Ada Lovelace,2026001,active,1,0,1,2,50.00\r\n"
    "bob,Bob Dropped,2026002,dropped,-,1,1,1,100.00\r\n"
    'carol,"Hopper, Grace ""Amazing""",,active,-,-,0,0,'
)


@pytest.fixture(autouse=True)
def credentials_path(tmp_path_factory, monkeypatch):
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)
    base_module.save_token(SERVER, "test-token")


@pytest.fixture
def repo(tmp_path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    (path / "codehood.toml").write_text(TOML, encoding="utf-8")
    return path


def _serve(monkeypatch, report: dict) -> list[tuple[str, str]]:
    """
    Make the command talk to a server whose attendance report is `report`,
    and return the log of requests it receives.
    """
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == f"{BASE}/attendance":
            return httpx.Response(200, json=report)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    def get_client(base_url=None):
        return httpx.Client(
            base_url=base_url or SERVER, transport=httpx.MockTransport(handler)
        )

    monkeypatch.setattr(attendance_module, "get_client", get_client)
    return calls


def test_without_csv_prints_a_table_with_dropped_students_and_absent_cells(
    repo, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _serve(monkeypatch, REPORT)

    result = runner.invoke(app, ["attendance", str(repo)], env=WIDE_TERMINAL)

    assert result.exit_code == 0, result.output
    for text in ("ada", "bob", "DROPPED", "1/manha", "2/tarde"):
        assert text in result.output
    assert "-" in result.output
    assert list(tmp_path.rglob("*.csv")) == []


def test_csv_option_writes_the_report_exactly_as_the_server_does(
    repo, tmp_path, monkeypatch
):
    _serve(monkeypatch, REPORT)
    out = tmp_path / "out.csv"

    result = runner.invoke(app, ["attendance", str(repo), "--csv", str(out)])

    assert result.exit_code == 0, result.output
    assert out.read_bytes() == REPORT_CSV.encode("utf-8")


def test_course_without_roll_calls_says_so_and_exits_zero(repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _serve(
        monkeypatch, {"events": [], "students": [_student("ada", "Ada", "ACTIVE", {})]}
    )

    result = runner.invoke(app, ["attendance", str(repo)], env=WIDE_TERMINAL)

    assert result.exit_code == 0, result.output
    assert "no roll call" in result.output.lower()
    assert "Traceback" not in result.output
