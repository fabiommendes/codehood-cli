"""
Tests for `codehood.push.calendar`: the pure core that turns `calendar.md`
into `TimeSlot`s and `CalendarEvent`s -- no clock, no network, no
`warnings` module. See `docs/design/mapping-local-filesystem.md`,
"Calendar", and `dev/specs/to-do/push-calendar.handoff.md`'s acceptance
criteria and testing strategy.

Table-driven examples cover the parser's grammar and the allocator's
worked examples from the mapping document (acceptance criteria 1-5).
Hypothesis strategies build `Calendar` values directly -- skipping the
text grammar entirely -- to check `allocate`'s own invariants: distinct
keys, real slugs, non-negative weeks starting at 0, the event-count
identity, and order-independence of `days:`.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import replace
from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from codehood.push.calendar import (
    Calendar,
    Duration,
    Event,
    Holiday,
    Section,
    TimeOfDay,
    TimeSlot,
    allocate,
    parse_calendar,
)
from codehood.push.errors import CalendarError

WEEKDAY_NAMES = (
    "SUNDAY",
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
)


#
# parse_calendar -- the mapping document's own worked example
#
MAPPING_EXAMPLE = """---
start: 2026-01-01
end:   2026-06-01
days:
  - Mon 14:00 2h, Lecture
holidays:
  - Oct, 12, Childrens Day
---

# Schedule

## Course overview

What we will cover, how grading works.

* Course presentation
* Instructor contact
* Office hours
"""


def test_parse_calendar_round_trips_the_mapping_documents_own_example():
    """Acceptance criterion 1."""
    calendar = parse_calendar(MAPPING_EXAMPLE)
    assert calendar.start == date(2026, 1, 1)
    assert calendar.end == date(2026, 6, 1)
    assert calendar.slots == (
        TimeSlot(
            slug="mon",
            day="MONDAY",
            start=TimeOfDay(hour=14, minute=0),
            duration=Duration(hours=2, minutes=0),
            title="Lecture",
        ),
    )
    assert calendar.holidays == (Holiday(month=10, day=12, title="Childrens Day"),)
    [section] = calendar.sections
    assert section.title == "Course overview"
    assert section.fixed_date is None
    assert section.description == (
        "What we will cover, how grading works.\n\n"
        "* Course presentation\n"
        "* Instructor contact\n"
        "* Office hours"
    )


#
# Table-driven grammar: days:, holidays:, fixed dates, errors.
#
def _calendar_text(
    days: list[str],
    holidays: list[str] | None = None,
    extra: str = "",
    start: str = "2026-01-01",
    end: str = "2026-06-01",
) -> str:
    days_field = (
        "days: []" if not days else "days:\n" + "\n".join(f"  - {d}" for d in days)
    )
    holidays_field = (
        "holidays: []"
        if not holidays
        else "holidays:\n" + "\n".join(f"  - {h}" for h in holidays)
    )
    return f"""---
start: {start}
end:   {end}
{days_field}
{holidays_field}
---

