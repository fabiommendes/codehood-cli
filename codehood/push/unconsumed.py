"""
The repository files a push did not read.

`find_unconsumed` is the pure core: it diffs the paths found on disk against
the paths the push stages consumed. `list_files` and `consumed_paths` feed it
from the filesystem.
"""

from __future__ import annotations

import os
from collections.abc import Collection, Iterable
from pathlib import Path

import pathspec

from ..repo import REPOSITORIES_DIR
from ..repo.diff import FileType
from ..repo.file_tracker import File

__all__ = ["consumed_paths", "excluded_paths", "find_unconsumed", "list_files"]

#: Files at the root that the push stages read.
ROOT_CONSUMED = ("codehood.toml", "README.md", "calendar.md", "grades.py", "grades.csv")

#: Directories never versioned by the course: skipped without a gitignore.
SKIPPED_DIRS = frozenset({".git", ".codehood", ".local"})


def find_unconsumed(
    paths: Iterable[str],
    *,
    consumed: Collection[str],
    excluded: Collection[str],
    gitignore: Iterable[str] = (),
) -> tuple[str, ...]:
    """
    Sort the versionable paths that no push stage read.

    `paths` are `/`-separated and relative to the repository root. Everything
    under `repositories/` counts as consumed, `excluded` paths have their own
    list, and the root `.gitignore` itself is not reported.
    """
    ignored = pathspec.PathSpec.from_lines("gitignore", gitignore)
    return tuple(
        sorted(
            path
            for path in set(paths)
            if path not in consumed
            and path not in excluded
            and path != ".gitignore"
            and not path.startswith(f"{REPOSITORIES_DIR}/")
            and not ignored.match_file(path)
        )
    )


def consumed_paths(files: Iterable[File]) -> frozenset[str]:
    """
    The paths the push stages read: the fixed root files, plus the tracked
    questions and resources that are not excluded.
    """
    tracked = {FileType.QUESTION, FileType.RESOURCE}
    return frozenset(ROOT_CONSUMED) | {
        file.path.as_posix()
        for file in files
        if file.type in tracked and not file.excluded
    }


def excluded_paths(files: Iterable[File]) -> frozenset[str]:
    """
    The tracked paths that a `[push] exclude` pattern matched.
    """
    return frozenset(file.path.as_posix() for file in files if file.excluded)


def list_files(root: Path) -> tuple[list[str], list[str]]:
    """
    Walk the repository, skipping `.git/`, `.local/` and the legacy `.codehood/`.

    Returns the relative paths and the lines of the root `.gitignore`.
    """
    paths: list[str] = []
    for directory, subdirs, names in os.walk(root):
        subdirs[:] = [name for name in subdirs if name not in SKIPPED_DIRS]
        base = Path(directory).relative_to(root)
        paths.extend((base / name).as_posix() for name in names)
    ignore = root / ".gitignore"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.is_file() else []
    return paths, lines
