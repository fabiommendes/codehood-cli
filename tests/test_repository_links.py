"""
Tests for repositories linked from `calendar.md` (batch 3): link
extraction, attaching and rewriting, the event `ref`, and `read_local_state`
scanning `repositories/`.
"""

from __future__ import annotations

import importlib
from dataclasses import replace
from pathlib import Path, PurePosixPath

import pytest

from codehood.push.calendar import Event
from codehood.push.errors import RepositoryError, ResourceLinkError
from codehood.push.links import (
    RepositoryLink,
    attach_repositories,
    extract_repository_links,
    rewrite_repository_links,
)
from codehood.push.repository import RepositoryEntry, RepositoryTree

push_module = importlib.import_module("codehood.cli.push")


def _entry(path: str) -> RepositoryEntry:
    return RepositoryEntry(
        path=path,
        mode="100644",
        sha256="0" * 64,
        git_sha="0" * 40,
        size=1,
        source=Path(path),
    )


def _tree(slug: str, *paths: str) -> RepositoryTree:
    return RepositoryTree(
        slug=slug,
        entries=tuple(_entry(path) for path in paths),
        tree_sha="0" * 40,
    )


def _event(description: str, title: str = "Lesson", week: int = 0) -> Event:
    return Event(week=week, time_slot="mon", title=title, description=description)


LAB1 = _tree("lab1", "a.py", "src/main.py", "src/pkg/mod.py")
LAB2 = _tree("lab2", "x.c")


#
# extract_repository_links
#
def test_extracts_a_repository_root_and_a_path():
    text = "[a](repositories/lab1) and [b](repositories/lab1/src/main.py)"
    assert extract_repository_links(text) == (
        RepositoryLink(slug="lab1"),
        RepositoryLink(slug="lab1", path=PurePosixPath("src/main.py")),
    )


def test_extraction_normalizes_and_ignores_other_links():
    text = (
        "[a](./repositories/lab1/) [b](https://x.org/repositories/lab1) "
        "[c](resources/w1/a.md) [d](repositories/lab1/a%20b.py#L3)"
    )
    assert extract_repository_links(text) == (
        RepositoryLink(slug="lab1"),
        RepositoryLink(slug="lab1", path=PurePosixPath("a b.py")),
    )


def test_extraction_skips_code():
    text = "`[a](repositories/lab1)`\n\n```\n[b](repositories/lab2)\n```\n"
    assert extract_repository_links(text) == ()


#
# attach_repositories
#
def test_a_link_to_a_file_attaches_the_repository():
    [event] = attach_repositories(
        [_event("[f](repositories/lab1/src/main.py)")], [LAB1, LAB2]
    )
    assert event.repositories == ("lab1",)


def test_a_link_to_the_root_attaches_the_repository():
    [event] = attach_repositories([_event("[r](repositories/lab1)")], [LAB1])
    assert event.repositories == ("lab1",)


def test_a_link_to_a_directory_that_holds_files_attaches_it():
    [event] = attach_repositories([_event("[d](repositories/lab1/src)")], [LAB1])
    assert event.repositories == ("lab1",)


def test_slugs_are_sorted_and_deduplicated():
    description = (
        "[b](repositories/lab2/x.c) [a](repositories/lab1) [c](repositories/lab2)"
    )
    [event] = attach_repositories([_event(description)], [LAB1, LAB2])
    assert event.repositories == ("lab1", "lab2")


def test_one_repository_may_be_linked_from_many_lessons():
    events = [
        _event("[r](repositories/lab1)", "One"),
        _event("[r](repositories/lab1/a.py)", "Two", 1),
    ]
    result = attach_repositories(events, [LAB1])
    assert [e.repositories for e in result] == [("lab1",), ("lab1",)]


def test_an_event_without_links_keeps_no_repositories_and_the_order():
    events = [_event("nothing", "One"), _event("[r](repositories/lab1)", "Two", 1)]
    result = attach_repositories(events, [LAB1])
    assert [e.title for e in result] == ["One", "Two"]
    assert result[0].repositories == ()
    assert result[0] == events[0]


def test_a_link_to_an_unknown_slug_is_an_error():
    with pytest.raises(ResourceLinkError, match="nope"):
        attach_repositories([_event("[r](repositories/nope)")], [LAB1])


def test_a_link_to_a_missing_path_is_an_error():
    with pytest.raises(ResourceLinkError, match=r"src/missing\.py"):
        attach_repositories([_event("[f](repositories/lab1/src/missing.py)")], [LAB1])


def test_a_link_to_a_directory_without_files_is_an_error():
    with pytest.raises(ResourceLinkError, match="docs"):
        attach_repositories([_event("[f](repositories/lab1/docs)")], [LAB1])


def test_a_prefix_of_a_file_name_is_not_a_directory():
    with pytest.raises(ResourceLinkError):
        attach_repositories([_event("[f](repositories/lab1/src/ma)")], [LAB1])


