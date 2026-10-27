"""
The pure core that turns `calendar.md` into TimeSlots and CalendarEvents.

Two steps, both side-effect free: `parse_calendar` reads the file into a
`Calendar` and nothing more, and `allocate` walks the course's date range
handing each h2 section a date. Neither knows the network, the clock, or
the server's idea of what it holds -- see `plan.py` for that half, and
`docs/design/mapping-local-filesystem.md`, "Calendar", for the mapping
this implements.

Every case the mapping calls a warning comes back in
`Allocation.warnings` rather than going to `warnings.warn`, so the whole
allocation is one comparable value.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import groupby
from typing import Literal

import yaml

from .errors import CalendarError

__all__ = [
    "Allocation",
    "Calendar",
    "Duration",
    "Event",
    "EventKey",
    "EventKind",
    "Holiday",
    "Section",
    "TimeOfDay",
    "TimeSlot",
    "Weekday",
    "allocate",
    "parse_calendar",
]

#: The weekday names the server's enum uses, in its own order.
type Weekday = Literal[
    "SUNDAY",
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
]

#: The kinds a push writes. `CANCELLED` is set server-side by an
#: instructor and has no local spelling -- see the mapping's "Calendar
#: events".
type EventKind = Literal["REGULAR", "HOLIDAY"]

#: Weekday spellings a `days:`/`## Title` entry may use, keyed
#: case-insensitively, both the three-letter abbreviation and the full name.
_WEEKDAY_ALIASES: dict[str, Weekday] = {
    "sun": "SUNDAY",
    "sunday": "SUNDAY",
    "mon": "MONDAY",
    "monday": "MONDAY",
    "tue": "TUESDAY",
    "tuesday": "TUESDAY",
    "wed": "WEDNESDAY",
    "wednesday": "WEDNESDAY",
    "thu": "THURSDAY",
    "thursday": "THURSDAY",
    "fri": "FRIDAY",
    "friday": "FRIDAY",
    "sat": "SATURDAY",
    "saturday": "SATURDAY",
}

#: The three-letter slug a `TimeSlot` uses before any collision suffix.
_WEEKDAY_SLUG: dict[Weekday, str] = {
    "SUNDAY": "sun",
    "MONDAY": "mon",
    "TUESDAY": "tue",
    "WEDNESDAY": "wed",
    "THURSDAY": "thu",
    "FRIDAY": "fri",
    "SATURDAY": "sat",
}

#: ISO weekday number (Monday=1 .. Sunday=7), the order `days:` sorts by.
_WEEKDAY_ISO: dict[Weekday, int] = {
    "MONDAY": 1,
    "TUESDAY": 2,
    "WEDNESDAY": 3,
    "THURSDAY": 4,
    "FRIDAY": 5,
    "SATURDAY": 6,
    "SUNDAY": 7,
}

#: `date.weekday()` (Monday=0 .. Sunday=6) to `Weekday`.
_PY_WEEKDAY: tuple[Weekday, ...] = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
)

_DAYS_ENTRY_RE = re.compile(
    r"^\s*(?P<day>\S+)\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+"
    r"(?P<duration>\S+)\s*,\s*(?P<title>.*?)\s*$"
)
_DURATION_RE = re.compile(r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?$")
_SECTION_RE = re.compile(
    r"^##[ \t]+(?P<title>.+?)(?:\s*\((?P<date>\d{4}-\d{2}-\d{2})\))?\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class TimeOfDay:
    """
    A wall-clock time of day, as the server's `start` object spells it.
    """

    hour: int
    minute: int


@dataclass(frozen=True)
class Duration:
    """
    A length of time, as the server's `duration` object spells it.
    """

    hours: int
    minutes: int


@dataclass(frozen=True)
class TimeSlot:
    """
    One recurring weekly slot, from a single `days:` entry.
    """

    slug: str
    day: Weekday
    start: TimeOfDay
    duration: Duration
    title: str | None = None

    @property
    def ref(self) -> str:
        """
        The md5 digest of this slot's pushable fields.

        The server stores no `ref` for a time slot, so this is computed on
        both sides of the diff -- see `run.fetch_server_state`.
        """
        canonical = json.dumps(
            {
                "slug": self.slug,
                "day": self.day,
                "start": {"hour": self.start.hour, "minute": self.start.minute},
                "duration": {
                    "hours": self.duration.hours,
                    "minutes": self.duration.minutes,
                },
                "title": self.title,
            },
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.md5(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Holiday:
    """
    One `holidays:` entry: a `Month, Day, Title` with the year left out.
    """

    month: int
    day: int
    title: str


@dataclass(frozen=True)
class Section:
    """
    One h2 section of `calendar.md`, before any date is assigned to it.
    """

    title: str
    description: str
    fixed_date: date | None = None


@dataclass(frozen=True)
class Calendar:
    """
    `calendar.md`, parsed and nothing more.
    """

    start: date
    end: date
    slots: tuple[TimeSlot, ...] = ()
    holidays: tuple[Holiday, ...] = ()
    sections: tuple[Section, ...] = ()


@dataclass(frozen=True)
class EventKey:
    """
    The `(week, timeSlot)` natural key that names one CalendarEvent.
    """

    week: int
    time_slot: str


@dataclass(frozen=True)
class Event:
    """
    One CalendarEvent, keyed the way the server keys it.

    `time_slot` is a `TimeSlot.slug`, not a `TimeSlot`: `(week,
    timeSlot)` is the server's primary key and its URL, so the plan
    carries exactly that pair and nothing downstream re-derives it.
    """

    week: int
    time_slot: str
    title: str
    description: str = ""
    kind: EventKind = "REGULAR"
    #: Slugs of the repositories the lesson links, sorted, without repeats.
    repositories: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        """
        `md5(f"{title}#{description}")`, per the mapping.

        With repositories, their sorted slugs also enter the digest, so
        linking or unlinking one re-sends the event. Without them the digest
        stays the old one, so existing refs do not change.
        """
        text = f"{self.title}#{self.description}"
        if self.repositories:
            text += "#repositories:" + ",".join(sorted(self.repositories))
        digest = text.encode("utf-8")
        return hashlib.md5(digest).hexdigest()


@dataclass(frozen=True)
class Allocation:
    """
    Every event a calendar yields, plus what the instructor should know.
    """

    events: tuple[Event, ...] = ()
    warnings: tuple[str, ...] = ()


def parse_calendar(text: str) -> Calendar:
    """
    Parse `calendar.md` into a `Calendar`.

    Raises:
        CalendarError: The frontmatter is missing or malformed, `start` or
            `end` is absent, `end` precedes `start`, or a `days:`/
            `holidays:` entry does not parse.
    """
    front_matter, body = _split_front_matter(text)

    start = _parse_date_field(front_matter, "start")
    end = _parse_date_field(front_matter, "end")
    if end < start:
        raise CalendarError(f"end ({end}) precedes start ({start})")

    raw_days = front_matter.get("days") or []
    if not isinstance(raw_days, list):
        raise CalendarError("`days:` must be a list")
    slots = _parse_time_slots(raw_days)

    raw_holidays = front_matter.get("holidays") or []
    if not isinstance(raw_holidays, list):
        raise CalendarError("`holidays:` must be a list")
    holidays = tuple(_parse_holiday(entry) for entry in raw_holidays)

    sections = _parse_sections(body)

    return Calendar(
        start=start,
        end=end,
        slots=slots,
        holidays=holidays,
        sections=sections,
    )


def allocate(calendar: Calendar) -> Allocation:
    """
    Hand every h2 section a date, and every holiday that lands on a slot
    an event of its own.

    Raises:
        CalendarError: A holiday's `Month, Day` matches two dates inside
            the course's range, which only the instructor can resolve.
    """
    warnings: list[str] = []

    # 1. Every (date, slot) candidate pair in range, in canonical order.
    candidates: list[tuple[date, TimeSlot]] = []
    day = calendar.start
    while day <= calendar.end:
        weekday = _PY_WEEKDAY[day.weekday()]
        for slot in calendar.slots:
            if slot.day == weekday:
                candidates.append((day, slot))
        day += timedelta(days=1)
    candidates.sort(
        key=lambda pair: (
            pair[0],
            pair[1].start.hour,
            pair[1].start.minute,
            pair[1].slug,
        )
    )

    # 2. Resolve every holiday against the whole date range (not just the
    #    dates that carry a slot).
    holiday_by_date: dict[date, Holiday] = {}
    for holiday in calendar.holidays:
        matches = [
            candidate
            for candidate in _date_range(calendar.start, calendar.end)
            if candidate.month == holiday.month and candidate.day == holiday.day
        ]
        if not matches:
            warnings.append(
                f"holiday {holiday.title!r} ({holiday.month}/{holiday.day}) "
                "matches no date in the course's range"
            )
            continue
        if len(matches) > 1:
            raise CalendarError(
                f"holiday {holiday.title!r} ({holiday.month}/{holiday.day}) "
                f"matches more than one date in the course's range: {matches}"
            )
        holiday_by_date[matches[0]] = holiday

    # 3. Drop holiday pairs; each becomes its own HOLIDAY event.
    emitted: list[tuple[date, TimeSlot, EventKind, str, str]] = []
    pool: list[tuple[date, TimeSlot]] = []
    for candidate_date, slot in candidates:
        matched_holiday = holiday_by_date.get(candidate_date)
        if matched_holiday is not None:
            emitted.append((candidate_date, slot, "HOLIDAY", matched_holiday.title, ""))
        else:
            pool.append((candidate_date, slot))

    # 4. Resolve fixed sections first; everything else queues sequentially.
    queue: list[Section] = []
    for section in calendar.sections:
        if section.fixed_date is None:
            queue.append(section)
            continue

        fixed_date = section.fixed_date
        index = None
        if (
            calendar.start <= fixed_date <= calendar.end
            and fixed_date not in holiday_by_date
        ):
            for candidate_index, (candidate_date, _slot) in enumerate(pool):
                if candidate_date == fixed_date:
                    index = candidate_index
                    break

        if index is None:
            warnings.append(
                f"section {section.title!r} has an invalid fixed date "
                f"({fixed_date}) and rejoins the sequential queue"
            )
            queue.append(section)
            continue

        candidate_date, slot = pool.pop(index)
        emitted.append(
            (candidate_date, slot, "REGULAR", section.title, section.description)
        )

    # 5. Assign the remaining sections, in file order, to the remaining
    #    pairs, in chronological order.
    allocated = min(len(queue), len(pool))
    for index in range(allocated):
        candidate_date, slot = pool[index]
        section = queue[index]
        emitted.append(
            (candidate_date, slot, "REGULAR", section.title, section.description)
        )

    if len(pool) > allocated:
        warnings.append(f"{len(pool) - allocated} date(s) left unallocated")
    if len(queue) > allocated:
        warnings.append(f"{len(queue) - allocated} section(s) truncated: no dates left")

    if not emitted:
        return Allocation(events=(), warnings=tuple(warnings))

    # 6. `week` is the ISO-week distance from the earliest emitted event.
    earliest = min(item[0] for item in emitted)
    earliest_monday = _iso_week_start(earliest)

    emitted.sort(
        key=lambda item: (
            item[0],
            item[1].start.hour,
            item[1].start.minute,
            item[1].slug,
        )
    )
    events = tuple(
        Event(
            week=(_iso_week_start(event_date) - earliest_monday).days // 7,
            time_slot=slot.slug,
            title=title,
            description=description,
            kind=kind,
        )
        for event_date, slot, kind, title, description in emitted
    )
    return Allocation(events=events, warnings=tuple(warnings))


#
# Utilities
#
def _split_front_matter(text: str) -> tuple[dict[str, object], str]:
    """
    Split `calendar.md`'s leading `---`-delimited YAML front matter from
    its body.

    Raises:
        CalendarError: There is no front matter, or it fails to parse as a
            YAML mapping.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise CalendarError("calendar.md has no front matter")
    for index in range(1, len(lines)):
        if lines[index].strip() != "---":
            continue
        front_matter_text = "".join(lines[1:index])
        body = "".join(lines[index + 1 :]).lstrip("\n")
        try:
            data = yaml.safe_load(front_matter_text)
        except yaml.YAMLError as exc:
            raise CalendarError(f"malformed front matter: {exc}") from exc
        if not isinstance(data, dict):
            raise CalendarError("front matter must be a YAML mapping")
        return data, body
    raise CalendarError("calendar.md's front matter is never closed")


