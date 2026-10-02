"""
Loading the instructor's `grades.py`.

The one place `codehood push` runs code that is not its own. The script is
the instructor's, runs on their machine and reads only their own course --
see `dev/specs/to-review/push-grades.md`, "The function runs inside the CLI".
"""

from __future__ import annotations

import importlib.util
import traceback
from pathlib import Path

from ..grades import GradeFunction
from .grades import GradesError

__all__ = ["load_grade_function"]

#: The name the instructor's function must have.
FUNCTION_NAME = "grade"


def load_grade_function(path: Path) -> GradeFunction:
    """
    Import `grades.py` from `path` and return its `grade` function.

    Raises:
        GradesError: The file does not import, or defines no callable
            named `grade`.
    """
    spec = importlib.util.spec_from_file_location("codehood_course_grades", path)
    if spec is None or spec.loader is None:
        raise GradesError([f"{path} cannot be imported as a Python module"])

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        raise GradesError(
            [f"{path} failed to import:\n{traceback.format_exc().rstrip()}"]
        ) from None

    function = getattr(module, FUNCTION_NAME, None)
    if not callable(function):
        raise GradesError([f"{path} defines no function named {FUNCTION_NAME!r}"])
    grade: GradeFunction = function
    return grade