# Schedule
{extra}
"""


DAY_ABBREVIATION_CASES = [
    ("Sun", "SUNDAY"),
    ("Mon", "MONDAY"),
    ("Tue", "TUESDAY"),
    ("Wed", "WEDNESDAY"),
    ("Thu", "THURSDAY"),
    ("Fri", "FRIDAY"),
    ("Sat", "SATURDAY"),
]


@pytest.mark.parametrize("abbreviation, expected", DAY_ABBREVIATION_CASES)
def test_parse_calendar_day_abbreviations(abbreviation: str, expected: str) -> None:
    text = _calendar_text([f"{abbreviation} 09:00 1h, Class"])
    [slot] = parse_calendar(text).slots
    assert slot.day == expected


def test_parse_calendar_duration_hours_only():
    text = _calendar_text(["Mon 09:00 3h, Class"])
    [slot] = parse_calendar(text).slots
    assert slot.duration == Duration(hours=3, minutes=0)


def test_parse_calendar_start_time():
    text = _calendar_text(["Wed 08:30 1h, Class"])
    [slot] = parse_calendar(text).slots
    assert slot.start == TimeOfDay(hour=8, minute=30)


def test_parse_calendar_title_is_the_entrys_trailing_text():
    text = _calendar_text(["Mon 09:00 1h, Recitation"])
    [slot] = parse_calendar(text).slots
    assert slot.title == "Recitation"


MONTH_ABBREVIATION_CASES = [("Jan", 1), ("Oct", 10), ("Dec", 12)]


@pytest.mark.parametrize("abbreviation, expected", MONTH_ABBREVIATION_CASES)
def test_parse_calendar_holiday_month_abbreviations(
    abbreviation: str, expected: int
) -> None:
    text = _calendar_text([], holidays=[f"{abbreviation}, 5, Some Day"])
    [holiday] = parse_calendar(text).holidays
    assert holiday.month == expected
    assert holiday.day == 5
    assert holiday.title == "Some Day"


def test_parse_calendar_slug_collision_on_same_weekday_suffixes_with_start_time():
    """Acceptance criterion 2."""
    text = _calendar_text(["Mon 14:00 2h, Lecture", "Mon 18:00 1h, Lab"])
    slugs = {slot.slug for slot in parse_calendar(text).slots}
    assert slugs == {"mon-14_00", "mon-18_00"}


def test_parse_calendar_single_slot_on_a_weekday_gets_the_bare_slug():
    """Acceptance criterion 2."""
    text = _calendar_text(["Tue 10:00 2h, Lecture"])
    [slot] = parse_calendar(text).slots
    assert slot.slug == "tue"


def test_parse_calendar_slots_are_sorted_by_weekday_then_start_regardless_of_file_order():
    """Acceptance criterion 2: "Reordering `days:` in the file changes no
    output at all."""
    a = parse_calendar(
        _calendar_text(
            ["Wed 09:00 1h, C", "Mon 18:00 1h, Lab", "Mon 14:00 2h, Lecture"]
        )
    )
    b = parse_calendar(
        _calendar_text(
            ["Mon 14:00 2h, Lecture", "Mon 18:00 1h, Lab", "Wed 09:00 1h, C"]
        )
    )
    assert a.slots == b.slots


def test_parse_calendar_fixed_date_section():
    """Acceptance criterion (fixed-date h2, mapping's "Calendar events")."""
    text = _calendar_text(
        ["Mon 14:00 2h, Lecture"], extra="\n## Midterm (2026-03-10)\n\nBody text.\n"
    )
    [section] = parse_calendar(text).sections
    assert section.title == "Midterm"
    assert section.fixed_date == date(2026, 3, 10)
    assert section.description == "Body text."


def test_parse_calendar_struck_through_title_is_a_cancelled_lesson():
    text = _calendar_text(
        ["Mon 14:00 2h, Lecture"],
        extra="\n## ~~Functions~~ (2026-03-09)\n\nMoved.\n\n## ~~ ~~\n\n## Loops\n",
    )
    cancelled, odd, regular = parse_calendar(text).sections
    assert (cancelled.title, cancelled.cancelled) == ("Functions", True)
    assert cancelled.fixed_date == date(2026, 3, 9)
    assert (odd.title, odd.cancelled) == ("~~ ~~", False)
    assert regular.cancelled is False


def test_allocate_gives_a_cancelled_lesson_its_date_and_kind():
    text = _calendar_text(
        ["Mon 14:00 2h, Lecture"],
        extra="\n## Intro\n\n## ~~Functions~~\n\n## Loops\n",
        start="2026-01-05",
        end="2026-01-19",
    )
    events = allocate(parse_calendar(text)).events
    assert [(e.week, e.title, e.kind) for e in events] == [
        (0, "Intro", "REGULAR"),
        (1, "Functions", "CANCELLED"),
        (2, "Loops", "REGULAR"),
    ]


def test_parse_calendar_section_without_a_date_has_no_fixed_date():
    text = _calendar_text(["Mon 14:00 2h, Lecture"], extra="\n## Intro\n\nBody.\n")
    [section] = parse_calendar(text).sections
    assert section.fixed_date is None


#
# Errors
#
def test_parse_calendar_missing_frontmatter_raises():
    with pytest.raises(CalendarError):
        parse_calendar("# Schedule\n\nNo frontmatter here.\n")


def test_parse_calendar_missing_start_raises():
    text = "---\nend: 2026-06-01\ndays: []\nholidays: []\n---\n\n# Schedule\n"
    with pytest.raises(CalendarError):
        parse_calendar(text)


def test_parse_calendar_missing_end_raises():
    text = "---\nstart: 2026-01-01\ndays: []\nholidays: []\n---\n\n# Schedule\n"
    with pytest.raises(CalendarError):
        parse_calendar(text)


def test_parse_calendar_end_before_start_raises():
    text = _calendar_text([], start="2026-06-01", end="2026-01-01")
    with pytest.raises(CalendarError):
        parse_calendar(text)


def test_parse_calendar_malformed_days_entry_raises():
    text = _calendar_text(["this is not a days entry"])
    with pytest.raises(CalendarError):
        parse_calendar(text)


def test_parse_calendar_malformed_holidays_entry_raises():
    text = _calendar_text([], holidays=["this is not a holiday"])
    with pytest.raises(CalendarError):
        parse_calendar(text)


def test_allocate_holiday_matching_two_dates_in_range_raises():
    """
    A course spanning more than a year can have a `Month, Day` land twice --
    the instructor's ambiguity to resolve, per the mapping's "Calendar".
    """
    slot = TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=9, minute=0),
        duration=Duration(hours=1, minutes=0),
    )
    calendar = Calendar(
        start=date(2026, 1, 1),
        end=date(2027, 12, 31),
        slots=(slot,),
        holidays=(Holiday(month=7, day=4, title="Twice"),),
    )
    with pytest.raises(CalendarError):
        allocate(calendar)


