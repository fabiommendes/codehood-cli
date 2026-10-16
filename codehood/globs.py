"""
Gitignore-like path patterns, as used by `[push] exclude` in `codehood.toml`.

Patterns are relative to the repository root, with `/` as the separator:

- `*` matches any run of characters inside one path segment, `?` one character.
- `**` as a whole segment matches any number of directories.
- A pattern that matches a directory also matches everything under it.
- A leading or trailing `/` is ignored. There is no negation (`!`).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

__all__ = ["is_excluded", "pattern_error"]


def is_excluded(path: str, patterns: Sequence[str]) -> bool:
    """
    Tell whether any pattern matches a root-relative, `/`-separated path.

    @example
        >>> is_excluded("questions/wip/a.mdq", ["questions/wip"])
        True
    """
    return any(_compile(pattern).match(path) for pattern in patterns)


def pattern_error(pattern: str) -> str | None:
    """
    Why a pattern is not acceptable, or `None` when it is.
    """
    body = pattern.strip().strip("/")
    if not body:
        return "pattern is empty"
    if body.startswith("!"):
        return "negated patterns (`!`) are not supported"
    if ".." in body.split("/"):
        return "pattern must stay inside the repository (no `..`)"
    return None


#
# Utilities
#
def _compile(pattern: str) -> re.Pattern[str]:
    segments = pattern.strip().strip("/").split("/")
    regex = ""
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if segment == "**":
            regex += ".+" if last else "(?:[^/]+/)*"
        else:
            regex += _segment_regex(segment) + ("" if last else "/")
    return re.compile(f"{regex}(?:/.*)?$")


def _segment_regex(segment: str) -> str:
    parts = {"*": "[^/]*", "?": "[^/]"}
    return "".join(parts.get(char) or re.escape(char) for char in segment)
