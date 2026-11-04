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
import unicodedata
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import takewhile
from pathlib import Path
from typing import Literal

import yaml

from ..repo.diff import FileType
from ..repo.file_tracker import scan_files
from .calendar import EventKey
from .errors import ResourceFileError, SlugCollisionError

__all__ = [
    "INFO_FILE",
    "README_SLUG",
    "CodeData",
    "FileData",
    "LinkData",
    "MdData",
    "ResourceData",
    "ResourceFile",
    "content_ref",
    "read_readme",
    "resource_slug",
    "scan_resources",
    "slugify",
    "slugify_text",
    "title_from_filename",
]

#: `.md`/`.markdown` files become `MD` resources -- see `push.md`, "Type is
#: inferred from the extension".
MD_SUFFIXES = (".md", ".markdown")

#: `.url` files become `LINK` resources, read as a text/uri-list.
LINK_SUFFIX = ".url"

#: The per-directory metadata file: never a resource itself.
INFO_FILE = "info.yaml"

#: The slug the course README pushes under, as an `MD` resource.
README_SLUG = "readme"

#: Keys an `info.yaml` entry may set.
INFO_KEYS = frozenset({"title", "description", "language", "mime"})

#: Extension -> the language a `CODE` resource reports. An `info.yaml`
#: `language` overrides it, so this is a reasonable-effort table, not a
#: spec-pinned one.
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

#: The combining marks NFKD splits off accented Latin letters; the server's
#: `src/utils/slugify.ts` strips the same range.
COMBINING_MARKS = re.compile("[\u0300-\u036f]")

