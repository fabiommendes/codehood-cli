"""
The pure core that turns files under `resources/` into `ResourceFile`s.

Nothing here touches the network or the server's idea of what it holds --
see `plan.py` for that half. A `ResourceFile` carries everything a
`push.plan.UpsertResource` needs, including the `ref` the server stores
verbatim and hands back on the next read, so the core can diff two of
these by comparing strings.

The `ResourceData` union mirrors the server's own tagged union on
`Resource.data` without importing it: the core stays independent of
`api/generated.py`, and `push/run.py` translates one into the other.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from ..repo.diff import FileType
from ..repo.file_tracker import scan_files
from .calendar import EventKey
from .errors import SlugCollisionError

__all__ = [
    "ResourceFile",
    "ResourceData",
    "MdData",
    "CodeData",
    "FileData",
    "slugify",
    "content_ref",
    "scan_resources",
]

#: `.md`/`.markdown` files become `MD` resources -- see `push.md`, "Type is
#: inferred from the extension".
MD_SUFFIXES = (".md", ".markdown")

#: Extension -> the language a `CODE` resource reports. No manifest to
#: declare this explicitly yet (see `BACKLOG.md`, "Resource manifest"), so
#: this is a reasonable-effort table, not a spec-pinned one.
CODE_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "bash",
    ".bash": "bash",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".kt": "kotlin",
    ".swift": "swift",
    ".scala": "scala",
    ".r": "r",
    ".pl": "perl",
    ".lua": "lua",
    ".hs": "haskell",
}

#: Any run of characters outside this set collapses to a single `-` in a
#: slug -- see `push.md`, "A resource's slug is its flattened path".
SLUG_INVALID_RUN = re.compile(r"[^a-z0-9._-]+")

H1_RE = re.compile(r"^#\s+(.+?)\s*$")

#: Leads every `ref` this CLI writes. `ref` is a free-form string the
#: server stores and returns untouched, so its meaning is entirely ours;
#: the prefix says which recipe produced the digest, so changing the recipe
#: later invalidates old refs loudly instead of colliding with them.
REF_PREFIX = "v1"


@dataclass(frozen=True)
class MdData:
    """
    A Markdown resource's body, front matter already stripped.
    """

    content: str
    type: Literal["MD"] = "MD"


@dataclass(frozen=True)
class CodeData:
    """
    A source file's text, plus the language the server highlights it as.
    """

    content: str
    language: str
    type: Literal["CODE"] = "CODE"


@dataclass(frozen=True)
class FileData:
    """
    An opaque file's bytes, uploaded whole under `filename`.
    """

    filename: str
    blob: bytes
    type: Literal["FILE"] = "FILE"


#: What a resource holds, tagged the way the server tags it. `LINK` is
#: absent: a link has no file to scan, so it cannot exist until the
#: resource manifest does (see `BACKLOG.md`).
type ResourceData = MdData | CodeData | FileData


@dataclass(frozen=True)
class ResourceFile:
    """
    One file under `resources/`, already typed, titled, and hashed.
    """

    slug: str
    title: str
    description: str | None
    data: ResourceData
    ref: str
    path: Path
    event: EventKey | None = None


def slugify(rel_path: Path) -> str:
    """
    Flatten a path under `resources/` into the slug the server stores.

    Drops the extension, lowercases, replaces every run of characters
    outside `[a-z0-9._-]` with a single `-`, and strips leading and
    trailing `-`. `week1/Slides (final).pdf` becomes `week1-slides-final`.
    """
    stem_path = rel_path.with_suffix("")
    flattened = "-".join(stem_path.parts).lower()
    flattened = SLUG_INVALID_RUN.sub("-", flattened)
    return flattened.strip("-")


def content_ref(
    title: str,
    description: str | None,
    data: ResourceData,
    event: EventKey | None = None,
) -> str:
    """
    Digest a resource's pushable fields into the `ref` the server stores.

    Sha-256, hex, over a canonical JSON rendering of `{v, title,
    description, data}` with no whitespace, prefixed by `REF_PREFIX`. Two
    resources with the same ref are the same resource, which is the whole
    basis on which `plan_push` decides not to push one again -- so the
    rendering has to be stable across runs, machines, and Python versions.

    A `FILE`'s bytes are digested separately and only their hex digest
    enters the rendering, keeping the payload small and JSON-safe.

    The event key the resource is attached to is part of the digest, so
    moving a resource to another lesson changes its ref. With `event=None`
    the digest MUST stay byte-identical to the one computed before events
    existed (existing refs and test vectors stay valid): add the key to the
    rendering only when it is not `None`.
    """
    payload: dict[str, object] = {
        "v": REF_PREFIX,
        "title": title,
        "description": description,
        "data": _data_payload(data),
    }
    if event is not None:
        payload["event"] = {"week": event.week, "timeSlot": event.time_slot}
    canonical = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{REF_PREFIX}:{digest}"


def scan_resources(root: Path, exclude: Sequence[str] = ()) -> Iterator[ResourceFile]:
    """
    Walk `resources/` and yield one `ResourceFile` per file.

    Reuses the (fixed) `repo.file_tracker.scan_files` for the walk, so a
    subdirectory never becomes a resource of its own. Files matching an
    `exclude` pattern are skipped without being read.

    Raises:
        SlugCollisionError: two or more files flatten to the same slug.
            Raised eagerly, before any file is read or any network call is
            made.
    """
    base = root / "resources"
    by_slug: dict[str, list[Path]] = defaultdict(list)
    entries: list[tuple[str, Path]] = []

    for file in scan_files(root, exclude):
        if file.type is not FileType.RESOURCE or file.excluded:
            continue
        rel_path = Path(file.name)
        slug = slugify(rel_path)
        by_slug[slug].append(rel_path)
        entries.append((slug, rel_path))

    collisions = {slug: paths for slug, paths in by_slug.items() if len(paths) > 1}
    if collisions:
        raise SlugCollisionError(collisions)

    for slug, rel_path in entries:
        yield _read_resource(base, slug, rel_path)


#
# Utilities
#
def _data_payload(data: ResourceData) -> dict[str, str]:
    """
    One resource's data as the flat, JSON-safe mapping `content_ref`
    digests.
    """
    match data:
        case MdData(content=content):
            return {"type": data.type, "content": content}
        case CodeData(content=content, language=language):
            return {"type": data.type, "content": content, "language": language}
        case FileData(filename=filename, blob=blob):
            return {
                "type": data.type,
                "filename": filename,
                "blob": hashlib.sha256(blob).hexdigest(),
            }


def _read_resource(base: Path, slug: str, rel_path: Path) -> ResourceFile:
    """
    Read one resource file off disk and infer its type, title, and ref.
    """
    path = base / rel_path
    suffix = path.suffix.lower()

    if suffix in MD_SUFFIXES:
        return _read_md_resource(path, slug)
    if suffix in CODE_LANGUAGES:
        return _read_code_resource(path, slug, CODE_LANGUAGES[suffix])
    return _read_file_resource(path, slug)


def _read_md_resource(path: Path, slug: str) -> ResourceFile:
    raw = path.read_text(encoding="utf-8")
    front_matter, body = _split_front_matter(raw)
    title = _front_matter_str(front_matter, "title") or _first_h1(body) or path.stem
    description = _front_matter_str(front_matter, "description")
    return _build(slug, title, description, MdData(content=body), path)


def _read_code_resource(path: Path, slug: str, language: str) -> ResourceFile:
    data = CodeData(content=path.read_text(encoding="utf-8"), language=language)
    return _build(slug, path.stem, None, data, path)


def _read_file_resource(path: Path, slug: str) -> ResourceFile:
    data = FileData(filename=path.name, blob=path.read_bytes())
    return _build(slug, path.stem, None, data, path)


def _build(
    slug: str,
    title: str,
    description: str | None,
    data: ResourceData,
    path: Path,
) -> ResourceFile:
    """
    Assemble a `ResourceFile`, deriving its `ref` from the rest.
    """
    return ResourceFile(
        slug=slug,
        title=title,
        description=description,
        data=data,
        ref=content_ref(title, description, data),
        path=path,
    )


def _split_front_matter(text: str) -> tuple[dict[str, object], str]:
    """
    Split a Markdown file's leading `---`-delimited YAML front matter from
    its body.

    Returns `({}, text)` unchanged when there is no front matter, or the
    front matter fails to parse as a YAML mapping.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() != "---":
            continue
        front_matter_text = "".join(lines[1:index])
        body = "".join(lines[index + 1 :]).lstrip("\n")
        try:
            data = yaml.safe_load(front_matter_text)
        except yaml.YAMLError:
            return {}, text
        if not isinstance(data, dict):
            return {}, text
        return data, body
    return {}, text


def _front_matter_str(front_matter: dict[str, object], key: str) -> str | None:
    value = front_matter.get(key)
    return None if value is None else str(value)


def _first_h1(body: str) -> str | None:
    for line in body.splitlines():
        match = H1_RE.match(line)
        if match:
            return match.group(1)
    return None
