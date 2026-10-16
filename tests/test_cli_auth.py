"""
Tests for `codehood login` / `codehood logout`. See
`dev/specs/to-review/login.md`, "Proving it works".
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.api import generated as generated_module
from codehood.cli.base import app
from codehood.models.base import Model

runner = CliRunner()


class _ErrorPayload(Model):
    """
    Stands in for whatever the server sends on a failed login. It has no
    generated counterpart: the spec documents no error response for
    `login`, so the CLI only ever sees the base `CodehoodAPIError`.
    """

    message: str


TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    '\n[server]\nurl = "https://codehood.example.edu"\n'
)


@pytest.fixture(autouse=True)
def credentials_path(tmp_path, monkeypatch):
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", tmp_path / "credentials.toml")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "codehood.toml").write_text(TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_login_outside_a_repo_errors_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["login"])
    assert result.exit_code == 1
    assert "not a codehood repository" in result.output


def test_login_happy_path_stores_token_and_never_prints_it(repo, monkeypatch):
    monkeypatch.setattr(
        generated_module,
        "login",
        lambda **kwargs: generated_module.LoginResponse(token="super-secret-token"),
    )
    result = runner.invoke(app, ["login"], input="ada\npassword123\n")
    assert result.exit_code == 0
    assert "logged in to https://codehood.example.edu" in result.output
    assert "super-secret-token" not in result.output
    assert (
        base_module.load_token("https://codehood.example.edu") == "super-secret-token"
    )


def test_login_defaults_to_the_course_instructor(repo, monkeypatch):
    sent = {}

    def _login(**kwargs):
        sent["login"] = kwargs["body"].login
        return generated_module.LoginResponse(token="t")

    monkeypatch.setattr(generated_module, "login", _login)
    result = runner.invoke(app, ["login"], input="\npassword123\n")
    assert result.exit_code == 0
    assert "Login [ada]" in result.output
    assert sent["login"] == "ada"


def test_login_bad_credentials_exits_nonzero_and_stores_nothing(repo, monkeypatch):
    def _raise(**kwargs):
        # The server documents no error response for `login`, so there is no
        # generated subclass for one -- the CLI catches the base class.
        raise base_module.CodehoodAPIError(
            401, _ErrorPayload(message="invalid credentials")
        )

    monkeypatch.setattr(generated_module, "login", _raise)
    result = runner.invoke(app, ["login"], input="ada\nwrong\n")
    assert result.exit_code == 1
    assert "invalid credentials" in result.output
    assert base_module.load_token("https://codehood.example.edu") is None


def test_logout_outside_a_repo_errors_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 1
    assert "not a codehood repository" in result.output


def test_logout_deletes_an_existing_token(repo):
    base_module.save_token("https://codehood.example.edu", "abc123")
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert "logged out of https://codehood.example.edu" in result.output
    assert base_module.load_token("https://codehood.example.edu") is None


def test_logout_with_nothing_stored_says_so_without_erroring(repo):
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert "not logged in to https://codehood.example.edu" in result.output


SERVER = "https://codehood.example.edu"


def _fake_login(monkeypatch, token: str = "tok") -> None:
    monkeypatch.setattr(
        generated_module,
        "login",
        lambda **kwargs: generated_module.LoginResponse(token=token),
    )


def test_login_says_which_login_it_stored(repo, monkeypatch):
    _fake_login(monkeypatch)
    result = runner.invoke(app, ["login"], input="ada\npw\n")
    assert result.exit_code == 0
    assert "logged in to https://codehood.example.edu as ada" in result.output
    assert "replacing" not in result.output


def test_login_of_another_user_says_it_replaces_the_stored_login(repo, monkeypatch):
    _fake_login(monkeypatch, "first")
    runner.invoke(app, ["login"], input="ada\npw\n")
    _fake_login(monkeypatch, "second")

    result = runner.invoke(app, ["login"], input="bob\npw\n")

    assert result.exit_code == 0
    assert "replacing the stored login for https://codehood.example.edu" in (
        result.output
    )
    assert "ada" in result.output
    assert "as bob" in result.output
    assert base_module.load_token(SERVER) == "second"


def test_login_again_as_the_same_user_is_not_a_replacement(repo, monkeypatch):
    _fake_login(monkeypatch, "first")
    runner.invoke(app, ["login"], input="ada\npw\n")
    _fake_login(monkeypatch, "second")

    result = runner.invoke(app, ["login"], input="ada\npw\n")

    assert result.exit_code == 0
    assert "replacing" not in result.output
    assert base_module.load_token(SERVER) == "second"


def test_login_over_a_token_from_before_logins_were_recorded_still_warns(
    repo, monkeypatch
):
    base_module.save_token(SERVER, "old")
    _fake_login(monkeypatch, "new")

    result = runner.invoke(app, ["login"], input="bob\npw\n")

    assert result.exit_code == 0
    assert "replacing the stored login for https://codehood.example.edu" in (
        result.output
    )
    assert base_module.load_token(SERVER) == "new"


def test_a_failed_login_keeps_the_stored_one(repo, monkeypatch):
    _fake_login(monkeypatch, "first")
    runner.invoke(app, ["login"], input="ada\npw\n")

    def _raise(**kwargs):
        raise base_module.CodehoodAPIError(401, _ErrorPayload(message="nope"))

    monkeypatch.setattr(generated_module, "login", _raise)
    result = runner.invoke(app, ["login"], input="bob\nwrong\n")

    assert result.exit_code == 1
    assert "replacing" not in result.output
    assert base_module.load_token(SERVER) == "first"
    assert base_module.load_login(SERVER) == "ada"


def test_logout_says_which_login_it_forgot(repo, monkeypatch):
    _fake_login(monkeypatch)
    runner.invoke(app, ["login"], input="ada\npw\n")

    result = runner.invoke(app, ["logout"])

    assert result.exit_code == 0
    assert "logged out of https://codehood.example.edu" in result.output
    assert "ada" in result.output
    assert base_module.load_token(SERVER) is None
    assert base_module.load_login(SERVER) is None
