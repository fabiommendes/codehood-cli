"""
Tests for the `CODEHOOD_TOKEN` environment variable, which overrides the
tokens stored in `~/.codehood/credentials.toml`.
"""

from __future__ import annotations

import httpx
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.api import generated as generated_module
from codehood.api.base import auth_headers, load_token, save_token
from codehood.cli.base import app
from codehood.cli.init import _has_credentials

runner = CliRunner()

URL = "https://codehood.example.edu"
TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    f'\n[server]\nurl = "{URL}"\n'
)


def test_env_token_wins_over_the_file(monkeypatch):
    save_token(URL, "from-file")
    monkeypatch.setenv("CODEHOOD_TOKEN", "from-env")
    assert load_token(URL) == "from-env"


def test_env_token_applies_to_any_server(monkeypatch):
    monkeypatch.setenv("CODEHOOD_TOKEN", "from-env")
    assert load_token("http://other.example") == "from-env"


def test_env_token_is_sent_as_bearer(monkeypatch):
    save_token(URL, "from-file")
    monkeypatch.setenv("CODEHOOD_TOKEN", "from-env")
    client = httpx.Client(base_url=URL)
    assert auth_headers(client) == {"Authorization": "Bearer from-env"}


def test_env_token_never_touches_the_credentials_file(
    monkeypatch, credentials_path, tmp_path
):
    # A directory in place of the file makes any read or write fail loudly.
    credentials_path.mkdir()
    monkeypatch.setenv("CODEHOOD_TOKEN", "from-env")
    assert load_token(URL) == "from-env"
    assert auth_headers(httpx.Client(base_url=URL)) == {
        "Authorization": "Bearer from-env"
    }
    assert _has_credentials(URL)


def test_file_content_is_unchanged_by_env_lookup(monkeypatch, credentials_path):
    save_token(URL, "from-file")
    before = credentials_path.read_bytes()
    monkeypatch.setenv("CODEHOOD_TOKEN", "from-env")
    load_token(URL)
    assert credentials_path.read_bytes() == before


def test_empty_env_token_falls_back_to_the_file(monkeypatch):
    save_token(URL, "from-file")
    monkeypatch.setenv("CODEHOOD_TOKEN", "")
    assert load_token(URL) == "from-file"


def test_empty_env_token_and_no_file_means_not_logged_in(monkeypatch):
    monkeypatch.setenv("CODEHOOD_TOKEN", "")
    assert load_token(URL) is None
    assert not _has_credentials(URL)


def test_init_sees_env_token_as_credentials(monkeypatch):
    monkeypatch.setenv("CODEHOOD_TOKEN", "from-env")
    assert _has_credentials(URL)


def test_login_notes_that_env_overrides_the_stored_key(
    tmp_path, monkeypatch, credentials_path
):
    (tmp_path / "codehood.toml").write_text(TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEHOOD_TOKEN", "from-env")
    monkeypatch.setattr(
        generated_module,
        "login",
        lambda **kwargs: generated_module.LoginResponse(token="new-key"),
    )
    result = runner.invoke(app, ["login"], input="ada\npassword123\n")
    assert result.exit_code == 0
    assert "CODEHOOD_TOKEN" in result.output
    assert "new-key" in credentials_path.read_text()


def test_logout_notes_that_env_overrides_the_stored_key(
    tmp_path, monkeypatch, credentials_path
):
    (tmp_path / "codehood.toml").write_text(TOML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    save_token(URL, "from-file")
    monkeypatch.setenv("CODEHOOD_TOKEN", "from-env")
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert "CODEHOOD_TOKEN" in result.output
    assert "from-file" not in credentials_path.read_text()
    assert base_module.TOKEN_ENV == "CODEHOOD_TOKEN"