#
# rewrite_repository_links
#
def test_a_repository_root_link_points_to_the_server_page():
    [event] = rewrite_repository_links(
        [_event("See [lab](repositories/lab1).")], "cs101", "ada_2026-1"
    )
    assert event.description == "See [lab](/cs101/ada_2026-1/repositories/lab1)."


def test_a_path_link_keeps_the_path_and_the_fragment():
    [event] = rewrite_repository_links(
        [_event("[f](./repositories/lab1/src/main.py#L3)")], "cs101", "ada_2026-1"
    )
    assert event.description == (
        "[f](/cs101/ada_2026-1/repositories/lab1/src/main.py#L3)"
    )


def test_other_links_are_left_untouched():
    text = "[x](https://example.org) [y](resources/w1/a.md) [z](#top)"
    [event] = rewrite_repository_links([_event(text)], "cs101", "ada_2026-1")
    assert event.description == text


def test_rewriting_keeps_the_event_otherwise_intact():
    original = _event("[lab](repositories/lab1)")
    [event] = rewrite_repository_links([original], "cs101", "ada_2026-1")
    assert replace(event, description=original.description) == original


#
# Event.ref
#
def test_the_ref_of_an_event_without_repositories_is_the_old_digest():
    import hashlib

    event = _event("Welcome.", "Intro")
    assert event.ref == hashlib.md5(b"Intro#Welcome.").hexdigest()


def test_linking_a_repository_changes_the_ref():
    plain = _event("Welcome.", "Intro")
    linked = replace(plain, repositories=("lab1",))
    assert linked.ref != plain.ref


def test_different_repositories_give_different_refs():
    base = _event("Welcome.", "Intro")
    assert (
        replace(base, repositories=("lab1",)).ref
        != replace(base, repositories=("lab2",)).ref
    )


def test_the_ref_is_stable_for_the_same_repositories():
    base = _event("Welcome.", "Intro")
    assert (
        replace(base, repositories=("lab1", "lab2")).ref
        == replace(base, repositories=("lab1", "lab2")).ref
    )


#
# read_local_state
#
TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    '\n[server]\nurl = "http://localhost:4321"\n'
)


def _calendar(first: str) -> str:
    return f"""---
start: 2026-01-05
end:   2026-06-01
days:
  - Mon 14:00 2h, Lecture
holidays: []
---

## First lesson

{first}
"""


def _course(root: Path, calendar: str, files: dict[str, str]) -> Path:
    (root / "codehood.toml").write_text(TOML, encoding="utf-8")
    (root / "README.md").write_text("# CS101\n\nA description.\n", encoding="utf-8")
    (root / "calendar.md").write_text(calendar, encoding="utf-8")
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def test_read_local_state_scans_repositories(tmp_path):
    root = _course(
        tmp_path,
        _calendar("Nothing."),
        {"repositories/lab1/a.py": "x\n", "repositories/lab2/b.py": "y\n"},
    )
    local = push_module.read_local_state(root)
    assert [tree.slug for tree in local.repositories] == ["lab1", "lab2"]


def test_read_local_state_links_and_rewrites_repository_links(tmp_path):
    root = _course(
        tmp_path,
        _calendar("Open [the lab](repositories/lab1/a.py)."),
        {"repositories/lab1/a.py": "x\n"},
    )
    [event] = push_module.read_local_state(root).events
    assert event.repositories == ("lab1",)
    assert event.description == (
        "Open [the lab](/cs101/ada_2026-1/repositories/lab1/a.py)."
    )


def test_read_local_state_rejects_a_link_to_a_missing_repository(tmp_path):
    root = _course(
        tmp_path,
        _calendar("[x](repositories/ghost)"),
        {"repositories/lab1/a.py": "x\n"},
    )
    with pytest.raises(ResourceLinkError, match="ghost"):
        push_module.read_local_state(root)


def test_read_local_state_rejects_a_loose_file_in_repositories(tmp_path):
    root = _course(tmp_path, _calendar("Nothing."), {"repositories/notes.txt": "x"})
    with pytest.raises(RepositoryError, match=r"notes\.txt"):
        push_module.read_local_state(root)


def test_read_local_state_applies_push_exclude_to_repositories(tmp_path):
    root = _course(
        tmp_path,
        _calendar("Nothing."),
        {"repositories/lab1/a.py": "x\n", "repositories/lab1/secret.txt": "s\n"},
    )
    toml = root / "codehood.toml"
    toml.write_text(
        TOML + '\n[push]\nexclude = ["repositories/lab1/secret.txt"]\n',
        encoding="utf-8",
    )
    [tree] = push_module.read_local_state(root).repositories
    assert [entry.path for entry in tree.entries] == ["a.py"]


def test_a_course_without_repositories_has_none(tmp_path):
    root = _course(tmp_path, _calendar("Nothing."), {})
    local = push_module.read_local_state(root)
    assert local.repositories == ()
    assert all(event.repositories == () for event in local.events)