#
# allocate -- the mapping's worked examples (acceptance criteria 3-5)
#
def test_allocate_holiday_on_a_slot_yields_a_holiday_event_and_shifts_sections():
    """
    Acceptance criterion 3: "A holiday falling on a slot yields a HOLIDAY
    event and shifts every following section by one date."

    Four Mondays (2026-01-05, 12, 19, 26); a holiday lands on the first.
    Two plain sections take the next two Mondays in order.
    """
    slot = TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
    )
    calendar = Calendar(
        start=date(2026, 1, 5),
        end=date(2026, 1, 26),
        slots=(slot,),
        holidays=(Holiday(month=1, day=5, title="New Year Break"),),
        sections=(
            Section(title="S1", description=""),
            Section(title="S2", description=""),
        ),
    )
    allocation = allocate(calendar)

    [holiday_event] = [e for e in allocation.events if e.kind == "HOLIDAY"]
    assert holiday_event.title == "New Year Break"
    assert holiday_event.description == ""
    assert holiday_event.time_slot == "mon"
    assert holiday_event.week == 0

    regular_by_title = {e.title: e for e in allocation.events if e.kind == "REGULAR"}
    assert set(regular_by_title) == {"S1", "S2"}
    assert regular_by_title["S1"].week == 1
    assert regular_by_title["S2"].week == 2


@pytest.mark.parametrize(
    "holiday_month, holiday_day",
    [(1, 1), (2, 1)],
    ids=["holiday-before-start", "holiday-after-end"],
)
def test_allocate_drops_a_holiday_matching_no_date_in_range(
    holiday_month: int, holiday_day: int
) -> None:
    """
    Acceptance criterion 3's second half, and the mapping's "Calendar": "A
    holiday matching no date inside the range is a warning and is ignored:
    ... it becomes no event, occupies no slot, and takes no part in
    numbering weeks."

    The course spans 2026-01-05..2026-01-26 (four Mondays); Jan 1 is before
    `start`, Feb 1 is after `end`, so neither ever resolves inside the
    range. If a pre-term holiday were allowed to anchor week 0, every real
    class would be pushed to a negative week -- `week` is a URL segment, so
    that would be a broken push, not just a cosmetic one.
    """
    slot = TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
    )
    calendar = Calendar(
        start=date(2026, 1, 5),
        end=date(2026, 1, 26),
        slots=(slot,),
        holidays=(Holiday(month=holiday_month, day=holiday_day, title="Out of range"),),
        sections=(
            Section(title="S1", description=""),
            Section(title="S2", description=""),
        ),
    )
    allocation = allocate(calendar)

    assert len(allocation.warnings) >= 1
    assert not any(event.kind == "HOLIDAY" for event in allocation.events)
    assert {event.title for event in allocation.events} == {"S1", "S2"}
    assert all(event.week >= 0 for event in allocation.events)
    assert min(event.week for event in allocation.events) == 0


