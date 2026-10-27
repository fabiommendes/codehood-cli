"""
The pure core that ties `resources/` files to the `calendar.md` lessons
that link to them.

A lesson is an `Event`: its `description` is the markdown of its h2
section. A markdown link in it whose target lies under `resources/`
attaches that resource to the event. Nothing here touches the network or
the disk: `plan.py` and `run.py` only carry the result.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from .calendar import Event, EventKey
from .errors import ResourceLinkError
from .repository import RepositoryTree
from .resource import ResourceFile, content_ref

__all__ = [
    "RepositoryLink",
    "attach_repositories",
    "attach_resources",
    "extract_repository_links",
    "extract_resource_links",
    "rewrite_repository_links",
    "rewrite_event_links",
    "rewrite_resource_links",
]


def extract_resource_links(markdown: str) -> tuple[PurePosixPath, ...]:
    """
    List the targets of the markdown links that point under `resources/`.

    Targets are returned relative to the course root, normalized (a leading
    `./` is dropped), in order of first appearance. Links to anything else
    (http URLs, other paths, `#anchors`) are ignored.
    """
    found: dict[PurePosixPath, None] = {}
    for start, end in _link_targets(markdown):
        target = _resources_target(markdown[start:end])
        if target is not None:
            found.setdefault(target, None)
    return tuple(found)


def attach_resources(
    events: Sequence[Event],
    resources: Sequence[ResourceFile],
    root: Path,
) -> tuple[ResourceFile, ...]:
    """
    Return `resources`, same order, with `event` set to the lesson linking
    each one and `ref` recomputed to include it.

    A resource no lesson links keeps `event=None` and its ref unchanged.
    `root` is the course root: a link `resources/a/b.pdf` matches the
    resource whose `path` is `root / "resources/a/b.pdf"`. The same
    resource linked more than once inside one lesson is fine.

    Raises:
        ResourceLinkError: A lesson links a path under `resources/` that is
            not one of `resources`, or one resource is linked from two
            different lessons.
    """
    by_path = {resource.path: resource for resource in resources}
    owner: dict[Path, Event] = {}
    for event in events:
        for link in extract_resource_links(event.description):
            path = root / link
            if path not in by_path:
                raise ResourceLinkError(
                    f"{_lesson(event)} links to {link}, which is not a resource"
                )
            first = owner.setdefault(path, event)
            if first is not event and (first.week, first.time_slot) != (
                event.week,
                event.time_slot,
            ):
                raise ResourceLinkError(
                    f"{link} is linked from two lessons: "
                    f"{_lesson(first)} and {_lesson(event)}"
                )

    attached: list[ResourceFile] = []
    for resource in resources:
        lesson = owner.get(resource.path)
        if lesson is None:
            attached.append(resource)
            continue
        key = EventKey(week=lesson.week, time_slot=lesson.time_slot)
        ref = content_ref(resource.title, resource.description, resource.data, key)
        attached.append(replace(resource, event=key, ref=ref))
    return tuple(attached)


def rewrite_resource_links(markdown: str, targets: Mapping[PurePosixPath, str]) -> str:
    """
    Replace the target of every `resources/` link found in `targets` by the
    mapped URL, keeping the link text.

    `targets` maps a root-relative path (as `extract_resource_links`
    returns it) to the URL that replaces it. A link spelled `./resources/x`
    or with a percent-encoded path matches like `resources/x`, and a
    `#fragment` on the original target is kept after the new URL. Anything
    else (other links, prose, links whose path is not in `targets`) is
    untouched.

    Code (fenced blocks and code spans) is never parsed for links. Reference
    links are rewritten at their definition only.
    """

    out = markdown
    for start, end in reversed(_link_targets(markdown)):
        raw = markdown[start:end]
        target = _resources_target(raw)
        url = targets.get(target) if target is not None else None
        if url is None:
            continue
        fragment = f"#{raw.split('#', 1)[1]}" if "#" in raw else ""
        out = out[:start] + url + fragment + out[end:]
    return out


def rewrite_event_links(
    events: Sequence[Event],
    resources: Sequence[ResourceFile],
    root: Path,
    discipline: str,
    course: str,
) -> tuple[Event, ...]:
    """
    Return `events`, same order, with every link to one of `resources`
    rewritten in the description to `/<discipline>/<course>/resources/<slug>`.

    Link text and `#fragment` are kept. Titles, week, slot and kind are
    unchanged; so is any event whose description links to no resource. The
    `ref` of a returned event follows its rewritten description, like any
    `Event`. `root` is the course root, as in `attach_resources`.
    """
    targets = {
        PurePosixPath(resource.path.relative_to(root).as_posix()): (
            f"/{discipline}/{course}/resources/{resource.slug}"
        )
        for resource in resources
    }
    return tuple(
        replace(event, description=rewrite_resource_links(event.description, targets))
        for event in events
    )


@dataclass(frozen=True)
class RepositoryLink:
    """
    A link target under `repositories/`: a repository, or a path inside it.
    """

    slug: str
    #: Path inside the repository, `None` for its root.
    path: PurePosixPath | None = None


def extract_repository_links(markdown: str) -> tuple[RepositoryLink, ...]:
    """
    List the targets of the markdown links that point under `repositories/`.

    Same rules as `extract_resource_links`: normalized (`./` dropped,
    percent-decoding applied, a trailing `/` ignored), in order of first
    appearance, code skipped, other links ignored. `repositories/lab1` and
    `repositories/lab1/src/main.py` both count.
    """
    raise NotImplementedError


def attach_repositories(
    events: Sequence[Event], repositories: Sequence[RepositoryTree]
) -> tuple[Event, ...]:
    """
    Return `events`, same order, with `repositories` set to the sorted slugs
    each lesson links.

    A link to a path inside a repository must name one of its files or a
    directory that holds some. One repository may be linked from many
    lessons. An event that links none keeps `repositories=()`.

    Raises:
        ResourceLinkError: A lesson links a slug that is not in
            `repositories`, or a path that is not in its tree.
    """
    raise NotImplementedError


def rewrite_repository_links(
    events: Sequence[Event], discipline: str, course: str
) -> tuple[Event, ...]:
    """
    Return `events`, same order, with every `repositories/` link rewritten to
    `/<discipline>/<course>/repositories/<slug>[/<path>]`.

    Link text and `#fragment` are kept; other links are untouched. Run it
    after `attach_repositories`, which validates the targets.
    """
    raise NotImplementedError


def _lesson(event: Event) -> str:
    return f"lesson {event.title!r} (week {event.week}, {event.time_slot})"


def _resources_target(raw: str) -> PurePosixPath | None:
    """
    The root-relative path a link target names under `resources/`, or
    `None` when it points anywhere else.
    """
    if "://" in raw or raw.startswith(("#", "/", "mailto:")):
        return None
    cleaned = unquote(raw.split("#", 1)[0].split("?", 1)[0])
    path = PurePosixPath(cleaned)
    if len(path.parts) < 2 or path.parts[0] != "resources" or ".." in path.parts:
        return None
    return path


#
# Markdown scanning
#

#: A fence opener: up to 3 spaces of indent, then 3 or more backticks or tildes.
FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")

#: A link reference definition on a single line.
DEFINITION_RE = re.compile(
    r"^ {0,3}\[(?P<label>(?:[^\]\\]|\\.)+)\]:[ \t]*"
    r"(?:<(?P<angle>[^>\n]*)>|(?P<plain>\S+))"
    r"(?:[ \t]+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?[ \t]*$"
)

Span = tuple[int, int]


def _link_targets(markdown: str) -> list[Span]:
    """
    The `(start, end)` span of the destination of every link in `markdown`,
    in document order and without duplicates.

    Inline links give their own destination. Reference links give the
    destination of their definition, once per definition. Code is skipped.
    """
    code, definitions, paragraphs = _code_mask(markdown)
    spans: set[Span] = set()
    defined: dict[str, Span] = {}
    definition_lines: set[int] = set()
    for line_start, line in definitions:
        match = DEFINITION_RE.match(line)
        if match is None:
            continue
        group = "angle" if match.group("angle") is not None else "plain"
        start, end = match.span(group)
        definition_lines.add(line_start)
        label = _normalize_label(match.group("label"))
        defined.setdefault(label, (line_start + start, line_start + end))

    used: set[str] = set()
    for first, last in paragraphs:
        i = first
        while i < last:
            if markdown[i] != "[" or code[i] or _escaped(markdown, i):
                i += 1
                continue
            close = _closing_bracket(markdown, code, i, last)
            if close is None:
                i += 1
                continue
            text = markdown[i + 1 : close]
            after = markdown[close + 1 : close + 2]
            if after == "(":
                span = _inline_target(markdown, close + 1, last)
                if span is not None:
                    spans.add(span)
            elif after == "[":
                label_end = _closing_bracket(markdown, code, close + 1, last)
                if label_end is not None:
                    label = markdown[close + 2 : label_end]
                    used.add(_normalize_label(label or text))
            elif not _is_definition_label(markdown, i, definition_lines):
                used.add(_normalize_label(text))
            i += 1
    spans.update(defined[label] for label in used if label in defined)
    return sorted(spans)


def _is_definition_label(markdown: str, index: int, definition_lines: set[int]) -> bool:
    """
    Whether the `[` at `index` opens the label of a definition line.
    """
    start = markdown.rfind("\n", 0, index) + 1
    return start in definition_lines


def _normalize_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def _escaped(text: str, index: int) -> bool:
    """
    Whether the character at `index` is backslash-escaped.
    """
    count = 0
    while index - count > 0 and text[index - count - 1] == "\\":
        count += 1
    return count % 2 == 1


def _closing_bracket(
    text: str, code: list[bool], opening: int, limit: int
) -> int | None:
    """
    The index of the `]` that closes the `[` at `opening`, or `None`.
    """
    depth = 0
    i = opening
    while i < limit:
        char = text[i]
        if code[i]:
            pass
        elif char == "\\":
            i += 1
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _inline_target(text: str, paren: int, limit: int) -> Span | None:
    """
    The span of the destination of the inline link whose `(` is at `paren`.
    """
    i = paren + 1
    while i < limit and text[i] in " \t\n":
        i += 1
    if i < limit and text[i] == "<":
        end = i + 1
        while end < limit and text[end] not in ">\n":
            end += 1
        return (i + 1, end) if end < limit and text[end] == ">" else None
    start = i
    depth = 0
    while i < limit:
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char.isspace():
            break
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        i += 1
    return (start, i) if depth == 0 and i > start else None


def _code_mask(markdown: str) -> tuple[list[bool], list[tuple[int, str]], list[Span]]:
    """
    Locate code in `markdown`.

    Returns:
        A per-character flag that is true inside fenced blocks and code
        spans, the `(offset, text)` of every line outside a fence, and the
        spans of the paragraphs (runs of non-blank lines outside fences).
    """
    code = [False] * len(markdown)
    lines: list[tuple[int, str]] = []
    paragraphs: list[Span] = []
    fence: tuple[str, int] | None = None
    para_start: int | None = None
    offset = 0
    for raw in markdown.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        end = offset + len(raw)
        if fence is not None:
            code[offset:end] = [True] * (end - offset)
            closer = FENCE_RE.match(line)
            if (
                closer is not None
                and closer.group("fence")[0] == fence[0]
                and len(closer.group("fence")) >= fence[1]
                and not closer.group("info").strip()
            ):
                fence = None
        else:
            opener = FENCE_RE.match(line)
            if opener is not None and not (
                opener.group("fence")[0] == "`" and "`" in opener.group("info")
            ):
                if para_start is not None:
                    paragraphs.append((para_start, offset))
                    para_start = None
                fence = (opener.group("fence")[0], len(opener.group("fence")))
                code[offset:end] = [True] * (end - offset)
            elif line.strip():
                lines.append((offset, line))
                if para_start is None:
                    para_start = offset
            elif para_start is not None:
                paragraphs.append((para_start, offset))
                para_start = None
        offset = end
    if para_start is not None:
        paragraphs.append((para_start, offset))
    for first, last in paragraphs:
        _mask_code_spans(markdown, code, first, last)
    return code, lines, paragraphs


def _mask_code_spans(text: str, code: list[bool], first: int, last: int) -> None:
    """
    Flag the code spans inside `text[first:last]`: a backtick run closed by
    the next run of the same length.
    """
    i = first
    while i < last:
        if text[i] == "\\":
            i += 2
        elif text[i] == "`":
            run = _backtick_run(text, i, last)
            j = i + run
            while j < last:
                if text[j] == "`":
                    other = _backtick_run(text, j, last)
                    if other == run:
                        code[i : j + other] = [True] * (j + other - i)
                        j += other
                        break
                    j += other
                else:
                    j += 1
            i = j if j > i + run and code[i] else i + run
        else:
            i += 1


def _backtick_run(text: str, index: int, limit: int) -> int:
    end = index
    while end < limit and text[end] == "`":
        end += 1
    return end - index
