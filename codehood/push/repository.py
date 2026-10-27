"""
The core that turns the folders under `repositories/` into git trees.

Each direct subfolder of `repositories/` is one repository, its name the
slug. A scan reads the files, hashes each one twice (sha-256 for the
server's blob store, sha1 for git) and computes the sha1 of the root tree
the server would build from them, so `plan.py` can compare it to the
server's `tree` without uploading anything. No network here.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pathspec

from ..globs import is_excluded
from ..repo import REPOSITORIES_DIR
from .errors import RepositoryError

__all__ = [
    "MAX_FILE_BYTES",
    "REPOSITORIES_DIR",
    "FileMode",
    "RepositoryEntry",
    "RepositoryTree",
    "batch_entries",
    "blob_sha",
    "file_mode",
    "scan_repositories",
    "tree_sha",
]

#: The largest file the server accepts, and the largest upload batch.
MAX_FILE_BYTES = 16 * 1024 * 1024

#: The git mode of a file: regular or executable.
type FileMode = Literal["100644", "100755"]

#: What the server accepts as a repository slug.
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._\-]*$")

#: The longest slug the server accepts.
MAX_SLUG_LENGTH = 200

#: A directory in a git tree.
TREE_MODE = "40000"


@dataclass(frozen=True)
class RepositoryEntry:
    """
    One file of a repository, as the server and git name it.
    """

    #: Relative to the repository folder, `/`-separated.
    path: str
    mode: FileMode
    #: Lowercase-hex sha-256 of the bytes: the server's blob hash.
    sha256: str
    #: Lowercase-hex sha1 of `b"blob <size>\0" + bytes`, as `git hash-object`.
    git_sha: str
    size: int
    #: The file on disk, read again only to upload it.
    source: Path


@dataclass(frozen=True)
class RepositoryTree:
    """
    One folder under `repositories/`, scanned.
    """

    slug: str
    #: Sorted by `path`, byte order.
    entries: tuple[RepositoryEntry, ...]
    #: Sha1 of the root git tree built from `entries`.
    tree_sha: str

    @property
    def size(self) -> int:
        """
        Total bytes of the files.
        """
        return sum(entry.size for entry in self.entries)


def scan_repositories(
    root: Path, exclude: Sequence[str] = ()
) -> Iterator[RepositoryTree]:
    """
    Yield every repository under `root / "repositories"`, sorted by slug.

    Inside each folder: `.git` directories are skipped, empty directories
    vanish, and the `.gitignore` files of the folder apply at every level
    (gitwildmatch, `!` included, via `pathspec`); the `.gitignore` files
    themselves are published, and the one at the course root does not
    apply. `exclude` holds the `[push] exclude` patterns, matched against
    paths relative to `root` (`repositories/<slug>/...`). The mode comes from
    the owner's executable bit (`100644` everywhere on Windows). A missing
    `repositories/` yields nothing.

    Raises:
        RepositoryError: A file sits directly in `repositories/`, a folder
            name is not a valid slug, a symlink is found, a file exceeds
            `MAX_FILE_BYTES`, or a folder has no file left to publish.
    """
    base = root / REPOSITORIES_DIR
    if not base.is_dir():
        return
    children = sorted(os.scandir(base), key=lambda child: child.name)
    for child in children:
        path = Path(child.path)
        if child.is_symlink():
            raise RepositoryError(f"{path} is a symlink")
        if not child.is_dir():
            raise RepositoryError(
                f"{path} is a file: {REPOSITORIES_DIR}/ holds only repository folders"
            )
        if not SLUG_RE.match(child.name) or len(child.name) > MAX_SLUG_LENGTH:
            raise RepositoryError(
                f"{path}: {child.name!r} is not a valid repository slug "
                "(lowercase letters, digits, '.', '_' and '-', starting with "
                "a letter or digit)"
            )
    for child in children:
        entries = tuple(
            sorted(
                _walk(root, Path(child.path), Path(child.path), exclude, []),
                key=lambda entry: entry.path.encode("utf-8"),
            )
        )
        if not entries:
            raise RepositoryError(f"{child.path} has no file to publish")
        yield RepositoryTree(child.name, entries, tree_sha(entries))


def blob_sha(data: bytes) -> str:
    """
    The sha1 git gives a file with these bytes.

    @example
        >>> blob_sha(b"")
        'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
    """
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree_sha(entries: Sequence[RepositoryEntry]) -> str:
    """
    The sha1 of the root tree git builds for these files.

    Subdirectories become nested trees, entries are sorted in git order
    (a directory compares as `name/`), and the result does not depend on
    the order of `entries`. Matches `git write-tree` on the same checkout.

    Raises:
        ValueError: `entries` is empty, or a path is both a file and a
            directory.
    """
    if not entries:
        raise ValueError("a tree needs at least one file")
    root: _Node = {}
    for entry in entries:
        *directories, name = entry.path.split("/")
        node = root
        for directory in directories:
            child = node.setdefault(directory, {})
            if not isinstance(child, dict):
                raise ValueError(f"{entry.path}: {directory!r} is also a file")
            node = child
        if name in node:
            raise ValueError(f"{entry.path} is both a file and a directory")
        node[name] = (entry.mode, entry.git_sha)
    return _node_sha(root)


def file_mode(path: Path) -> FileMode:
    """
    `100755` when the owner may execute `path`, `100644` otherwise or on
    Windows.
    """
    if sys.platform == "win32":
        return "100644"
    return "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"


def batch_entries(
    entries: Sequence[RepositoryEntry], max_bytes: int = MAX_FILE_BYTES
) -> Iterator[tuple[RepositoryEntry, ...]]:
    """
    Split files into upload batches of at most `max_bytes` each, in order.

    Every batch holds at least one file; a file of exactly `max_bytes`
    travels alone.

    Raises:
        ValueError: A file is larger than `max_bytes`.
    """
    batch: list[RepositoryEntry] = []
    total = 0
    for entry in entries:
        if entry.size > max_bytes:
            raise ValueError(f"{entry.path} is larger than {max_bytes} bytes")
        if batch and total + entry.size > max_bytes:
            yield tuple(batch)
            batch, total = [], 0
        batch.append(entry)
        total += entry.size
        if total == max_bytes:
            yield tuple(batch)
            batch, total = [], 0
    if batch:
        yield tuple(batch)


#
# Utilities
#

#: A directory is a mapping; a file is its `(mode, git sha)`.
type _Node = dict[str, _Node | tuple[str, str]]


def _node_sha(node: _Node) -> str:
    """
    The sha1 of the git tree object for a nested directory mapping.
    """
    items: list[tuple[bytes, bytes]] = []
    for name, value in node.items():
        raw = name.encode("utf-8")
        if isinstance(value, dict):
            mode, sha, key = TREE_MODE, _node_sha(value), raw + b"/"
        else:
            (mode, sha), key = value, raw
        items.append((key, mode.encode() + b" " + raw + b"\0" + bytes.fromhex(sha)))
    body = b"".join(content for _, content in sorted(items))
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def _walk(
    root: Path,
    repository: Path,
    directory: Path,
    exclude: Sequence[str],
    specs: list[tuple[str, pathspec.PathSpec]],
) -> Iterator[RepositoryEntry]:
    """
    Yield the publishable files under `directory`, depth first.

    `repository` is the folder of the repository being scanned. `specs` pairs each `.gitignore` found on the way down with the
    directory it lives in, relative to the repository folder, outermost
    first.
    """
    prefix = directory.relative_to(repository).as_posix()
    gitignore = directory / ".gitignore"
    if gitignore.is_file() and not gitignore.is_symlink():
        lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        specs = [
            *specs,
            (
                "" if prefix == "." else prefix + "/",
                pathspec.PathSpec.from_lines("gitignore", lines),
            ),
        ]
    for child in sorted(os.scandir(directory), key=lambda item: item.name):
        path = Path(child.path)
        if child.name == ".git":
            continue
        relative = path.relative_to(repository).as_posix()
        if is_excluded(path.relative_to(root).as_posix(), exclude):
            continue
        is_dir = child.is_dir(follow_symlinks=False)
        if _ignored(relative + "/" if is_dir else relative, specs):
            continue
        if child.is_symlink():
            raise RepositoryError(f"{path} is a symlink")
        if is_dir:
            yield from _walk(root, repository, path, exclude, specs)
        elif child.is_file(follow_symlinks=False):
            yield _read_entry(path, relative)
        else:
            raise RepositoryError(f"{path} is not a regular file")


def _ignored(relative: str, specs: list[tuple[str, pathspec.PathSpec]]) -> bool:
    """
    Whether the nested `.gitignore` files ignore a path: the innermost rule
    that matches decides, and within one file the last one.
    """
    ignored = False
    for base, spec in specs:
        if not relative.startswith(base):
            continue
        result = spec.check_file(relative[len(base) :])
        if result.include is not None:
            ignored = result.include
    return ignored


def _read_entry(path: Path, relative: str) -> RepositoryEntry:
    """
    Hash one file into a `RepositoryEntry`.
    """
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise RepositoryError(
            f"{path} is {size} bytes, over the {MAX_FILE_BYTES} byte limit"
        )
    data = path.read_bytes()
    return RepositoryEntry(
        path=relative,
        mode=file_mode(path),
        sha256=hashlib.sha256(data).hexdigest(),
        git_sha=blob_sha(data),
        size=len(data),
        source=path,
    )