def test_allocate_fixed_date_section_pins_that_date_and_others_keep_order():
    """
    Acceptance criterion 4 (now numbered 5): a dated h2 pins that section;
    the sections around it keep the remaining dates in order.

    Four Mondays; S2 is pinned to the third (2026-01-19). S1 and S3 take
    the earliest remaining dates in file order: 2026-01-05 and 2026-01-12.
    """
    slot = TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
    )
    calendar = Calendar(
        start=date(2026, 1, 5),
        end=date(2026, 1, 26),
        slots=(slot,),
        sections=(
            Section(title="S1", description=""),
            Section(title="S2", description="", fixed_date=date(2026, 1, 19)),
            Section(title="S3", description=""),
        ),
    )
    allocation = allocate(calendar)

    by_title = {e.title: e for e in allocation.events}
    assert set(by_title) == {"S1", "S2", "S3"}
    assert by_title["S1"].week == 0
    assert by_title["S3"].week == 1
    assert by_title["S2"].week == 2


#
# Event.ref / TimeSlot.ref
#
def test_event_ref_is_md5_of_title_hash_description():
    """The mapping's "Calendar events": `ref = md5(f"{title}#{description}")`."""
    event = Event(week=0, time_slot="mon", title="Intro", description="Welcome.")
    expected = hashlib.md5("Intro#Welcome.".encode()).hexdigest()
    assert event.ref == expected


def test_event_ref_changes_with_title_or_description():
    base = Event(week=0, time_slot="mon", title="Intro", description="Welcome.")
    diff_title = Event(week=0, time_slot="mon", title="Other", description="Welcome.")
    diff_description = Event(
        week=0, time_slot="mon", title="Intro", description="Other."
    )
    assert base.ref != diff_title.ref
    assert base.ref != diff_description.ref


def test_event_ref_ignores_week_and_time_slot_but_not_kind():
    """
    `week` and `time_slot` are the key of the event, so they stay out of the
    digest; a `kind` flip changes what the server holds and has to show in it.
    """
    a = Event(week=0, time_slot="mon", title="Intro", description="Welcome.")
    b = Event(week=5, time_slot="tue", title="Intro", description="Welcome.")
    holiday = Event(
        week=0, time_slot="mon", title="Intro", description="Welcome.", kind="HOLIDAY"
    )
    assert a.ref == b.ref
    assert a.ref != holiday.ref


def _base_slot() -> TimeSlot:
    return TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
        title="Lecture",
    )


def test_time_slot_ref_is_deterministic_for_the_same_content():
    a = _base_slot()
    b = _base_slot()
    assert a.ref == b.ref


@pytest.mark.parametrize(
    "mutate",
    [
        lambda slot: replace(slot, day="TUESDAY"),
        lambda slot: replace(slot, start=TimeOfDay(hour=15, minute=0)),
        lambda slot: replace(slot, duration=Duration(hours=1, minutes=0)),
        lambda slot: replace(slot, title="Different"),
    ],
    ids=["day", "start", "duration", "title"],
)
def test_time_slot_ref_changes_when_a_pushable_field_changes(mutate) -> None:
    base = _base_slot()
    assert mutate(base).ref != base.ref


#
# Property-based invariants on `allocate` -- built directly from `Calendar`
# values, bypassing the text grammar entirely.
#
@st.composite
def _allocate_calendars(draw: st.DrawFn) -> Calendar:
    start = draw(st.dates(min_value=date(2026, 1, 5), max_value=date(2026, 10, 1)))
    span = draw(st.integers(min_value=7, max_value=60))
    end = start + timedelta(days=span)

    num_slots = draw(st.integers(min_value=1, max_value=3))
    slots = tuple(
        TimeSlot(
            slug=f"slot{i}",
            day=draw(st.sampled_from(WEEKDAY_NAMES)),
            start=TimeOfDay(
                hour=draw(st.integers(0, 23)),
                minute=draw(st.sampled_from([0, 15, 30, 45])),
            ),
            duration=Duration(hours=1, minutes=0),
            title=None,
        )
        for i in range(num_slots)
    )

    num_sections = draw(st.integers(min_value=0, max_value=8))
    sections = tuple(
        Section(title=f"section-{i}", description="") for i in range(num_sections)
    )

    num_holidays = draw(st.integers(min_value=0, max_value=2))
    month_days = draw(
        st.lists(
            st.tuples(st.integers(1, 12), st.integers(1, 28)),
            min_size=num_holidays,
            max_size=num_holidays,
            unique=True,
        )
    )
    holidays = tuple(
        Holiday(month=month, day=day, title=f"holiday-{i}")
        for i, (month, day) in enumerate(month_days)
    )

    return Calendar(
        start=start, end=end, slots=slots, holidays=holidays, sections=sections
    )


