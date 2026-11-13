"""
The base: what the last successful sync left on the server.

For each synced resource the base keeps the JSON payload the push sent, plus
the `rev` and `updatedAt` the server reported. Comparing local, base and
server tells who changed what since then. It lives in `.local/codehood/base/`,
one JSON file per collection.

`encode_collection` and `decode_collection` are the pure core; `load_base` and
`save_base` are the effects around them. Writes are atomic (temporary file in
the same directory, then `os.replace`), and a file that is missing, unreadable
or in an unknown format counts as an absent base for that collection, reported
through `BaseState.warnings` instead of an exception.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from ..repo import MACHINE_DIR, ensure_machine_dir

__all__ = [
    "COLLECTIONS",
    "FORMAT_VERSION",
    "BaseEntry",
    "BaseState",
    "JsonValue",
    "base_dir",
    "decode_collection",
    "encode_collection",
    "load_base",
    "save_base",
]

type JsonValue = (
    dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None
)

#: Version of the file format. A file with another version is an absent base.
FORMAT_VERSION = 1

#: Names of the `BaseState` collections, and of their files (`<name>.json`).
COLLECTIONS = (
    "course",
    "resources",
    "questions",
    "exams",
    "time_slots",
    "calendar_events",
    "grade_columns",
)

BASE_DIR = "base"


@dataclass(frozen=True)
class BaseEntry:
    """
    One resource as of the last successful sync.

    `payload` is the JSON body that was sent, in wire form. `updated_at` is the
    server's ISO timestamp, kept as text.
    """

    payload: dict[str, JsonValue]
    rev: str | None = None
    updated_at: str | None = None


@dataclass
class BaseState:
    """
    The base of every synced resource type, keyed by natural key.

    An empty `BaseState` is an absent base. Calendar events are keyed by a
    string the caller builds from the week and the time slot. `warnings` is
    filled by `load_base` and ignored by comparison and by `save_base`.
    """

    course: dict[str, BaseEntry] = field(default_factory=dict)
    resources: dict[str, BaseEntry] = field(default_factory=dict)
    questions: dict[str, BaseEntry] = field(default_factory=dict)
    exams: dict[str, BaseEntry] = field(default_factory=dict)
    time_slots: dict[str, BaseEntry] = field(default_factory=dict)
    calendar_events: dict[str, BaseEntry] = field(default_factory=dict)
    grade_columns: dict[str, BaseEntry] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default=(), compare=False)


def base_dir(root: Path) -> Path:
    """
    The directory that holds the base files of the repository at `root`.
    """
    return root / MACHINE_DIR / BASE_DIR


def encode_collection(entries: dict[str, BaseEntry]) -> str:
    """
    Serialize one collection to the text of its file.
    """
    document = {
        "version": FORMAT_VERSION,
        "entries": {
            key: {
                "payload": entry.payload,
                "rev": entry.rev,
                "updatedAt": entry.updated_at,
            }
            for key, entry in entries.items()
        },
    }
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def decode_collection(text: str, name: str) -> tuple[dict[str, BaseEntry], str | None]:
    """
    Parse the text of a collection file.

    Returns the entries and a warning. Text that is not valid, or has an
    unexpected shape or version, gives no entries and a warning naming `name`.
    """
    try:
        document = json.loads(text)
        if not isinstance(document, dict):
            raise TypeError("not an object")
        version = document.get("version")
        if version != FORMAT_VERSION:
            return {}, f"base '{name}': unknown format version {version!r}, ignored"
        raw = document.get("entries")
        if not isinstance(raw, dict):
            raise TypeError("'entries' is not an object")
        return {key: _decode_entry(value) for key, value in raw.items()}, None
    except (ValueError, TypeError) as exc:
        return {}, f"base '{name}': unreadable ({exc}), ignored"


def load_base(root: Path) -> BaseState:
    """
    Read the base of the repository at `root`.

    Never raises: a missing file is an empty collection without a warning, any
    other problem is an empty collection with one.
    """
    collections: dict[str, dict[str, BaseEntry]] = {}
    warnings: list[str] = []
    for name in COLLECTIONS:
        path = base_dir(root) / f"{name}.json"
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            collections[name] = {}
            continue
        except (OSError, UnicodeDecodeError) as exc:
            collections[name] = {}
            warnings.append(f"base '{name}': unreadable ({exc}), ignored")
            continue
        collections[name], warning = decode_collection(text, name)
        if warning is not None:
            warnings.append(warning)
    return BaseState(**collections, warnings=tuple(warnings))


def save_base(root: Path, state: BaseState) -> None:
    """
    Write every collection of `state`, each file atomically.

    A crash leaves each file either as it was or fully written, never partial.
    The `.gitignore` that keeps `.local/codehood/` out of git is created first
    when missing.
    """
    ensure_machine_dir(root)
    directory = base_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    for name in COLLECTIONS:
        write_atomic(
            directory / f"{name}.json", encode_collection(getattr(state, name))
        )


#
# Utilities
#


def write_atomic(path: Path, text: str) -> None:
    """
    Write `text` to `path` through a temporary file in the same directory.
    """
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _decode_entry(value: object) -> BaseEntry:
    if not isinstance(value, dict):
        raise TypeError("entry is not an object")
    payload = value.get("payload")
    rev = value.get("rev")
    updated_at = value.get("updatedAt")
    if not isinstance(payload, dict):
        raise TypeError("entry payload is not an object")
    if rev is not None and not isinstance(rev, str):
        raise TypeError("entry rev is not text")
    if updated_at is not None and not isinstance(updated_at, str):
        raise TypeError("entry updatedAt is not text")
    return BaseEntry(payload=payload, rev=rev, updated_at=updated_at)
