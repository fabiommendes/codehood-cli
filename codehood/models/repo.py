"""
Pydantic models for `codehood.toml`, the course repository's identity file.

The file holds a course's identity (`discipline`, `instructor`, `edition`),
the server it syncs with, and the grade columns it pushes. It never holds a
secret -- see `dev/specs/to-do/init.md`, "`codehood.toml` is committed and
holds no secret", for why.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..globs import pattern_error
from .base import Model
from .validators import (
    DisciplineSlug,
    EditionSlug,
    GradeColumnSlug,
    InstructorUsername,
    ServerUrl,
)

__all__ = [
    "CourseIdentity",
    "ServerConfig",
    "GradeColumnConfig",
    "GradesConfig",
    "PushConfig",
    "RepoConfig",
]


class CourseIdentity(Model):
    """
    The three values that name a course: `(discipline, instructor, edition)`.
    """

    discipline: DisciplineSlug
    instructor: InstructorUsername
    edition: EditionSlug


class ServerConfig(Model):
    """
    The server a course repository syncs with.
    """

    url: ServerUrl


class GradeColumnConfig(Model):
    """
    One `[[grades.column]]` table: a grade column the course pushes.
    """

    slug: GradeColumnSlug
    #: Defaults to the slug.
    title: str = Field(default="", max_length=80)
    kind: Literal["number", "label"] = "number"

    @model_validator(mode="after")
    def title_defaults_to_slug(self) -> Self:
        self.title = self.title.strip() or self.slug
        return self


class GradesConfig(Model):
    """
    The `[grades]` table: the course's grade columns, in table order.
    """

    column: list[GradeColumnConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def slugs_are_unique(self) -> Self:
        seen: set[str] = set()
        for column in self.column:
            if column.slug in seen:
                raise ValueError(f"grade column {column.slug!r} is declared twice")
            seen.add(column.slug)
        return self


class PushConfig(Model):
    """
    The `[push]` table: what `codehood push` leaves out.
    """

    model_config = ConfigDict(extra="forbid")

    #: Gitignore-like patterns, relative to the repository root. See
    #: `codehood.globs`.
    exclude: list[str] = Field(default_factory=list)

    @field_validator("exclude")
    @classmethod
    def patterns_are_valid(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            if (error := pattern_error(pattern)) is not None:
                raise ValueError(f"{pattern!r}: {error}")
        return patterns


class RepoConfig(Model):
    """
    The full contents of `codehood.toml`: course identity, server, the
    grade columns the course pushes and what it leaves out of a push.
    """

    course: CourseIdentity
    server: ServerConfig
    grades: GradesConfig = Field(default_factory=GradesConfig)
    push: PushConfig = Field(default_factory=PushConfig)

    @classmethod
    def open(cls, path: Path | None = None) -> RepoConfig:
        """
        Open the codehood.toml file and return the corresponding config.

        Path can be the path to the config file or the base directory where it
        is located. Defaults to CWD.
        """
        if path is None:
            path = Path.cwd()
        if path.is_dir():
            path = path / "codehood.toml"

        if not path.exists():
            raise FileNotFoundError(f"could not find Codehood config at {path}")

        # `tomllib`, not `tomlkit`: pydantic reads only the first table out of
        # a `tomlkit` array of tables, which would drop every grade column
        # but one.
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return RepoConfig.model_validate(data)
