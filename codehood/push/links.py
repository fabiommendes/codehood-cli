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
from pathlib import Path, PurePosixPath
from dataclasses import replace
from urllib.parse import unquote

from .calendar import Event, EventKey
from .errors import ResourceLinkError
from .resource import ResourceFile, content_ref

__all__ = [
    "attach_resources",
    "extract_resource_links",
    "rewrite_event_links",
    "rewrite_resource_links",
]

#: An inline markdown link or image: `[text](target "title")`. Group
#: `target` is the destination, with optional `<...>` brackets.
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(?:<(?P<angle>[^>]*)>|(?P<plain>[^\s)]*))")


def extract_resource_links(markdown: str) -> tuple[PurePosixPath, ...]:
    """
    List the targets of the markdown links that point under `resources/`.

    Targets are returned relative to the course root, normalized (a leading
    `./` is dropped), in order of first appearance. Links to anything else
    (http URLs, other paths, `#anchors`) are ignored.
    """
    found: dict[PurePosixPath, None] = {}
    for match in LINK_RE.finditer(markdown):
        target = _resources_target(match.group("angle") or match.group("plain") or "")
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
    """

    def replace_target(match: re.Match[str]) -> str:
        group = "angle" if match.group("angle") is not None else "plain"
        raw = match.group(group) or ""
        target = _resources_target(raw)
        url = targets.get(target) if target is not None else None
        if url is None:
            return match.group(0)
        fragment = f"#{raw.split('#', 1)[1]}" if "#" in raw else ""
        start, end = match.span(group)
        offset = match.start()
        whole = match.group(0)
        return whole[: start - offset] + url + fragment + whole[end - offset :]

    return LINK_RE.sub(replace_target, markdown)


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
