from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import tomlkit

from ..models.repo import CourseIdentity, RepoConfig, ServerConfig
from . import _layout

PathStatus = Literal["created", "exists"]


@dataclass(frozen=True)
class PathReport:
    """
    One line of `init`'s output: a path, and whether it was just created.
    """

    path: Path
    status: PathStatus


class RepoError(Exception):
    """
    Base class for errors `write_repo` raises. `cli/init.py` catches this
    and reports it as a clean CLI error rather than a traceback.
    """


class IdentityConflictError(RepoError):
    """
    Raised when an existing `codehood.toml` names a different course than
    the one `init` was asked to write. `init` never changes an identity
    field once committed -- see the spec's "Nothing is ever overwritten".
    """


def write_repo(
    path: Path,
    identity: CourseIdentity,
    server: ServerConfig,
    *,
    name: str | None = None,
    git: bool = True,
    examples: bool = True,
) -> list[PathReport]:
    """
    Write (or repair) a course repository at `path`.

    Creates whatever is missing from the layout in
    `dev/specs/to-do/init.md`'s "The layout" and leaves whatever already
    exists untouched, so running this twice with the same arguments is a
    no-op. Never overwrites a file.

    Args:
        path: The repository root. Created if missing.
        identity: The course's `(discipline, instructor, edition)`.
        server: The server this repository syncs with.
        git: Run `git init` (skipped if `path` is already inside a work
            tree).
        examples: Write the example question and exam.

    Returns:
        One `PathReport` per path considered, in write order.

    Raises:
        IdentityConflictError: An existing `codehood.toml` names a
            different course.
    """
    path.mkdir(parents=True, exist_ok=True)
    reports = [
        ensure_config(path / _layout.CONFIG_FILE, identity, server),
        ensure_file(
            path / _layout.README_FILE,
            _layout.render_readme(name or identity.discipline),
        ),
        ensure_file(path / _layout.CALENDAR_FILE, _layout.render_calendar()),
        ensure_file(path / _layout.GITIGNORE_FILE, _layout.render_gitignore()),
        ensure_dir(path / _layout.QUESTIONS_DIR),
        ensure_dir(path / _layout.EXAMS_DIR),
        ensure_dir(path / _layout.RESOURCES_DIR),
        ensure_dir(path / _layout.REPOSITORIES_DIR),
        ensure_dir(path / _layout.MACHINE_DIR),
    ]
    if examples:
        reports.append(
            ensure_file(
                path / _layout.QUESTIONS_DIR / _layout.EXAMPLE_QUESTION_FILE,
                _layout.render_example_question(),
            )
        )
        reports.append(
            ensure_file(
                path / _layout.EXAMS_DIR / _layout.EXAMPLE_EXAM_FILE,
                _layout.render_example_exam(identity.discipline),
            )
        )
    git_report = ensure_git(path, enabled=git)
    if git_report is not None:
        reports.append(git_report)
    return [
        PathReport(report.path.relative_to(path), report.status) for report in reports
    ]


def ensure_file(path: Path, content: str) -> PathReport:
    """
    Write `content` to `path` if it does not already exist.
    """
    if path.exists():
        return PathReport(path, "exists")
    path.write_text(content, encoding="utf-8")
    return PathReport(path, "created")


def ensure_dir(path: Path) -> PathReport:
    """
    Create `path` as a directory if it does not already exist.
    """
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)
    return PathReport(path, "exists" if existed else "created")


def read_config(path: Path) -> RepoConfig | None:
    """
    Read `codehood.toml` at `path`, or `None` if it does not exist.

    Used by anything that wants the current repository's server URL as a
    default (e.g. `api.base.get_client`) without duplicating `_ensure_config`'s
    parsing.
    """
    if not path.exists():
        return None
    return RepoConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


def ensure_config(
    path: Path, identity: CourseIdentity, server: ServerConfig
) -> PathReport:
    """
    Write `codehood.toml`, or validate an existing one.

    An existing file is read but never rewritten, so a second `init` with the
    same arguments changes no bytes.
    """
    if path.exists():
        existing = RepoConfig.model_validate(
            tomllib.loads(path.read_text(encoding="utf-8"))
        )
        if existing.course != identity:
            raise IdentityConflictError(
                f"{path} already names a course "
                f"(discipline={existing.course.discipline!r}, "
                f"instructor={existing.course.instructor!r}, "
                f"edition={existing.course.edition!r}); "
                "init never changes an identity field"
            )
        return PathReport(path, "exists")
    path.write_text(render_config(identity, server), encoding="utf-8")
    return PathReport(path, "created")


def render_config(identity: CourseIdentity, server: ServerConfig) -> str:
    """
    Render `codehood.toml`'s contents as TOML text.
    """
    doc = tomlkit.document()
    course = tomlkit.table()
    course["discipline"] = identity.discipline
    course["instructor"] = identity.instructor
    course["edition"] = identity.edition
    doc["course"] = course
    server_table = tomlkit.table()
    server_table["url"] = server.url
    doc["server"] = server_table
    return tomlkit.dumps(doc)


def ensure_git(path: Path, *, enabled: bool) -> PathReport | None:
    """
    Run `git init` in `path`, unless disabled or already inside a work
    tree.

    Returns `None` when there is nothing to report: `git` is disabled, or
    `path` is already inside a work tree it does not own (so creating a
    nested repository would be wrong -- see the spec's git test).
    """
    if not enabled:
        return None
    git_dir = path / _layout.GIT_DIR
    if git_dir.exists():
        return PathReport(git_dir, "exists")
    if is_inside_work_tree(path):
        return None
    subprocess.run(
        ["git", "init"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return PathReport(git_dir, "created")


def is_inside_work_tree(path: Path) -> bool:
    """
    Return whether `path` is already inside a git work tree.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"
