"""
Repository files `ch push` leaves unread are listed, never fatal.
"""

from __future__ import annotations

import subprocess

from codehood.globs import is_excluded
from codehood.push.exclude import scan_excluded
from codehood.push.unconsumed import (
    excluded_paths,
    find_unconsumed,
    ignore_patterns,
    list_files,
    read_ignore,
)
from codehood.repo.file_tracker import scan_files


def _write(root, relative: str, text: str = "x\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_find_unconsumed_is_pure_and_sorted():
    paths = [
        "z.txt",
        "codehood.toml",
        "exams/exam/midterm.md",
        "questions/a.md",
        "questions/notes.txt",
        "resources/r.md",
        "repositories/lab/main.py",
        "resources/hidden.md",
        "build/out.bin",
    ]
    result = find_unconsumed(
        paths,
        consumed={"codehood.toml", "questions/a.md", "resources/r.md"},
        excluded={"resources/hidden.md"},
        gitignore=["build/"],
    )
    assert result == (
        "exams/exam/midterm.md",
        "questions/notes.txt",
        "z.txt",
    )


def test_list_files_skips_dot_dirs_and_returns_gitignore(tmp_path):
    _write(tmp_path, ".gitignore", "*.log\ntmp/\n")
    _write(tmp_path, ".git/config")
    _write(tmp_path, ".codehood/state")
    _write(tmp_path, ".local/codehood/base/course.json")
    _write(tmp_path, "a.log")
    _write(tmp_path, "tmp/b.txt")
    _write(tmp_path, "kept/c.txt")
    paths, gitignore = list_files(tmp_path)
    assert sorted(paths) == [".gitignore", "a.log", "kept/c.txt", "tmp/b.txt"]
    assert "*.log" in gitignore
    assert find_unconsumed(
        paths, consumed=set(), excluded=set(), gitignore=gitignore
    ) == ("kept/c.txt",)


def _git_init(root) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


def test_list_files_in_a_git_repo_follows_the_global_and_info_excludes(
    tmp_path, monkeypatch
):
    global_ignore = tmp_path / "global-ignore"
    global_ignore.write_text("*.secret\n", encoding="utf-8")
    global_config = tmp_path / "gitconfig"
    global_config.write_text(
        f"[core]\n\texcludesFile = {global_ignore}\n", encoding="utf-8"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    course = tmp_path / "course"
    course.mkdir()
    _git_init(course)
    (course / ".git" / "info" / "exclude").write_text("local.txt\n", encoding="utf-8")
    _write(course, ".gitignore", "*.log\n")
    _write(course, "sub/.gitignore", "inner.txt\n")
    for name in (
        "a.secret",
        "local.txt",
        "a.log",
        "sub/inner.txt",
        "sub/kept.txt",
        "new.txt",
        ".local/codehood/base.json",
    ):
        _write(course, name)
    paths, lines = list_files(course)
    assert lines == []
    assert paths == [".gitignore", "new.txt", "sub/.gitignore", "sub/kept.txt"]


def test_list_files_in_a_git_repo_keeps_tracked_and_drops_deleted(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "none"))
    course = tmp_path / "course"
    course.mkdir()
    _git_init(course)
    _write(course, "tracked.txt")
    _write(course, "gone.txt")
    subprocess.run(["git", "add", "."], cwd=course, check=True)
    (course / "gone.txt").unlink()
    paths, _ = list_files(course)
    assert paths == ["tracked.txt"]


def test_codehoodignore_drops_paths_from_the_report(tmp_path):
    _write(tmp_path, ".codehoodignore", "chalk.toml\np1/\n")
    for name in ("chalk.toml", "p1/conf.yaml", "p1/grades.csv", "other.txt"):
        _write(tmp_path, name)
    paths, gitignore = list_files(tmp_path)
    result = find_unconsumed(
        paths,
        consumed=set(),
        excluded=set(),
        gitignore=gitignore,
        codehoodignore=read_ignore(tmp_path),
    )
    assert result == ("other.txt",)


def test_codehoodignore_under_pushed_trees_is_excluded_and_protected(tmp_path):
    _write(tmp_path, ".codehoodignore", "questions/wip/\nresources/*.tmp\n")
    _write(tmp_path, "questions/wip/a.md", "---\nid: wip-a\n---\nbody\n")
    _write(tmp_path, "questions/ok.md", "---\nid: ok\n---\nbody\n")
    _write(tmp_path, "resources/x.tmp")
    _write(tmp_path, "resources/y.pdf")
    patterns = ignore_patterns(tmp_path, read_ignore(tmp_path))
    assert sorted(patterns) == ["questions/wip/a.md", "resources/x.tmp"]
    excluded = {file.path for file in scan_excluded(tmp_path, patterns)}
    assert excluded == {"questions/wip/a.md", "resources/x.tmp"}
    tracked = list(scan_files(tmp_path, patterns))
    assert excluded_paths(tracked) == {"questions/wip/a.md", "resources/x.tmp"}


def test_ignore_patterns_escape_glob_characters(tmp_path):
    _write(tmp_path, ".codehoodignore", "resources/a\\*b.md\n")
    _write(tmp_path, "resources/a*b.md")
    _write(tmp_path, "resources/aXb.md")
    patterns = ignore_patterns(tmp_path, read_ignore(tmp_path))
    assert is_excluded("resources/a*b.md", patterns)
    assert not is_excluded("resources/aXb.md", patterns)


def test_outside_git_only_the_root_gitignore_applies(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "none"))
    _write(tmp_path, ".gitignore", "*.log\n")
    _write(tmp_path, "sub/.gitignore", "inner.txt\n")
    _write(tmp_path, "a.log")
    _write(tmp_path, "sub/inner.txt")
    paths, gitignore = list_files(tmp_path)
    result = find_unconsumed(paths, consumed=set(), excluded=set(), gitignore=gitignore)
    assert result == ("sub/.gitignore", "sub/inner.txt")
