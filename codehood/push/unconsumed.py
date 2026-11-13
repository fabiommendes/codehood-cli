"""
The repository files a push did not read.

`find_unconsumed` is the pure core: it diffs the paths found on disk against
the paths the push stages consumed. `list_files` and `consumed_paths` feed it
from the filesystem.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Collection, Iterable
from pathlib import Path

import pathspec

from ..repo import REPOSITORIES_DIR
from ..repo.diff import FileType
from ..repo.file_tracker import File

__all__ = [
    "IGNORE_FILE",
    "consumed_paths",
    "excluded_paths",
    "find_unconsumed",
    "ignore_patterns",
    "list_files",
    "read_ignore",
]

#: Course-root file with gitignore-syntax lines that codehood ignores.
IGNORE_FILE = ".codehoodignore"

#: Trees whose files are pushed one by one: a match there is excluded, not
#: forgotten, so the server copy survives the prune.
PUSHED_TREES = ("questions", "resources")

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
    codehoodignore: Iterable[str] = (),
) -> tuple[str, ...]:
    """
    Sort the versionable paths that no push stage read.

    `paths` are `/`-separated and relative to the repository root. Everything
    under `repositories/` counts as consumed, `excluded` paths have their own
    list, and the root `.gitignore` and `.codehoodignore` are not reported.
    `codehoodignore` lines (gitignore syntax) drop a path as if it did not exist.
    """
    ignored = pathspec.PathSpec.from_lines("gitignore", gitignore)
    dropped = pathspec.PathSpec.from_lines("gitignore", codehoodignore)
    return tuple(
        sorted(
            path
            for path in set(paths)
            if path not in consumed
            and path not in excluded
            and path not in (".gitignore", IGNORE_FILE)
            and not path.startswith(f"{REPOSITORIES_DIR}/")
            and not ignored.match_file(path)
            and not dropped.match_file(path)
        )
    )


def consumed_paths(
    files: Iterable[File],
    *,
    sources: Iterable[Path] = (),
    root: Path | None = None,
) -> frozenset[str]:
    """
    The paths the push stages read: the fixed root files, plus the tracked
    questions and resources that are not excluded.

    `sources` are the test files that `code` questions link. They count as
    read when they lie under `root`.
    """
    tracked = {FileType.QUESTION, FileType.RESOURCE, FileType.EXAM}
    linked = {
        relative.as_posix()
        for source in sources
        if (relative := _relative_to(source, root)) is not None
    }
    return (
        frozenset(ROOT_CONSUMED)
        | linked
        | {
            file.path.as_posix()
            for file in files
            if file.type in tracked and not file.excluded
        }
    )


def _relative_to(path: Path, root: Path | None) -> Path | None:
    """
    `path` made relative to `root` with `..` segments resolved, or `None`
    when it lies outside it.
    """
    if root is None:
        return None
    resolved = Path(os.path.normpath(path))
    try:
        return resolved.relative_to(Path(os.path.normpath(root)))
    except ValueError:
        return None


def excluded_paths(files: Iterable[File]) -> frozenset[str]:
    """
    The tracked paths that a `[push] exclude` pattern matched.
    """
    return frozenset(file.path.as_posix() for file in files if file.excluded)


def list_files(root: Path) -> tuple[list[str], list[str]]:
    """
    List the repository files that git does not ignore.

    In a git repository, git decides (`.gitignore` at any level,
    `.git/info/exclude` and `core.excludesFile`), tracked and untracked files
    alike, and the returned lines are empty. Otherwise it walks the tree,
    skipping `.git/`, `.local/` and the legacy `.codehood/`, and returns the
    lines of the root `.gitignore` for `find_unconsumed` to apply.

    Returns the relative paths and the `.gitignore` lines.
    """
    if (found := _git_files(root)) is not None:
        return found, []
    paths: list[str] = []
    for directory, subdirs, names in os.walk(root):
        subdirs[:] = [name for name in subdirs if name not in SKIPPED_DIRS]
        base = Path(directory).relative_to(root)
        paths.extend((base / name).as_posix() for name in names)
    return paths, _read_lines(root / ".gitignore")


def read_ignore(root: Path) -> list[str]:
    """
    The lines of the course's `.codehoodignore`, empty when there is none.
    """
    return _read_lines(root / IGNORE_FILE)


def ignore_patterns(root: Path, lines: Iterable[str]) -> list[str]:
    """
    `[push] exclude` patterns for the pushed files that `.codehoodignore` matches.

    Each file under `questions/` and `resources/` that the lines match becomes
    one literal pattern, so the existing exclude mechanism protects it.
    """
    spec = pathspec.PathSpec.from_lines("gitignore", lines)
    patterns: list[str] = []
    for tree in PUSHED_TREES:
        for directory, _, names in os.walk(root / tree):
            base = Path(directory).relative_to(root)
            for name in names:
                path = (base / name).as_posix()
                if spec.match_file(path):
                    patterns.append(re.sub(r"([*?\\])", r"\\\1", path))
    return patterns


#
# Utilities
#
def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def _git_files(root: Path) -> list[str] | None:
    """
    Ask git for the files of a course that is a git repository, or `None` when
    it is not one or git is unavailable.
    """
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return sorted(
        {
            name
            for name in names
            if name
            and name.split("/", 1)[0] not in SKIPPED_DIRS
            and (root / name).is_file()
        }
    )
