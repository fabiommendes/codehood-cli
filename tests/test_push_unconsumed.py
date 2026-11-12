"""
Repository files `ch push` leaves unread are listed, never fatal.
"""

from __future__ import annotations

from codehood.push.unconsumed import find_unconsumed, list_files


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
