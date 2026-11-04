"""
Tests for the scaffolded `README.md` and the rule that reads it: the H1 is
the course name, the first paragraph the description. See
`dev/specs/to-do/init.md`, "`README.md` is the course name and description".
"""

from __future__ import annotations

from pathlib import Path

from codehood.push.resource import read_course_readme
from codehood.repo import write_repo

README = Path("README.md")


def test_scaffolded_readme_yields_a_description_and_no_resource(
    tmp_path, identity, server
):
    write_repo(tmp_path, identity, server)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")

    description, resource = read_course_readme(text, None, README)

    assert description
    assert resource is None
    # `init` has no --name flag, so it pre-fills the H1 with the discipline.
    assert text.startswith(f"# {identity.discipline}\n")


def test_missing_h1_still_yields_the_first_paragraph() -> None:
    description, resource = read_course_readme(
        "Just a paragraph, no heading.\n", None, README
    )
    assert description == "Just a paragraph, no heading."
    assert resource is None


def test_description_stops_at_next_heading() -> None:
    text = "# Name\n\nFirst paragraph.\n\n## Grading\n\nMore.\n"
    description, _ = read_course_readme(text, None, README)
    assert description == "First paragraph."


def test_description_is_only_the_first_paragraph() -> None:
    text = "# Name\n\nFirst line,\nsame paragraph.\n\nSecond paragraph.\n"
    description, resource = read_course_readme(text, None, README)
    assert description == "First line,\nsame paragraph."
    assert resource is not None
    assert resource.title == "Name"


def test_untitled_readme_resource_is_titled_readme() -> None:
    _, resource = read_course_readme("First.\n\nSecond.\n", None, README)
    assert resource is not None
    assert resource.title == "README"


def test_name_flag_becomes_the_h1(tmp_path):
    """The H1 is the course name init was given, not the discipline slug."""
    from codehood.models.repo import CourseIdentity, ServerConfig

    write_repo(
        tmp_path,
        CourseIdentity(discipline="cs101", instructor="ada", edition="2026-1"),
        ServerConfig(url="https://x.edu"),
        name="Introduction to Computer Science",
        git=False,
        examples=False,
    )
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# Introduction to Computer Science\n")
