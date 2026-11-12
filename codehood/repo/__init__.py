"""
Layout and scaffolding for a course repository.

A course repository is a directory of plain text an instructor edits,
commits, and pushes: `codehood.toml`, `README.md`, `calendar.md`,
`questions/`, `exams/`, and `resources/`. This module knows that layout and
how to write it, but nothing about the terminal or the network -- see
`dev/specs/to-do/init.md`.
"""

from __future__ import annotations

from ._layout import (
    CALENDAR_FILE,
    CONFIG_FILE,
    EXAMPLE_EXAM_FILE,
    EXAMPLE_ID,
    EXAMPLE_QUESTION_FILE,
    EXAMS_DIR,
    GIT_DIR,
    GITIGNORE_FILE,
    MACHINE_DIR,
    QUESTIONS_DIR,
    README_FILE,
    REPOSITORIES_DIR,
    RESOURCES_DIR,
)
from ._scaffold import (
    IdentityConflictError,
    PathReport,
    PathStatus,
    RepoError,
    ensure_machine_dir,
    read_config,
    write_repo,
)

__all__ = [
    "CALENDAR_FILE",
    "CONFIG_FILE",
    "EXAMPLE_EXAM_FILE",
    "EXAMPLE_ID",
    "EXAMPLE_QUESTION_FILE",
    "EXAMS_DIR",
    "GITIGNORE_FILE",
    "GIT_DIR",
    "MACHINE_DIR",
    "QUESTIONS_DIR",
    "README_FILE",
    "REPOSITORIES_DIR",
    "RESOURCES_DIR",
    "IdentityConflictError",
    "PathReport",
    "PathStatus",
    "RepoError",
    "ensure_machine_dir",
    "read_config",
    "write_repo",
]