def _parse_date_field(front_matter: dict[str, object], key: str) -> date:
    """
    Read a `date`-valued front matter field, accepting both the `date`
    object YAML already parses and a plain ISO string.

    Raises:
        CalendarError: The field is absent or does not parse as a date.
    """
    value = front_matter.get(key)
    if value is None:
        raise CalendarError(f"calendar.md's front matter has no `{key}:`")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CalendarError(f"`{key}: {value!r}` is not a valid date") from exc
    raise CalendarError(f"`{key}: {value!r}` is not a valid date")


def _parse_time_slots(raw_days: list[object]) -> tuple[TimeSlot, ...]:
    """
    Parse every `days:` entry into a `TimeSlot`, sorted by ISO weekday then
    start time, with slugs assigned (and suffixed on collision) afterward.

    Raises:
        CalendarError: An entry does not match `WeekDay HH:MM Duration,
            Title`.
    """
    parsed: list[tuple[Weekday, TimeOfDay, Duration, str | None]] = []
    for entry in raw_days:
        parsed.append(_parse_time_slot_entry(str(entry)))

    parsed.sort(key=lambda item: (_WEEKDAY_ISO[item[0]], item[1].hour, item[1].minute))

    slots: list[TimeSlot] = []
    for weekday, group in groupby(parsed, key=lambda item: item[0]):
        entries = list(group)
        base_slug = _WEEKDAY_SLUG[weekday]
        collision = len(entries) > 1
        for day, start, duration, title in entries:
            slug = (
                f"{base_slug}-{start.hour:02d}_{start.minute:02d}"
                if collision
                else base_slug
            )
            slots.append(
                TimeSlot(
                    slug=slug, day=day, start=start, duration=duration, title=title
                )
            )
    return tuple(slots)


