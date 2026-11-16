"""
`codehood exam`: commands that act on one exam of the course on the server.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import httpx
import typer
from pydantic import ValidationError

from .. import repo
from ..api import generated
from ..api.base import get_client
from ..models.repo import RepoConfig
from .base import app

__all__ = ["exam", "refusal_text", "release"]

exam = typer.Typer(name="exam", help="Act on one exam of the course.")
app.add_typer(exam)


@exam.command()
def release(
    slug: Annotated[str, typer.Argument(help="Slug of the exam.")],
    path: Annotated[
        Path,
        typer.Argument(help="Course repository. Defaults to the current directory."),
    ] = Path("."),
) -> None:
    """
    Release the grades of an exam to its students.

    Releasing an exam already released changes nothing.

    Raises:
        typer.Exit: With code 1 when the repository has no valid
            `codehood.toml`, or the server refuses the release.
    """
    try:
        config = RepoConfig.open(repo.config_path(path))
    except (FileNotFoundError, ValidationError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    client = get_client(config.server.url)
    try:
        result = generated.exam_release(
            discipline=config.course.discipline,
            course=f"{config.course.instructor}_{config.course.edition}",
            slug=slug,
            client=client,
        )
    except generated.GradeReleaseRefused as exc:
        typer.echo(f"error: cannot release {slug}: {refusal_text(exc)}", err=True)
        raise typer.Exit(code=1) from exc
    except httpx.HTTPStatusError as exc:
        typer.echo(f"error: {status_text(slug, exc.response.status_code)}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"released the grades of {slug} at {result.grades_released_at}")


def refusal_text(exc: generated.GradeReleaseRefused) -> str:
    """
    Why the server refused to release an exam, with the counts it checked.
    """
    match exc.reason:
        case "not-closed":
            return (
                "the exam is not closed yet. Close it on the exam's page "
                "(this also ends the attempts still open), then release again"
            )
        case "pending":
            return f"{plural(exc.payload.pending_answers, 'answer')} still without a grade"
        case "exception-open":
            count = exc.payload.open_exceptions
            verb = "keeps" if count == 1 else "keep"
            return f"{plural(count, 'student exception')} still {verb} a personal window open"
        case "not-an-exam":
            return "it is a quiz or a practice; only an EXAM releases grades"


#
# Utilities
#
def status_text(slug: str, status: int) -> str:
    """
    The error line for a failed release the server gave no reason for.
    """
    match status:
        case 403:
            return f"not allowed to release {slug}: only the course's instructor can"
        case 404:
            return f"no exam {slug} in this course"
        case _:
            return f"could not release {slug}: the server answered {status}"


def plural(count: int, noun: str) -> str:
    """
    `count` followed by `noun`, with an `s` unless `count` is 1.
    """
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
