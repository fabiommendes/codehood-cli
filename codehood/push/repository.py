"""
The core that turns the folders under `repositories/` into git trees.

Each direct subfolder of `repositories/` is one repository, its name the
slug. A scan reads the files, hashes each one twice (sha-256 for the
server's blob store, sha1 for git) and computes the sha1 of the root tree
the server would build from them, so `plan.py` can compare it to the
server's `tree` without uploading anything. No network here.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..repo import REPOSITORIES_DIR

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
        raise NotImplementedError


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
    raise NotImplementedError


def blob_sha(data: bytes) -> str:
    """
    The sha1 git gives a file with these bytes.

    @example
        >>> blob_sha(b"")
        'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'
    """
    raise NotImplementedError


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
    raise NotImplementedError


def file_mode(path: Path) -> FileMode:
    """
    `100755` when the owner may execute `path`, `100644` otherwise or on
    Windows.
    """
    raise NotImplementedError


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
    raise NotImplementedError
