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
    read_course_name,
)
from ._scaffold import (
    IdentityConflictError,
    PathReport,
    PathStatus,
    RepoError,
    read_config,
    write_repo,
)

__all__ = [
    "write_repo",
    "read_config",
    "read_course_name",
    "PathReport",
    "PathStatus",
    #: Errors
    "RepoError",
    "IdentityConflictError",
    #: Layout constants
    "CONFIG_FILE",
    "README_FILE",
    "CALENDAR_FILE",
    "GITIGNORE_FILE",
    "QUESTIONS_DIR",
    "EXAMS_DIR",
    "RESOURCES_DIR",
    "REPOSITORIES_DIR",
    "MACHINE_DIR",
    "GIT_DIR",
    "EXAMPLE_ID",
    "EXAMPLE_QUESTION_FILE",
    "EXAMPLE_EXAM_FILE",
]
