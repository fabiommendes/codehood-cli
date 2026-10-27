"""
Tests for `codehood_cli.repo.write_repo` -- the pure scaffolding logic
behind `codehood init`. See `dev/specs/to-do/init.md`, "Proving it works".
"""

from __future__ import annotations

import subprocess

import pytest

from codehood.repo import IdentityConflictError, write_repo

GOLDEN_PATHS = {
    "codehood.toml",
    "README.md",
    "calendar.md",
    ".gitignore",
    "questions",
    "exams",
    "resources",
    "repositories",
    ".codehood",
    "questions/example.md",
    "exams/example.md",
    ".git",
}


def test_golden_layout(tmp_path, identity, server):
    """
    A fresh `init` creates exactly the layout in the spec's "The layout" --
    no more, no less.
    """
    reports = write_repo(tmp_path, identity, server)
    created = {str(report.path) for report in reports if report.status == "created"}
    assert created == GOLDEN_PATHS


def test_no_examples_skips_the_pair(tmp_path, identity, server):
    reports = write_repo(tmp_path, identity, server, examples=False)
    created = {str(report.path) for report in reports if report.status == "created"}
    assert created == GOLDEN_PATHS - {"questions/example.md", "exams/example.md"}


def test_idempotence(tmp_path, identity, server):
    """
    Running `init` twice creates nothing new and changes no file's bytes.
    A third run after a hand-edit preserves the edit.
    """
    first = write_repo(tmp_path, identity, server)
    files_before = {
        report.path: (tmp_path / report.path).read_bytes()
        for report in first
        if (tmp_path / report.path).is_file()
    }

    second = write_repo(tmp_path, identity, server)
    assert all(report.status == "exists" for report in second)
    for path, contents in files_before.items():
        assert (tmp_path / path).read_bytes() == contents

    readme = tmp_path / "README.md"
    edited = readme.read_text(encoding="utf-8") + "\nHand-edited paragraph.\n"
    readme.write_text(edited, encoding="utf-8")

    third = write_repo(tmp_path, identity, server)
    assert all(report.status == "exists" for report in third)
    assert readme.read_text(encoding="utf-8") == edited


def test_conflicting_identity_is_refused(tmp_path, identity, server):
    write_repo(tmp_path, identity, server)
    other = identity.model_copy(update={"discipline": "cs102"})
    with pytest.raises(IdentityConflictError, match="discipline"):
        write_repo(tmp_path, other, server)


def test_git_init_creates_dot_git(tmp_path, identity, server):
    write_repo(tmp_path, identity, server)
    assert (tmp_path / ".git").is_dir()


def test_no_git_flag_skips_dot_git(tmp_path, identity, server):
    write_repo(tmp_path, identity, server, git=False)
    assert not (tmp_path / ".git").exists()


def test_inside_existing_work_tree_creates_no_nested_repo(tmp_path, identity, server):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    nested = tmp_path / "nested"
    nested.mkdir()

    write_repo(nested, identity, server)

    assert not (nested / ".git").exists()
