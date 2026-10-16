"""
Tests for `codehood_cli.api.base`. See `dev/specs/to-review/api.md`,
"A shared client, threaded through as an optional parameter", and
`dev/specs/to-review/login.md`, "Proving it works".
"""

from __future__ import annotations

import stat

import httpx
import pytest

from codehood.api.base import (
    DEFAULT_BASE_URL,
    NotLoggedInError,
    auth_headers,
    delete_token,
    get_client,
    load_login,
    load_token,
    query_params,
    save_token,
    stored_servers,
)


def test_default_base_url_with_no_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = get_client()
    assert str(client.base_url) == DEFAULT_BASE_URL


def test_default_base_url_reads_codehood_toml(tmp_path, monkeypatch):
    (tmp_path / "codehood.toml").write_text(
        '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
        '\n[server]\nurl = "https://codehood.example.edu"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    client = get_client()
    assert str(client.base_url) == "https://codehood.example.edu"


def test_explicit_base_url_wins_over_repo(tmp_path, monkeypatch):
    (tmp_path / "codehood.toml").write_text(
        '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
        '\n[server]\nurl = "https://codehood.example.edu"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    client = get_client("https://other.example.edu")
    assert str(client.base_url) == "https://other.example.edu"


def test_load_token_with_no_store_returns_none():
    assert load_token("http://localhost:4321") is None


def test_save_and_load_token_round_trips(credentials_path):
    save_token("http://localhost:4321", "abc123")
    assert load_token("http://localhost:4321") == "abc123"


def test_save_token_is_chmod_600(credentials_path):
    save_token("http://localhost:4321", "abc123")
    mode = stat.S_IMODE(credentials_path.stat().st_mode)
    assert mode == 0o600


def test_two_servers_dont_clobber_each_other():
    save_token("http://localhost:4321", "abc123")
    save_token("https://codehood.example.edu", "def456")
    assert load_token("http://localhost:4321") == "abc123"
    assert load_token("https://codehood.example.edu") == "def456"


def test_save_token_overwrites_same_server():
    save_token("http://localhost:4321", "abc123")
    save_token("http://localhost:4321", "def456")
    assert load_token("http://localhost:4321") == "def456"


def test_delete_token_reports_whether_there_was_one():
    assert delete_token("http://localhost:4321") is False
    save_token("http://localhost:4321", "abc123")
    assert delete_token("http://localhost:4321") is True
    assert load_token("http://localhost:4321") is None
    assert delete_token("http://localhost:4321") is False


def test_delete_token_leaves_other_servers_alone():
    save_token("http://localhost:4321", "abc123")
    save_token("https://codehood.example.edu", "def456")
    delete_token("http://localhost:4321")
    assert load_token("https://codehood.example.edu") == "def456"


def test_stored_servers_lists_every_server_with_a_token():
    assert stored_servers() == []
    save_token("http://localhost:4321", "abc123")
    save_token("https://codehood.example.edu", "def456")
    assert set(stored_servers()) == {
        "http://localhost:4321",
        "https://codehood.example.edu",
    }


def test_auth_headers_raises_not_logged_in_with_no_token():
    client = httpx.Client(base_url="http://localhost:4321")
    with pytest.raises(NotLoggedInError, match="http://localhost:4321"):
        auth_headers(client)


def test_auth_headers_returns_bearer_header_when_logged_in():
    save_token("http://localhost:4321", "abc123")
    client = httpx.Client(base_url="http://localhost:4321")
    assert auth_headers(client) == {"Authorization": "Bearer abc123"}


#
# query_params
#
# Both of these are regressions, not hypotheticals: `listResource` grew
# `types` and `slugs`, and `codehood push` started answering `400 "2026-1"
# is not a course segment`-style errors because it sent `?types=&slugs=`
# on a call that filtered by neither.
#
def test_query_params_drops_unset_parameters():
    assert query_params({"types": None, "slugs": None}) == {}


def test_query_params_keeps_falsy_values_that_were_actually_given():
    """
    `None` means "not given"; `False`, `0`, and `[]` are values a caller
    chose, and dropping them would silently change the request.
    """
    assert query_params({"active": False, "take": 0, "slugs": []}) == {
        "active": False,
        "take": 0,
        "slugs": [],
    }


#
# Default headers
#
def test_get_client_declares_json_so_astro_allows_a_bodyless_delete():
    """
    A `DELETE` carries no body and so would send no `Content-Type`, which
    Astro's cross-site guard treats as an HTML form submission and refuses
    with `403 Cross-site DELETE form submissions are forbidden`. Pruning a
    resource is exactly that request.
    """
    client = get_client("http://localhost:4321")
    assert client.headers["Content-Type"] == "application/json"


def test_save_token_records_the_login_beside_the_token():
    save_token("https://a.example", "tok", login="ada")
    assert load_token("https://a.example") == "tok"
    assert load_login("https://a.example") == "ada"


def test_a_token_saved_without_a_login_has_none():
    save_token("https://a.example", "tok")
    assert load_login("https://a.example") is None


def test_saving_a_token_without_a_login_forgets_the_previous_login():
    save_token("https://a.example", "one", login="ada")
    save_token("https://a.example", "two")
    assert load_login("https://a.example") is None


def test_delete_token_forgets_the_login_too():
    save_token("https://a.example", "tok", login="ada")
    save_token("https://b.example", "tok", login="bob")
    delete_token("https://a.example")
    assert load_login("https://a.example") is None
    assert load_login("https://b.example") == "bob"


def test_a_credentials_file_from_before_logins_still_loads(credentials_path):
    credentials_path.write_text('[servers]\n"https://a.example" = "legacy"\n')
    assert load_token("https://a.example") == "legacy"
    assert load_login("https://a.example") is None
    assert stored_servers() == ["https://a.example"]
    save_token("https://b.example", "new", login="bob")
    assert load_token("https://a.example") == "legacy"


def test_the_servers_table_keeps_plain_token_strings(credentials_path):
    """An older CLI reading the same file must still find its tokens."""
    import tomllib

    save_token("https://a.example", "tok", login="ada")
    data = tomllib.loads(credentials_path.read_text())
    assert data["servers"]["https://a.example"] == "tok"
