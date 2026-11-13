"""
Tests for how `exams/` is tracked and pushed from the command line: one file
type, a recursive walk, and the lines `ch push` prints for an exam.
"""

from __future__ import annotations

import importlib

from typer.testing import CliRunner

from codehood.push.unconsumed import consumed_paths
from codehood.repo.diff import FileType
from codehood.repo.file_tracker import scan_files

push_module = importlib.import_module("codehood.cli.push")
runner = CliRunner()


def _write(root, relative: str, text: str = "# [x] X\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_every_mdq_file_under_exams_is_one_exam_whatever_its_directory(tmp_path):
    _write(tmp_path, "exams/a.md")
    _write(tmp_path, "exams/published/b.mdq")
    _write(tmp_path, "exams/_draft/deep/c.mdq.md")
    _write(tmp_path, "exams/notes.txt", "x")

    files = {
        f.name: f
        for f in scan_files(tmp_path, [])
        if f.name.startswith(("a", "p", "_", "n"))
    }

    exams = {name for name, f in files.items() if f.type is FileType.EXAM}
    assert exams == {"a.md", "published/b.mdq", "_draft/deep/c.mdq.md"}
    assert files["notes.txt"].type is FileType.WARNING
    assert files["a.md"].path.as_posix() == "exams/a.md"


def test_an_exam_file_counts_as_read_by_the_push(tmp_path):
    _write(tmp_path, "exams/part1/a.md")

    consumed = consumed_paths(scan_files(tmp_path, []))

    assert "exams/part1/a.md" in consumed


def test_every_exam_of_the_example_courses_resolves():
    from pathlib import Path

    from codehood.push.exam import ExamFile, scan_exams
    from codehood.push.exclude import scan_excluded
    from codehood.push.question import scan_questions

    examples = Path(__file__).parent / "examples"
    found = {}
    for root in sorted(examples.iterdir()):
        if not (root / "exams").is_dir():
            continue
        questions = list(scan_questions(root))
        for exam in scan_exams(root, questions, list(scan_excluded(root, []))):
            found[f"{root.name}/{exam.slug}"] = exam

    assert found
    assert all(isinstance(e, ExamFile) for e in found.values()), found
    assert found["ada-full/final"].status == "DRAFT"
    assert found["ada-full/warmup"].type == "PRACTICE"
    assert found["ada-full/warmup"].status == "SCHEDULED"
