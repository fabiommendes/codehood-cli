"""
What a course's `grades.py` works with.

`codehood push` calls the `grade` function of that file once per enrolled
student, with a `Student`, and pushes what it returns as grade columns. See
`dev/specs/to-review/push-grades.md`.

```python
from codehood.grades import Student

def grade(student: Student) -> dict[str, float | str | None]:
    midterm = student.exams["midterm"].score or 0.0
    return {"total": 0.6 * midterm + 0.4 * (student.scores["project"] or 0.0)}
```
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

__all__ = [
    "Student",
    "ExamResult",
    "ExamState",
    "GradeFunction",
    "GradeValue",
]

#: Why an exam has a score or lacks one: every answer graded, answers still
#: waiting for a grade, an attempt still open, an exam the student missed,
#: or an exam with no attempt that has not closed yet.
type ExamState = Literal["graded", "pending", "in_progress", "missed", "not_held"]

#: What one cell of a grade column holds. `None` is no value at all.
type GradeValue = float | str | None

#: The signature of `grades.py`'s `grade`: a student's value for each column
#: the function computes, keyed by column slug.
type GradeFunction = Callable[["Student"], Mapping[str, GradeValue]]


@dataclass(frozen=True)
class ExamResult:
    """
    One student's result at one exam.

    `score` is a percentage from -100 to 100, the scale of the Grades tab,
    and is a number only when `state` is `graded`.
    """

    score: float | None
    state: ExamState


@dataclass(frozen=True)
class Student:
    """
    One enrolled student, with everything `grade` may compute from.

    `exams` has one result per exam of the server's Grades tab, by slug, and
    `scores` one entry per score column of `grades.csv`, `None` where the
    student has no row or the cell is empty.
    """

    username: str
    name: str
    email: str
    school_id: str | None
    github: str | None
    status: Literal["active", "dropped"]
    exams: Mapping[str, ExamResult] = field(default_factory=dict)
    scores: Mapping[str, GradeValue] = field(default_factory=dict)
