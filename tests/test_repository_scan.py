"""
Tests for `codehood.push.repository` (batch 1): the scan of `repositories/`
and the local git tree sha, plus the `repositories/` folder `ch init` makes.

The expected shas come from two independent sources: the shared vector
table (`fixtures/git-vectors.json`) and the real `git` binary.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from codehood.push.errors import RepositoryError
from codehood.push.repository import (
    MAX_FILE_BYTES,
    RepositoryEntry,
    RepositoryTree,
    batch_entries,
    blob_sha,
    file_mode,
    scan_repositories,
    tree_sha,
)

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures" / "git-vectors.json").read_text(
        encoding="utf-8"
    )
)

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="needs POSIX modes")


def _bytes(item: dict[str, Any]) -> bytes:
    if "contentBase64" in item:
        return base64.b64decode(item["contentBase64"])
    return item["content"].encode("utf-8")


def _write(root: Path, files: dict[str, bytes | str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)


def _scan(root: Path, exclude: tuple[str, ...] = ()) -> list[RepositoryTree]:
    return list(scan_repositories(root, exclude))


def _one(root: Path, exclude: tuple[str, ...] = ()) -> RepositoryTree:
    [tree] = _scan(root, exclude)
    return tree


def _paths(tree: RepositoryTree) -> list[str]:
    return [entry.path for entry in tree.entries]


def _entry(path: str, size: int = 1, mode: str = "100644") -> RepositoryEntry:
    return RepositoryEntry(
        path=path,
        mode=mode,  # type: ignore[arg-type]
        sha256="0" * 64,
        git_sha="0" * 40,
        size=size,
        source=Path(path),
    )


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _git_tree_sha(folder: Path) -> str:
    """The root tree git builds from a copy of `folder`, `.gitignore` included."""
    oracle = folder.parent / f"{folder.name}-oracle"
    shutil.copytree(folder, oracle)
    _git(oracle, "init", "-q")
    _git(oracle, "add", "-A")
    return _git(oracle, "write-tree")


#
# blob_sha
#
@pytest.mark.parametrize("blob", VECTORS["blobs"], ids=lambda b: b["name"])
def test_blob_sha_matches_the_vectors(blob):
    assert blob_sha(_bytes(blob)) == blob["sha"]


@pytest.mark.parametrize("blob", VECTORS["blobs"], ids=lambda b: b["name"])
def test_blob_sha_matches_git_hash_object(blob, tmp_path):
    (tmp_path / "f").write_bytes(_bytes(blob))
    assert blob_sha(_bytes(blob)) == _git(tmp_path, "hash-object", "f")


#
# tree_sha
#
def _vector_entries(tree: dict[str, Any]) -> list[RepositoryEntry]:
    return [
        RepositoryEntry(
            path=file["path"],
            mode=file["mode"],
            sha256=hashlib.sha256(_bytes(file)).hexdigest(),
            git_sha=file["sha"],
            size=len(_bytes(file)),
            source=Path(file["path"]),
        )
        for file in tree["files"]
    ]


@pytest.mark.parametrize("tree", VECTORS["trees"], ids=lambda t: t["name"])
def test_tree_sha_matches_the_vectors(tree):
    assert tree_sha(_vector_entries(tree)) == tree["rootSha"]


@pytest.mark.parametrize("tree", VECTORS["trees"], ids=lambda t: t["name"])
def test_tree_sha_ignores_the_order_of_entries(tree):
    entries = _vector_entries(tree)
    assert tree_sha(entries[::-1]) == tree["rootSha"]


def test_tree_sha_of_nothing_is_refused():
    with pytest.raises(ValueError):
        tree_sha([])


def test_tree_sha_refuses_a_path_that_is_a_file_and_a_directory():
    with pytest.raises(ValueError):
        tree_sha([_entry("a"), _entry("a/b")])


#
# scan_repositories: shape
#
def test_a_missing_repositories_folder_yields_nothing(tmp_path):
    assert _scan(tmp_path) == []


def test_each_subfolder_is_a_repository_sorted_by_slug(tmp_path):
    _write(
        tmp_path / "repositories",
        {"lab2/a.txt": "2", "lab1/a.txt": "1", "lab10/a.txt": "3"},
    )
    assert [tree.slug for tree in _scan(tmp_path)] == ["lab1", "lab10", "lab2"]


def test_an_entry_describes_its_file(tmp_path):
    _write(tmp_path / "repositories" / "lab1", {"src/a.py": "hello\n"})
    tree = _one(tmp_path)
    [entry] = tree.entries
    assert entry.path == "src/a.py"
    assert entry.mode == "100644"
    assert entry.size == 6
    assert entry.sha256 == hashlib.sha256(b"hello\n").hexdigest()
    assert entry.git_sha == "ce013625030ba8dba906f756967f9e9ca394464a"
    assert entry.source == tmp_path / "repositories" / "lab1" / "src" / "a.py"
    assert tree.size == 6


def test_entries_are_sorted_by_path_in_byte_order(tmp_path):
    _write(
        tmp_path / "repositories" / "lab1",
        {"b.txt": "b", "a/z.txt": "z", "a-b.txt": "x", "a.txt": "a", "B.txt": "B"},
    )
    assert _paths(_one(tmp_path)) == [
        "B.txt",
        "a-b.txt",
        "a.txt",
        "a/z.txt",
        "b.txt",
    ]


def test_tree_size_sums_the_files(tmp_path):
    _write(tmp_path / "repositories" / "lab1", {"a": "123", "d/b": "45"})
    assert _one(tmp_path).size == 5


@pytest.mark.parametrize("tree", VECTORS["trees"], ids=lambda t: t["name"])
def test_scanned_tree_sha_matches_the_vectors(tree, tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    for file in tree["files"]:
        _write(folder, {file["path"]: _bytes(file)})
        (folder / file["path"]).chmod(0o755 if file["mode"] == "100755" else 0o644)
    assert _one(tmp_path).tree_sha == tree["rootSha"]


#
# scan_repositories: git as the oracle
#
@posix_only
def test_tree_sha_matches_real_git_on_a_mixed_tree(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(
        folder,
        {
            "README.md": "# Lab\n",
            "a.txt": "a",
            "a/b.txt": "b",
            "a-b/c.txt": "c",
            "src/pkg/mod.py": "x = 1\n",
            "spaced name/é ü.txt": "ação\n",
            "data.bin": bytes([0, 1, 2, 255, 254]),
            "empty.txt": "",
        },
    )
    (folder / "src" / "run.sh").write_text("#!/bin/sh\n")
    (folder / "src" / "run.sh").chmod(0o755)
    (folder / "hollow" / "deeper").mkdir(parents=True)
    assert _one(tmp_path).tree_sha == _git_tree_sha(folder)


@posix_only
def test_tree_sha_matches_real_git_with_nested_gitignores_and_negation(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(
        folder,
        {
            ".gitignore": "*.log\nbuild/\n",
            "keep.py": "k",
            "debug.log": "noise",
            "build/out.o": "o",
            "sub/.gitignore": "*.tmp\n!important.log\n",
            "sub/a.tmp": "t",
            "sub/important.log": "kept",
            "sub/other.log": "dropped",
            "sub/deeper/.gitignore": "secret.txt\n",
            "sub/deeper/secret.txt": "s",
            "sub/deeper/open.txt": "o",
        },
    )
    assert _one(tmp_path).tree_sha == _git_tree_sha(folder)


#
# scan_repositories: .gitignore
#
def test_nested_gitignore_with_negation_is_respected(tmp_path):
    _write(
        tmp_path / "repositories" / "lab1",
        {
            ".gitignore": "*.log\n",
            "sub/.gitignore": "!important.log\n*.tmp\n",
            "sub/important.log": "x",
            "sub/other.log": "x",
            "sub/a.tmp": "x",
            "top.log": "x",
            "ok.txt": "x",
        },
    )
    assert _paths(_one(tmp_path)) == [
        ".gitignore",
        "ok.txt",
        "sub/.gitignore",
        "sub/important.log",
    ]


def test_the_gitignore_files_are_published(tmp_path):
    _write(
        tmp_path / "repositories" / "lab1",
        {".gitignore": "*.log\n", "sub/.gitignore": "*.tmp\n", "a.txt": "a"},
    )
    assert ".gitignore" in _paths(_one(tmp_path))
    assert "sub/.gitignore" in _paths(_one(tmp_path))


def test_a_nested_gitignore_does_not_leak_to_siblings(tmp_path):
    _write(
        tmp_path / "repositories" / "lab1",
        {"sub/.gitignore": "*.tmp\n", "sub/a.tmp": "x", "other/a.tmp": "x"},
    )
    assert _paths(_one(tmp_path)) == ["other/a.tmp", "sub/.gitignore"]


def test_the_course_root_gitignore_does_not_apply(tmp_path):
    _write(tmp_path, {".gitignore": "*.log\nrepositories/\n"})
    _write(tmp_path / "repositories" / "lab1", {"debug.log": "x", "a.txt": "a"})
    assert _paths(_one(tmp_path)) == ["a.txt", "debug.log"]


def test_a_gitignore_of_one_repository_does_not_apply_to_another(tmp_path):
    _write(
        tmp_path / "repositories",
        {"one/.gitignore": "*.log\n", "one/a": "a", "two/x.log": "x"},
    )
    trees = {tree.slug: _paths(tree) for tree in _scan(tmp_path)}
    assert trees["two"] == ["x.log"]


#
# scan_repositories: exclude, .git, empty dirs
#
def test_push_exclude_patterns_apply_under_repositories(tmp_path):
    _write(
        tmp_path / "repositories" / "lab1",
        {"secret.txt": "s", "docs/notes.txt": "n", "a.txt": "a"},
    )
    tree = _one(tmp_path, ("repositories/lab1/secret.txt",))
    assert _paths(tree) == ["a.txt", "docs/notes.txt"]


def test_push_exclude_patterns_do_not_hit_other_repositories(tmp_path):
    _write(
        tmp_path / "repositories",
        {"one/secret.txt": "s", "one/a": "a", "two/secret.txt": "s"},
    )
    trees = {
        tree.slug: _paths(tree)
        for tree in _scan(tmp_path, ("repositories/one/secret.txt",))
    }
    assert trees == {"one": ["a"], "two": ["secret.txt"]}


def test_dot_git_directories_are_skipped_at_every_level(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(
        folder,
        {
            "a.txt": "a",
            ".git/config": "[core]",
            ".git/objects/ab": "x",
            "vendor/lib/.git/HEAD": "ref",
            "vendor/lib/code.c": "c",
        },
    )
    assert _paths(_one(tmp_path)) == ["a.txt", "vendor/lib/code.c"]


def test_the_tree_sha_ignores_dot_git(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"a.txt": "a"})
    plain = _one(tmp_path).tree_sha
    _write(folder, {".git/HEAD": "ref: refs/heads/main\n"})
    assert _one(tmp_path).tree_sha == plain


def test_empty_directories_are_omitted(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"a.txt": "a"})
    (folder / "empty" / "nested").mkdir(parents=True)
    with_empty = _one(tmp_path)
    assert _paths(with_empty) == ["a.txt"]
    shutil.rmtree(folder / "empty")
    assert _one(tmp_path).tree_sha == with_empty.tree_sha


def test_a_directory_left_empty_by_gitignore_vanishes(tmp_path):
    _write(
        tmp_path / "repositories" / "lab1",
        {".gitignore": "*.tmp\n", "a.txt": "a", "cache/x.tmp": "x"},
    )
    assert _paths(_one(tmp_path)) == [".gitignore", "a.txt"]


#
# scan_repositories: modes
#
@posix_only
def test_the_owner_execute_bit_makes_100755(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"run.sh": "#!/bin/sh\n", "plain.txt": "x"})
    (folder / "run.sh").chmod(0o755)
    (folder / "plain.txt").chmod(0o644)
    modes = {entry.path: entry.mode for entry in _one(tmp_path).entries}
    assert modes == {"run.sh": "100755", "plain.txt": "100644"}


@posix_only
def test_only_the_owner_bit_counts(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"group.sh": "x", "owner.sh": "x"})
    (folder / "group.sh").chmod(0o654)
    (folder / "owner.sh").chmod(0o744)
    modes = {entry.path: entry.mode for entry in _one(tmp_path).entries}
    assert modes == {"group.sh": "100644", "owner.sh": "100755"}


@posix_only
def test_file_mode_reads_the_owner_execute_bit(tmp_path):
    exe = tmp_path / "exe"
    exe.write_text("x")
    exe.chmod(0o700)
    plain = tmp_path / "plain"
    plain.write_text("x")
    plain.chmod(0o600)
    assert (file_mode(exe), file_mode(plain)) == ("100755", "100644")


@posix_only
def test_the_mode_changes_the_tree_sha(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"run.sh": "x"})
    (folder / "run.sh").chmod(0o644)
    before = _one(tmp_path).tree_sha
    (folder / "run.sh").chmod(0o755)
    assert _one(tmp_path).tree_sha != before


#
# scan_repositories: errors
#
def test_a_loose_file_in_repositories_is_an_error(tmp_path):
    _write(tmp_path / "repositories", {"notes.txt": "x", "lab1/a": "a"})
    with pytest.raises(RepositoryError, match=r"notes\.txt"):
        _scan(tmp_path)


@posix_only
def test_a_symlink_to_a_file_is_an_error(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"a.txt": "a"})
    os.symlink("a.txt", folder / "link.txt")
    with pytest.raises(RepositoryError, match=r"link\.txt"):
        _scan(tmp_path)


@posix_only
def test_a_symlink_to_a_directory_is_an_error(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"real/a.txt": "a"})
    os.symlink("real", folder / "alias", target_is_directory=True)
    with pytest.raises(RepositoryError, match="alias"):
        _scan(tmp_path)


@posix_only
def test_a_dangling_symlink_is_an_error(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"a.txt": "a"})
    os.symlink("nowhere", folder / "dangling")
    with pytest.raises(RepositoryError, match="dangling"):
        _scan(tmp_path)


@pytest.mark.parametrize("name", ["has space", "UPPER", "-lead", "a_b!", ".hidden"])
def test_a_folder_whose_name_is_not_a_slug_is_an_error(tmp_path, name):
    _write(tmp_path / "repositories" / name, {"a": "a"})
    with pytest.raises(RepositoryError, match=name.replace(".", r"\.")):
        _scan(tmp_path)


def test_a_file_over_the_limit_is_refused(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"ok.txt": "ok"})
    with (folder / "big.bin").open("wb") as handle:
        handle.truncate(MAX_FILE_BYTES + 1)
    with pytest.raises(RepositoryError, match=r"big\.bin"):
        _scan(tmp_path)


def test_a_file_of_exactly_the_limit_is_accepted(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    folder.mkdir(parents=True)
    with (folder / "big.bin").open("wb") as handle:
        handle.truncate(MAX_FILE_BYTES)
    [entry] = _one(tmp_path).entries
    assert entry.size == MAX_FILE_BYTES


def test_a_folder_with_no_file_is_an_error(tmp_path):
    (tmp_path / "repositories" / "lab1" / "sub").mkdir(parents=True)
    with pytest.raises(RepositoryError, match="lab1"):
        _scan(tmp_path)


def test_a_folder_whose_files_are_all_ignored_is_an_error(tmp_path):
    folder = tmp_path / "repositories" / "lab1"
    _write(folder, {"a.tmp": "x"})
    with pytest.raises(RepositoryError, match="lab1"):
        _scan(tmp_path, ("repositories/lab1/a.tmp",))


#
# batch_entries
#
def test_batches_keep_the_order_and_the_limit():
    entries = [_entry(f"f{i}", size) for i, size in enumerate([4, 4, 4, 1, 7, 2])]
    batches = list(batch_entries(entries, max_bytes=8))
    assert [[e.path for e in batch] for batch in batches] == [
        ["f0", "f1"],
        ["f2", "f3"],
        ["f4"],
        ["f5"],
    ]


def test_a_file_of_exactly_the_limit_travels_alone():
    entries = [_entry("a", 1), _entry("big", 8), _entry("b", 1)]
    batches = list(batch_entries(entries, max_bytes=8))
    assert [[e.path for e in batch] for batch in batches] == [["a"], ["big"], ["b"]]


def test_a_file_over_the_limit_is_refused_by_batching():
    with pytest.raises(ValueError):
        list(batch_entries([_entry("big", 9)], max_bytes=8))


def test_no_entries_make_no_batches():
    assert list(batch_entries([])) == []


def test_the_default_limit_is_sixteen_megabytes():
    assert MAX_FILE_BYTES == 16 * 1024 * 1024
    half = MAX_FILE_BYTES // 2
    entries = [_entry("a", half), _entry("b", half), _entry("c", 1)]
    assert [len(batch) for batch in batch_entries(entries)] == [2, 1]


@given(st.lists(st.integers(min_value=0, max_value=20), max_size=30))
def test_batches_partition_the_entries_within_the_limit(sizes):
    entries = [_entry(f"f{i}", size) for i, size in enumerate(sizes)]
    batches = list(batch_entries(entries, max_bytes=20))
    assert [e for batch in batches for e in batch] == entries
    assert all(batch and sum(e.size for e in batch) <= 20 for batch in batches)