def _parse_time_slot_entry(
    entry: str,
) -> tuple[Weekday, TimeOfDay, Duration, str | None]:
    match = _DAYS_ENTRY_RE.match(entry)
    if match is None:
        raise CalendarError(
            f"`days:` entry {entry!r} is not `WeekDay HH:MM Duration, Title`"
        )

    weekday = _WEEKDAY_ALIASES.get(match.group("day").lower())
    if weekday is None:
        raise CalendarError(f"`days:` entry {entry!r} has an unknown weekday")

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))

    duration_match = _DURATION_RE.match(match.group("duration"))
    if duration_match is None or not _duration_has_value(duration_match):
        raise CalendarError(f"`days:` entry {entry!r} has an invalid duration")
    hours = int(duration_match.group("hours") or 0)
    minutes = int(duration_match.group("minutes") or 0)

    title = match.group("title").strip() or None
    return (
        weekday,
        TimeOfDay(hour=hour, minute=minute),
        Duration(hours=hours, minutes=minutes),
        title,
    )


def _duration_has_value(match: re.Match[str]) -> bool:
    """
    Whether a duration match captured at least one of `hours`/`minutes`.
    """
    return match.group("hours") is not None or match.group("minutes") is not None


def _parse_holiday(entry: object) -> Holiday:
    """
    Parse one `holidays:` entry, `Month, Day, Title`.

    Raises:
        CalendarError: The entry does not split into three parts, or the
            month/day do not parse.
    """
    text = str(entry)
    parts = [part.strip() for part in text.split(",", 2)]
    if len(parts) != 3:
        raise CalendarError(f"`holidays:` entry {entry!r} is not `Month, Day, Title`")
    month_text, day_text, title = parts

    month = _parse_month(month_text)
    try:
        day = int(day_text)
    except ValueError as exc:
        raise CalendarError(f"`holidays:` entry {entry!r} has an invalid day") from exc

    return Holiday(month=month, day=day, title=title)


def _parse_month(text: str) -> int:
    if text.isdigit():
        return int(text)
    for fmt in ("%b", "%B"):
        try:
            return datetime.strptime(text, fmt).month
        except ValueError:
            continue
    raise CalendarError(f"{text!r} is not a valid month")


def _parse_sections(body: str) -> tuple[Section, ...]:
    """
    Parse every h2 (`## Title`, optionally `## Title (YYYY-MM-DD)`) into a
    `Section`, its description running to the next h2 or the end of file.
    """
    matches = list(_SECTION_RE.finditer(body))
    sections = []
    for index, match in enumerate(matches):
        title = match.group("title").strip()
        fixed_date = (
            date.fromisoformat(match.group("date")) if match.group("date") else None
        )
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        description = body[start:end].strip()
        sections.append(
            Section(title=title, description=description, fixed_date=fixed_date)
        )
    return tuple(sections)


def _date_range(start: date, end: date) -> Iterator[date]:
    """
    Every date from `start` to `end`, inclusive.
    """
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _iso_week_start(day: date) -> date:
    """
    The Monday of the ISO week `day` falls in.
    """
    return day - timedelta(days=day.isoweekday() - 1)
