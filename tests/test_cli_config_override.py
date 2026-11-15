"""
Tests for the global `--config` option and `CODEHOOD_CONFIG`. See
`dev/specs/to-do/config-override.md`, "Acceptance criteria".
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from codehood import repo as repo_module
from codehood.api import base as base_module
from codehood.api import generated as generated_module
from codehood.cli.base import app
from codehood.cli.push import read_local_state
from codehood.models.repo import RepoConfig

runner = CliRunner()

MAIN_URL = "https://main.example.edu"
OTHER_URL = "https://other.example.edu"


def _toml(url: str) -> str:
    return (
        '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
        f'\n[server]\nurl = "{url}"\n'
    )


@pytest.fixture
def course(tmp_path, monkeypatch):
    """
    A directory with `codehood.toml` (main server) and `other.toml` (other server).
    """
    (tmp_path / "codehood.toml").write_text(_toml(MAIN_URL), encoding="utf-8")
    (tmp_path / "other.toml").write_text(_toml(OTHER_URL), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _logins(monkeypatch):
    """
    Stub `generated.login` and `login` prompts; returns the list of clients used.
    """
    clients: list[httpx.Client] = []

    def fake_login(*, body, client):
        clients.append(client)
        return generated_module.LoginResponse(token="tok")

    monkeypatch.setattr(generated_module, "login", fake_login)
    return clients


def test_config_option_reads_that_file_not_codehood_toml(course):
    result = runner.invoke(app, ["-c", "other.toml", "attendance"])
    # No token for OTHER_URL: the error names the override's server.
    assert MAIN_URL not in str(result.exception)
    assert OTHER_URL in str(result.exception)


def test_config_option_long_form(course):
    result = runner.invoke(app, ["--config", "other.toml", "attendance"])
    assert OTHER_URL in str(result.exception)


def test_env_var_behaves_like_the_option(course, monkeypatch):
    monkeypatch.setenv("CODEHOOD_CONFIG", "other.toml")
    result = runner.invoke(app, ["attendance"])
    assert OTHER_URL in str(result.exception)


def test_option_beats_the_env_var(course, monkeypatch):
    (course / "third.toml").write_text(_toml("https://third.example.edu"))
    monkeypatch.setenv("CODEHOOD_CONFIG", "other.toml")
    result = runner.invoke(app, ["-c", "third.toml", "attendance"])
    assert "https://third.example.edu" in str(result.exception)


def test_empty_env_var_counts_as_unset(course, monkeypatch):
    monkeypatch.setenv("CODEHOOD_CONFIG", "")
    result = runner.invoke(app, ["attendance"])
    assert MAIN_URL in str(result.exception)


def test_override_is_relative_to_cwd_not_to_the_push_path(course):
    sub = course / "sub"
    sub.mkdir()
    (sub / "x.toml").write_text("not [valid toml")
    (course / "x.toml").write_text(_toml(OTHER_URL))
    result = runner.invoke(app, ["-c", "./x.toml", "push", "--dry-run", "sub/"])
    # `./x.toml` parsed fine; the failure is about `sub/`'s files.
    assert "no README.md at sub" in result.output


def test_a_config_in_the_root_is_not_reported_as_unconsumed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            *("-c", "alt.toml", "init", ".", "--server", OTHER_URL),
            *("--discipline", "cs101", "--instructor", "ada", "--edition", "2026-1"),
            *("--no-git", "--no-examples"),
        ],
    )
    assert result.exit_code == 0, result.output
    (tmp_path / "questions" / "stray.txt").write_text("x")
    repo_module.set_config_override(Path("alt.toml"))

    config = RepoConfig.open(Path("alt.toml"))
    unconsumed = read_local_state(Path("."), config).unconsumed

    assert unconsumed == ("questions/stray.txt",)


def test_push_reads_the_override_for_the_files_under_path(course):
    sub = course / "sub"
    sub.mkdir()
    # No README.md under sub: the config loaded, the files are read from sub/.
    result = runner.invoke(app, ["-c", "other.toml", "push", "--dry-run", "sub/"])
    assert result.exit_code == 1
    assert "no README.md at sub" in result.output


@pytest.mark.parametrize(
    "command",
    [
        ["push", "--dry-run"],
        ["grades"],
        ["attendance"],
        ["login"],
        ["logout"],
        ["api", "--help"],
    ],
)
def test_missing_override_file_is_a_one_line_error(course, command):
    result = runner.invoke(app, ["-c", "missing.toml", *command], input="ada\npw\n")
    assert result.exit_code == 1
    assert (
        result.output.strip() == "error: could not find Codehood config at missing.toml"
    )


def test_login_uses_the_override_server_and_stores_the_token_under_it(
    course, monkeypatch
):
    clients = _logins(monkeypatch)
    result = runner.invoke(app, ["-c", "other.toml", "login"], input="ada\npw\n")
    assert result.exit_code == 0, result.output
    assert f"logged in to {OTHER_URL}" in result.output
    assert str(clients[0].base_url).startswith(OTHER_URL)
    assert base_module.load_token(OTHER_URL) == "tok"
    assert base_module.load_token(MAIN_URL) is None


def test_logout_uses_the_override_server(course):
    base_module.save_token(OTHER_URL, "tok")
    base_module.save_token(MAIN_URL, "keep")
    result = runner.invoke(app, ["-c", "other.toml", "logout"])
    assert result.exit_code == 0
    assert f"logged out of {OTHER_URL}" in result.output
    assert base_module.load_token(OTHER_URL) is None
    assert base_module.load_token(MAIN_URL) == "keep"


def test_get_client_without_argument_uses_the_override(course):
    repo_module.set_config_override(course / "other.toml")
    assert str(base_module.get_client().base_url).startswith(OTHER_URL)


def test_get_client_without_override_uses_codehood_toml(course):
    assert str(base_module.get_client().base_url).startswith(MAIN_URL)


INIT_ARGS = [
    "--discipline", "cs101", "--instructor", "ada", "--edition", "2026-1",
    "--server", "https://codehood.example.edu", "--no-git",
]  # fmt: skip


def test_init_writes_the_config_to_the_override_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "course"
    args = ["-c", "other.toml", "init", "course", *INIT_ARGS]

    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert (tmp_path / "other.toml").is_file()
    assert not (target / "codehood.toml").exists()
    assert (target / "README.md").is_file()

    second = runner.invoke(app, args)
    assert second.exit_code == 0
    assert "exists  " in second.output
    assert any(
        line.split()[-1] == "other.toml" and line.split()[0] == "exists"
        for line in second.output.splitlines()
    )


def test_init_creates_the_missing_parent_of_the_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["-c", "conf/prod.toml", "init", "course", *INIT_ARGS])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "conf" / "prod.toml").is_file()


def test_init_over_an_override_naming_another_course_conflicts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "other.toml").write_text(_toml(OTHER_URL).replace("cs101", "cs202"))
    result = runner.invoke(app, ["-c", "other.toml", "init", "course", *INIT_ARGS])
    assert result.exit_code == 1
    assert "already names a course" in result.output


def test_a_second_invocation_without_the_option_reads_codehood_toml(course):
    first = runner.invoke(app, ["-c", "other.toml", "attendance"])
    assert OTHER_URL in str(first.exception)
    second = runner.invoke(app, ["attendance"])
    assert MAIN_URL in str(second.exception)


def test_help_lists_the_option_and_the_env_var():
    result = runner.invoke(app, ["--help"], terminal_width=200)
    assert "--config" in result.output
    assert "-c" in result.output
    assert "CODEHOOD_CONFIG" in result.output
