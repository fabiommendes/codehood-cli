"""
Tests for `read_local_state` and the pure README rule it relies on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codehood.cli.push import read_local_state
from codehood.models.repo import CourseKey, RepoConfig
from codehood.push.errors import SlugCollisionError
from codehood.push.resource import MdData, read_course_readme
from codehood.repo import write_repo


@pytest.fixture
def repo(tmp_path: Path, identity, server) -> Path:
    write_repo(tmp_path, identity, server, git=False, examples=False)
    return tmp_path


def _state(repo: Path):
    return read_local_state(repo, RepoConfig.open(repo))


def _readme(repo: Path, text: str) -> None:
    (repo / "README.md").write_text(text, encoding="utf-8")


def _readme_resources(local):
    return [r for r in local.resources if r.slug == "readme"]


# CourseKey


def test_course_key_slug_and_urls():
    key = CourseKey("cs101", "ada", "2026-1")
    assert key.slug == "ada_2026-1"
    assert key.url("resources", "notes") == "/cs101/ada_2026-1/resources/notes"
    assert key.url("resources") == "/cs101/ada_2026-1/resources"


def test_local_state_carries_the_course_key(repo):
    local = _state(repo)
    assert local.key == CourseKey("cs101", "ada", "2026-1")
    assert local.course == "ada_2026-1"


# read_local_state: README rules


def test_h1_and_one_paragraph_is_only_the_description(repo):
    _readme(repo, "# Name\n\nOnly this.\n")
    local = _state(repo)
    assert local.description == "Only this."
    assert _readme_resources(local) == []


def test_one_paragraph_without_h1_is_the_description(repo):
    _readme(repo, "Only this.\n")
    local = _state(repo)
    assert local.description == "Only this."
    assert _readme_resources(local) == []


def test_rest_of_the_readme_becomes_a_resource_without_the_h1(repo):
    _readme(repo, "# Name\n\nIntro.\n\n## Grading\n\nExams.\n")
    local = _state(repo)
    assert local.description == "Intro."
    [resource] = _readme_resources(local)
    assert resource.title == "Name"
    assert isinstance(resource.data, MdData)
    assert resource.data.content == "Intro.\n\n## Grading\n\nExams.\n"


def test_description_override_makes_the_whole_readme_a_resource(repo):
    config = (repo / "codehood.toml").read_text(encoding="utf-8")
    (repo / "codehood.toml").write_text(
        config.replace("[course]\n", '[course]\ndescription = "Custom."\n', 1),
        encoding="utf-8",
    )
    _readme(repo, "# Name\n\nIntro.\n")
    local = _state(repo)
    assert local.description == "Custom."
    [resource] = _readme_resources(local)
    assert resource.data.content == "Intro.\n"


def test_resource_named_readme_collides_with_the_course_readme(repo):
    _readme(repo, "# Name\n\nIntro.\n\nMore.\n")
    (repo / "resources").mkdir(exist_ok=True)
    (repo / "resources" / "readme.md").write_text("# Other\n", encoding="utf-8")
    with pytest.raises(SlugCollisionError):
        _state(repo)


def test_calendar_warnings_are_returned_not_printed(repo, capsys):
    _state(repo)
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


# read_course_readme


def test_read_course_readme_is_pure_on_text():
    path = Path("README.md")
    description, resource = read_course_readme("# T\n\nP.\n", None, path)
    assert description == "P."
    assert resource is None
    description, resource = read_course_readme("", None, path)
    assert (description, resource) == ("", None)
