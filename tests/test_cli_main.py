"""
Tests for `codehood.cli.main`, the console-script entry point: failures every
command shares end as one `error:` line and exit code 1, not a traceback.
"""

from __future__ import annotations

import sys

import pytest

from codehood.api import base as base_module
from codehood.cli import main

TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    '\n[server]\nurl = "http://localhost:9"\n'
)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", tmp_path / "credentials.toml")
    (tmp_path / "codehood.toml").write_text(TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["codehood", *args])
    with pytest.raises(SystemExit) as exit_info:
        main()
    return exit_info.value.code


def test_a_command_run_without_login_is_a_one_line_error(repo, monkeypatch, capsys):
    code = _run(monkeypatch, "attendance")

    err = capsys.readouterr().err
    assert code == 1
    assert "error: not logged in to http://localhost:9 -- run `codehood login`" in err
    assert "Traceback" not in err


def test_an_unreachable_server_is_a_one_line_error(repo, monkeypatch, capsys):
    base_module.save_token("http://localhost:9", "token", login="ada")

    code = _run(monkeypatch, "attendance")

    err = capsys.readouterr().err
    assert code == 1
    assert "error: could not reach http://localhost:9" in err
    assert "Traceback" not in err
