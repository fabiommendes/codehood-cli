"""
Tests for the scaffolded `README.md` -- the H1 is the course name, the
prose under it the description. See `dev/specs/to-do/init.md`, "`README.md`
is the course name and description".
"""

from __future__ import annotations

from codehood.repo import read_course_name, write_repo


def test_readme_yields_a_name(tmp_path, identity, server):
    write_repo(tmp_path, identity, server)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")

    result = read_course_name(text)

    assert result is not None
    name, description = result
    # `init` has no --name flag (see the CLI report), so it pre-fills the
    # H1 with the discipline slug -- the value it was actually given.
    assert name == identity.discipline
    assert description


def test_missing_h1_reports_no_name() -> None:
    assert read_course_name("Just a paragraph, no heading.\n") is None


def test_description_stops_at_next_heading() -> None:
    text = "# Name\n\nFirst paragraph.\n\n## Grading\n\nIgnored.\n"
    name, description = read_course_name(text)
    assert name == "Name"
    assert description == "First paragraph."


def test_description_is_only_the_first_paragraph() -> None:
    text = "# Name\n\nFirst line,\nsame paragraph.\n\nSecond paragraph.\n"
    assert read_course_name(text) == ("Name", "First line,\nsame paragraph.")


def test_name_flag_becomes_the_h1(tmp_path):
    """The H1 is the course name init was given, not the discipline slug."""
    from codehood.models.repo import CourseIdentity, ServerConfig
    from codehood.repo import write_repo

    write_repo(
        tmp_path,
        CourseIdentity(discipline="cs101", instructor="ada", edition="2026-1"),
        ServerConfig(url="https://x.edu"),
        name="Introduction to Computer Science",
        git=False,
        examples=False,
    )
    parsed = read_course_name((tmp_path / "README.md").read_text())
    assert parsed is not None
    assert parsed[0] == "Introduction to Computer Science"