def _candidate_pairs(calendar: Calendar) -> list[tuple[date, TimeSlot]]:
    """Mirrors the mapping's "Allocation, precisely", step 1."""
    pairs = []
    day = calendar.start
    while day <= calendar.end:
        weekday_name = WEEKDAY_NAMES[(day.weekday() + 1) % 7]  # Monday=1 -> index 1
        for slot in calendar.slots:
            if slot.day == weekday_name:
                pairs.append((day, slot))
        day += timedelta(days=1)
    return pairs


def _holiday_dates(calendar: Calendar) -> set[date]:
    """Mirrors step 2: a holiday resolves only against `start.year`/`end.year`
    and only if the resulting date actually falls inside the range."""
    resolved: set[date] = set()
    for holiday in calendar.holidays:
        for year in {calendar.start.year, calendar.end.year}:
            try:
                candidate = date(year, holiday.month, holiday.day)
            except ValueError:
                continue
            if calendar.start <= candidate <= calendar.end:
                resolved.add(candidate)
    return resolved


@given(calendar=_allocate_calendars())
@settings(max_examples=100)
def test_allocate_events_land_on_distinct_real_slot_keys_with_nonnegative_weeks(
    calendar,
):
    allocation = allocate(calendar)
    keys = [(event.week, event.time_slot) for event in allocation.events]

    assert len(keys) == len(set(keys)), "every (week, timeSlot) key must be distinct"
    slugs = {slot.slug for slot in calendar.slots}
    assert all(time_slot in slugs for _, time_slot in keys)
    assert all(week >= 0 for week, _ in keys)
    # Weeks count from the course start, so none passes the course end.
    last_week = (
        calendar.end
        - timedelta(days=calendar.end.weekday())
        - (calendar.start - timedelta(days=calendar.start.weekday()))
    ).days // 7
    assert all(week <= last_week for week, _ in keys)


@given(calendar=_allocate_calendars())
@settings(max_examples=100)
def test_allocate_event_count_matches_sections_allocated_and_holidays_on_a_slot(
    calendar,
):
    allocation = allocate(calendar)
    candidates = _candidate_pairs(calendar)
    holiday_dates = _holiday_dates(calendar)

    holiday_pairs = [pair for pair in candidates if pair[0] in holiday_dates]
    remaining_pairs = [pair for pair in candidates if pair[0] not in holiday_dates]

    holiday_events = [e for e in allocation.events if e.kind == "HOLIDAY"]
    regular_events = [e for e in allocation.events if e.kind == "REGULAR"]

    assert len(holiday_events) == len(holiday_pairs)
    assert len(regular_events) == min(len(calendar.sections), len(remaining_pairs))
    assert len(regular_events) <= len(remaining_pairs)


@given(calendar=_allocate_calendars())
@settings(max_examples=50)
def test_allocate_is_invariant_to_the_order_of_days_entries(calendar):
    """Acceptance criterion 2: reordering `days:` changes no output."""
    shuffled_slots = list(calendar.slots)
    random.Random(0).shuffle(shuffled_slots)
    shuffled = replace(calendar, slots=tuple(shuffled_slots))
    assert allocate(calendar) == allocate(shuffled)


def test_allocate_counts_iso_weeks_from_the_course_start():
    """
    Week 0 is the Monday-to-Sunday week the course starts in, as on the
    server, not the week of the first event.
    """
    monday = TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
    )
    wednesday = TimeSlot(
        slug="wed",
        day="WEDNESDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
    )
    # A Saturday: the first class, Monday the 16th, is already in week 1.
    calendar = Calendar(
        start=date(2026, 3, 14),
        end=date(2026, 3, 31),
        slots=(monday, wednesday),
        sections=(
            Section(title="S1", description=""),
            Section(title="S2", description=""),
            Section(title="S3", description="", fixed_date=date(2026, 3, 23)),
        ),
    )
    allocation = allocate(calendar)

    by_title = {e.title: e for e in allocation.events}
    assert (by_title["S1"].week, by_title["S1"].time_slot) == (1, "mon")
    assert (by_title["S2"].week, by_title["S2"].time_slot) == (1, "wed")
    assert (by_title["S3"].week, by_title["S3"].time_slot) == (2, "mon")
