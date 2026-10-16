"""
The files a push leaves out because of `[push] exclude` in `codehood.toml`.

Excluded files are never read, so they cannot be pushed; what the server
already holds under their slugs is protected from pruning (see
`plan.plan_push`). Only `questions/` and `resources/` are excludable: they
are the only trees whose files are pushed one by one.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..repo.diff import FileType
from ..repo.file_tracker import scan_files
from .resource import slugify

__all__ = ["ExcludedFile", "scan_excluded"]


@dataclass(frozen=True)
class ExcludedFile:
    """
    A question or resource file that matched an `exclude` pattern.
    """

    kind: Literal["question", "resource"]
    slug: str
    #: Relative to the repository root, `/`-separated.
    path: str


def scan_excluded(root: Path, exclude: Sequence[str]) -> Iterator[ExcludedFile]:
    """
    Yield every question and resource file the patterns exclude.
    """
    kinds = {FileType.QUESTION: "question", FileType.RESOURCE: "resource"}
    for file in scan_files(root, exclude):
        if file.excluded and file.type in kinds:
            yield ExcludedFile(
                kind=kinds[file.type],  # type: ignore[arg-type]
                slug=slugify(Path(file.name)),
                path=file.path.as_posix(),
            )