#: Where a file name splits into words for its fallback title: hyphens,
#: underscores, whitespace, and camel case humps.
TITLE_WORD_BREAK = re.compile(
    r"[-_\s]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)

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

    @property
    def sha256(self) -> str:
        """
        The hex sha-256 of `blob`, the name the server stores it under.
        """
        return hashlib.sha256(self.blob).hexdigest()


@dataclass(frozen=True)
class LinkData:
    """
    An external `http(s)` URL, read from a `.url` file.
    """

    url: str
    type: Literal["LINK"] = "LINK"


#: What a resource holds, tagged the way the server tags it.
type ResourceData = MdData | CodeData | FileData | LinkData


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


def resource_slug(rel_path: Path) -> str:
    """
    The slug a file under `resources/` pushes under: `slugify`, keeping the
    extension of anything but Markdown.

    `aabb.py` and `aabb.png` in one folder are two resources, `aabb.py` and
    `aabb.png`, while `notas.md` stays `notas`, so a lesson's page reads
    like a page. `week1/Slides (final).PDF` becomes `week1-slides-final.pdf`.
    """
    if rel_path.suffix.lower() in MD_SUFFIXES or not rel_path.suffix:
        return slugify(rel_path)
    return slugify(rel_path) + slugify_text(rel_path.suffix)


def slugify(rel_path: Path) -> str:
    """
    Flatten a path into a slug without its extension.

    Joins the parts with `-`, then applies `slugify_text`.
    `week1/Slides (final).pdf` becomes `week1-slides-final` and
    `laços/herança.md` becomes `lacos-heranca`.
    """
    return slugify_text("-".join(rel_path.with_suffix("").parts))


def slugify_text(text: str) -> str:
    """
    Turn free text into a slug: accents dropped, lowercase, runs outside
    `[a-z0-9._-]` collapsed to `-`, no leading or trailing `-`.

    Accents go the way the server's `src/utils/slugify.ts` drops them: NFKD,
    then the combining marks removed. Letters NFKD does not decompose (`ß`,
    `æ`, `ø`) are not transliterated and become `-`, as on the server.
    """
    plain = COMBINING_MARKS.sub("", unicodedata.normalize("NFKD", text))
    return SLUG_INVALID_RUN.sub("-", plain.lower()).strip("-")


def title_from_filename(stem: str) -> str:
    """
    The fallback title of a file: its name split on hyphens, underscores
    and camel case, each word capitalised.

    `janela-minima` becomes `Janela Minima` and `bigONotation` becomes
    `Big O Notation`. Letters after the first keep their case, so `PDF`
    stays `PDF`.
    """
    words = [word for word in TITLE_WORD_BREAK.split(stem) if word]
    return " ".join(word[:1].upper() + word[1:] for word in words) or stem


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
    `exclude` pattern are skipped without being read. An `info.yaml` is
    read as the metadata of its directory's files, not pushed.

    Raises:
        SlugCollisionError: two or more files flatten to the same slug.
            Raised eagerly, before any file is read or any network call is
            made.
        ResourceFileError: an `info.yaml` or a `.url` file is malformed.
    """
    base = root / "resources"
    by_slug: dict[str, list[Path]] = defaultdict(list)
    entries: list[tuple[str, Path]] = []
    info_dirs: set[Path] = set()

    for file in scan_files(root, exclude):
        if file.type is not FileType.RESOURCE or file.excluded:
            continue
        rel_path = Path(file.name)
        if rel_path.name == INFO_FILE:
            info_dirs.add(rel_path.parent)
            continue
        slug = resource_slug(rel_path)
        by_slug[slug].append(rel_path)
        entries.append((slug, rel_path))

    collisions = {slug: paths for slug, paths in by_slug.items() if len(paths) > 1}
    if collisions:
        raise SlugCollisionError(collisions)

    infos = {folder: read_info(base / folder / INFO_FILE) for folder in info_dirs}
    for slug, rel_path in entries:
        info = infos.get(rel_path.parent, {}).get(rel_path.name, ResourceInfo())
        yield read_resource(base, slug, rel_path, info)


def read_readme(path: Path, *, describes_course: bool) -> ResourceFile | None:
    """
    Read the course README as the `MD` resource `README_SLUG`, titled by its
    H1 and without it, or `None` when it would add nothing.

    The course has no room for more than a short description, so the rest of
    the README (grading, bibliography, policies) goes up as a resource. When
    its first paragraph `describes_course`, a README holding only that
    paragraph is `None`, since the course already shows it.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = "README"
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            lines = lines[index + 1 :]
        break
    content = "\n".join(lines).strip()
    first_paragraph = "\n".join(
        takewhile(
            lambda line: line.strip() and not line.startswith("#"),
            content.splitlines(),
        )
    )
    if not content or (describes_course and content == first_paragraph):
        return None
    data = MdData(content=content + "\n")
    return ResourceFile(
        slug=README_SLUG,
        title=title,
        description=None,
        data=data,
        ref=content_ref(title, None, data),
        path=path,
    )


#
# Utilities
#
@dataclass(frozen=True)
class ResourceInfo:
    """
    One file's entry in its directory's `info.yaml`; `None` means unset.
    """

    title: str | None = None
    description: str | None = None
    #: Forces `CODE`, highlighted as this language.
    language: str | None = None
    #: Forces `FILE`. The server derives the served type from the filename,
    #: so the value itself is not sent.
    mime: str | None = None


def read_info(path: Path) -> dict[str, ResourceInfo]:
    """
    Parse an `info.yaml` into each named file's `ResourceInfo`.

    Raises:
        ResourceFileError: the file is not a YAML mapping of file names to
            mappings, an entry uses a key outside `INFO_KEYS` or a value
            that is not a string, or it names a file that does not exist.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ResourceFileError(path, f"not valid YAML: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ResourceFileError(path, "expected a mapping of file names")
    infos: dict[str, ResourceInfo] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise ResourceFileError(path, f"{name!r}: expected a mapping")
        unknown = set(entry) - INFO_KEYS
        if unknown:
            keys = ", ".join(sorted(map(str, unknown)))
            raise ResourceFileError(path, f"{name!r}: unknown keys {keys}")
        if not all(isinstance(value, str) for value in entry.values()):
            raise ResourceFileError(path, f"{name!r}: values must be strings")
        if not (path.parent / str(name)).is_file():
            raise ResourceFileError(path, f"{name!r}: no such file in this folder")
        infos[str(name)] = ResourceInfo(**entry)
    return infos


def read_resource(
    base: Path, slug: str, rel_path: Path, info: ResourceInfo
) -> ResourceFile:
    """
    Read one resource file off disk and infer its type, title, and ref.

    The type comes from the extension unless `info` forces one; `info`'s
    title and description win over anything the file declares, and the
    file name is the last resort for the title.

    Raises:
        ResourceFileError: a `.url` file holds no `http(s)` URI.
    """
    path = base / rel_path
    suffix = path.suffix.lower()
    title: str | None = None
    description: str | None = None
    data: ResourceData

    if info.mime is not None:
        data = FileData(filename=path.name, blob=path.read_bytes())
    elif info.language is not None:
        data = CodeData(
            content=path.read_text(encoding="utf-8"), language=info.language
        )
    elif suffix in MD_SUFFIXES:
        front_matter, body = split_front_matter(path.read_text(encoding="utf-8"))
        title = front_matter_str(front_matter, "title") or first_h1(body)
        description = front_matter_str(front_matter, "description")
        data = MdData(content=body)
    elif suffix == LINK_SUFFIX:
        url, title, description = read_uri_list(path)
        data = LinkData(url=url)
    elif suffix in CODE_LANGUAGES:
        content = path.read_text(encoding="utf-8")
        data = CodeData(content=content, language=CODE_LANGUAGES[suffix])
    else:
        data = FileData(filename=path.name, blob=path.read_bytes())

    title = info.title or title or title_from_filename(path.stem)
    description = info.description if info.description is not None else description
    return ResourceFile(
        slug=slug,
        title=title,
        description=description,
        data=data,
        ref=content_ref(title, description, data),
        path=path,
    )


def read_uri_list(path: Path) -> tuple[str, str | None, str | None]:
    """
    Read a text/uri-list into its first URI, title and description.

    The first comment line is the title and the remaining ones, joined by
    newlines, the description; each loses its `#` and surrounding
    whitespace, and blank ones are dropped.

    Raises:
        ResourceFileError: the file has no URI, or the first one is not
            `http(s)`, the only kind the server accepts for a `LINK`.
    """
    comments: list[str] = []
    uris: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            comment = stripped[1:].strip()
            if comment:
                comments.append(comment)
        elif stripped:
            uris.append(stripped)
    if not uris:
        raise ResourceFileError(path, "no URI in this text/uri-list")
    if not re.match(r"https?://", uris[0], re.IGNORECASE):
        raise ResourceFileError(path, f"{uris[0]!r} is not an http(s) URL")
    title = comments[0] if comments else None
    description = "\n".join(comments[1:]) or None
    return uris[0], title, description


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
        case FileData(filename=filename):
            return {"type": data.type, "filename": filename, "blob": data.sha256}
        case LinkData(url=url):
            return {"type": data.type, "url": url}


def split_front_matter(text: str) -> tuple[dict[str, object], str]:
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


def front_matter_str(front_matter: dict[str, object], key: str) -> str | None:
    value = front_matter.get(key)
    return None if value is None else str(value)


def first_h1(body: str) -> str | None:
    for line in body.splitlines():
        match = H1_RE.match(line)
        if match:
            return match.group(1)
    return None
