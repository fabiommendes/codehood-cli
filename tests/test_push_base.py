"""
The base store: round-trip, atomic writes and recovery from bad files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from codehood.push import base as base_module
from codehood.push.base import (
    COLLECTIONS,
    FORMAT_VERSION,
    BaseEntry,
    BaseState,
    base_dir,
    decode_collection,
    encode_collection,
    load_base,
    save_base,
)

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=8),
    lambda inner: (
        st.lists(inner, max_size=3)
        | st.dictionaries(st.text(max_size=5), inner, max_size=3)
    ),
    max_leaves=8,
)
entries = st.builds(
    BaseEntry,
    payload=st.dictionaries(st.text(max_size=5), json_values, max_size=4),
    rev=st.none() | st.text(max_size=12),
    updated_at=st.none() | st.text(max_size=30),
)
collections = st.dictionaries(st.text(min_size=1, max_size=8), entries, max_size=3)
states = st.builds(BaseState, **{name: collections for name in COLLECTIONS})


def sample(rev: str = "r1") -> BaseState:
    entry = BaseEntry({"title": "A"}, rev, "2026-01-01T00:00:00.000Z")
    return BaseState(course={"c": entry}, questions={"q1": entry})


@given(states)
def test_pure_round_trip(state):
    for name in COLLECTIONS:
        entries_, warning = decode_collection(
            encode_collection(getattr(state, name)), name
        )
        assert warning is None
        assert entries_ == getattr(state, name)


def test_disk_round_trip(tmp_path):
    state = sample()
    save_base(tmp_path, state)
    assert load_base(tmp_path) == state
    assert load_base(tmp_path).warnings == ()


@given(states)
def test_disk_round_trip_property(state):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        save_base(Path(tmp), state)
        assert load_base(Path(tmp)) == state


def test_missing_base_is_empty_and_silent(tmp_path):
    state = load_base(tmp_path)
    assert state == BaseState()
    assert state.warnings == ()


def test_save_leaves_no_temporaries(tmp_path):
    save_base(tmp_path, sample())
    assert sorted(p.suffix for p in base_dir(tmp_path).iterdir()) == [".json"] * len(
        COLLECTIONS
    )


@pytest.mark.parametrize(
    "content",
    [
        "",
        "{not json",
        "[]",
        '{"version": 1}',
        '{"version": 1, "entries": []}',
        '{"version": 1, "entries": {"k": {"payload": 3}}}',
        '{"version": 1, "entries": {"k": {"payload": {}, "rev": 3}}}',
        json.dumps({"version": FORMAT_VERSION + 1, "entries": {}}),
    ],
)
def test_bad_file_is_absent_with_warning(tmp_path, content):
    save_base(tmp_path, sample())
    (base_dir(tmp_path) / "course.json").write_text(content)
    state = load_base(tmp_path)
    assert state.course == {}
    assert state.questions == sample().questions
    assert len(state.warnings) == 1
    assert "course" in state.warnings[0]


def test_unreadable_file_is_absent_with_warning(tmp_path):
    save_base(tmp_path, sample())
    (base_dir(tmp_path) / "course.json").write_bytes(b"\xff\xfe\x00")
    state = load_base(tmp_path)
    assert state.course == {}
    assert len(state.warnings) == 1


def test_crash_before_rename_keeps_previous_base(tmp_path, monkeypatch):
    old, new = sample("old"), sample("new")
    save_base(tmp_path, old)

    def die(*_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "replace", die)
    with pytest.raises(KeyboardInterrupt):
        save_base(tmp_path, new)
    monkeypatch.undo()
    assert load_base(tmp_path) == old
    assert load_base(tmp_path).warnings == ()


def test_truncated_temporary_is_never_read(tmp_path, monkeypatch):
    """
    A process killed mid-write leaves a truncated temporary beside the real
    files. Reading ignores it and returns the previous base.
    """
    old = sample("old")
    save_base(tmp_path, old)
    real_write = base_module.write_atomic

    def torn(path: Path, text: str) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text[: len(text) // 2])
        raise KeyboardInterrupt

    monkeypatch.setattr(base_module, "write_atomic", torn)
    with pytest.raises(KeyboardInterrupt):
        save_base(tmp_path, sample("new"))
    monkeypatch.setattr(base_module, "write_atomic", real_write)
    assert load_base(tmp_path) == old
    assert load_base(tmp_path).warnings == ()


def test_crash_between_collections_gives_old_or_new_per_file(tmp_path, monkeypatch):
    old, new = sample("old"), sample("new")
    save_base(tmp_path, old)
    real = os.replace
    calls = []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 2:
            raise KeyboardInterrupt
        real(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    with pytest.raises(KeyboardInterrupt):
        save_base(tmp_path, new)
    monkeypatch.undo()
    loaded = load_base(tmp_path)
    assert loaded.warnings == ()
    for name in COLLECTIONS:
        assert getattr(loaded, name) in (getattr(old, name), getattr(new, name))


def test_saving_the_base_keeps_it_out_of_git_in_a_repository_without_scaffold(
    tmp_path: Path,
):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    save_base(tmp_path, sample())

    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ".local" not in status
    assert (base_dir(tmp_path).parent / ".gitignore").read_text() == "*\n"


def test_saving_the_base_keeps_an_existing_inner_gitignore(tmp_path: Path):
    ignore = base_dir(tmp_path).parent / ".gitignore"
    ignore.parent.mkdir(parents=True)
    ignore.write_text("*\n# mine\n", encoding="utf-8")

    save_base(tmp_path, sample())

    assert ignore.read_text() == "*\n# mine\n"
