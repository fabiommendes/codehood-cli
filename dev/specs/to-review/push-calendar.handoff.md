---
type: handoff
status: to-review
tags: [push, calendar, sync]
relatedTo: [docs/design/mapping-local-filesystem.md]
---

# Handoff: calendar sync for `codehood push`

Authority is `docs/design/mapping-local-filesystem.md`, sections "Course",
"Calendar", "Sync preflight", "Deletion and pruning". Where this document and
that one disagree, that one wins and this one is the bug.

## Goal

`codehood push` reads `calendar.md`, derives the course's `startAt`/`endAt`, its
TimeSlots and its CalendarEvents, and converges the server onto them: upsert
what differs, prune what no local line accounts for, never touch a `CANCELLED`
event.

## What already landed (done before the cycle starts)

- `pyproject.toml`: the `mdq` path dependency pointed at `../mdq.spec`, which no
  longer exists. Now `../mdq/mdq-py`. Nothing in the repo could resolve
  dependencies before this.
- `resources/openapi/codehood.json` refreshed from the live dev server. It now
  carries `/api/course/{discipline}/{course}/time-slot[/{slug}]` and
  `.../calendar-event[/{week}/{timeSlot}]`, which the stale copy had at the top
  level with an opaque `{id}`.
- `codehood/api/generate.py`: `ENDPOINTS` gained `timeslot` and
  `calendar-event`, plus a `py_class_name` sanitizer. The server spells some
  names as prose (`Calendar Event`, `createCalendar-event`) and the generator
  was emitting those verbatim, producing `def create_calendar-event` and
  `class Calendar Event`. Fallout for the tester: the refreshed spec adds a
  required `enrollmentCount` to the course response, so seven existing tests
  fail on their own fixtures.

## Public API

### New: `codehood/push/calendar.py` (pure)

Parsing and allocation, no clock, no network, no warnings module.

```python
type Weekday = Literal["SUNDAY", "MONDAY", ..., "SATURDAY"]
type EventKind = Literal["REGULAR", "HOLIDAY"]

@dataclass(frozen=True)
class TimeOfDay:  hour: int; minute: int
@dataclass(frozen=True)
class Duration:   hours: int; minutes: int

@dataclass(frozen=True)
class TimeSlot:
    slug: str; day: Weekday; start: TimeOfDay
    duration: Duration; title: str | None
    @property
    def ref(self) -> str: ...        # md5 over its own pushable fields

@dataclass(frozen=True)
class Holiday:  month: int; day: int; title: str

@dataclass(frozen=True)
class Section:                       # one h2, before any date is assigned
    title: str; description: str; fixed_date: date | None

@dataclass(frozen=True)
class Calendar:                      # `calendar.md`, parsed and nothing more
    start: date; end: date
    slots: tuple[TimeSlot, ...]
    holidays: tuple[Holiday, ...]
    sections: tuple[Section, ...]

@dataclass(frozen=True)
class Event:                         # allocated, ready to push
    week: int; time_slot: str        # `time_slot` is a TimeSlot.slug
    title: str; description: str
    kind: EventKind
    @property
    def ref(self) -> str: ...        # md5(f"{title}#{description}")

@dataclass(frozen=True)
class Allocation:
    events: tuple[Event, ...]
    warnings: tuple[str, ...]

def parse_calendar(text: str) -> Calendar: ...          # raises CalendarError
def allocate(calendar: Calendar) -> Allocation: ...     # raises CalendarError
```

`Event.time_slot` is a slug, not a `TimeSlot`: `(week, timeSlot-slug)` is the
server's primary key, and keeping the plan's key exactly the URL's key means
nothing downstream has to re-derive it.

Warnings are *returned*, not emitted. Every case the mapping calls a warning
(holiday matching no date, illegal fixed date, more sections than dates, more
dates than sections) lands in `Allocation.warnings` as a sentence, in file
order. The CLI prints them. This is the one thing that makes allocation
testable as a pure function.

Errors (`CalendarError`, new in `push/errors.py`): malformed frontmatter, a
missing `start`/`end`, an unparsable `days:` or `holidays:` entry, a holiday
whose `Month, Day` matches two dates in the range, `end` before `start`.

### Allocation, precisely

1. Candidate pairs: every `(date, slot)` with `start <= date <= end` and
   `date`'s weekday equal to `slot.day`, ordered by `(date, slot.start,
   slot.slug)`.
2. Resolve each holiday against the range. A `Month, Day` that matches no date
   *inside* `start`..`end` is a warning and is dropped outright: it becomes no
   event, occupies no slot, and takes no part in step 6's week numbering. Two
   matches inside the range: `CalendarError`. One match: that date is a holiday.
3. Drop every candidate pair whose date is a holiday. Each *dropped* pair
   becomes a `HOLIDAY` event titled after the holiday entry, description `""`.
   A holiday on no pair produces nothing (and no warning: the mapping only
   warns about the no-date-at-all case).
9. Resolve fixed sections (`## Title (YYYY-MM-DD)`). A date that is outside the
   range, a holiday, or carries no slot: warning, and the section rejoins the
   sequential queue. Otherwise it takes the first pair on that date, which
   leaves the pool.
5. Assign the remaining sections, in file order, to the remaining pairs in
   chronological order. Leftover pairs: warning, unallocated. Leftover
   sections: warning, truncated.
6. `week` is the ISO-week distance from the earliest emitted event of *any*
   kind, so week 0 exists and no week is ever negative. Every emitted event sits
   on a candidate pair, and every candidate pair is inside `start`..`end`, so
   the anchor is always a date the course actually spans -- an out-of-range
   holiday cannot drag week 0 backwards, because step 2 already dropped it.

### Changed: `codehood/push/plan.py`

`plan_push` takes nine positional arguments today and would take fourteen.
Replace them with two frozen dataclasses, which is the type-safety win the task
asks for: a caller cannot silently swap `server_resources` for
`server_questions` any more, because they are named fields of distinct types.

```python
@dataclass(frozen=True)
class LocalState:
    discipline: str; course: str
    description: str                 # README body, H1 dropped
    start: date; end: date           # from calendar.md, NOT the edition
    slots: tuple[TimeSlot, ...]
    events: tuple[Event, ...]
    resources: tuple[ResourceFile, ...] = ()
    questions: tuple[QuestionFile, ...] = ()

@dataclass(frozen=True)
class ServerEvent: ref: str; kind: Literal["REGULAR","HOLIDAY","CANCELLED"]

@dataclass(frozen=True)
class ServerState:                   # moves here from run.py: it is pure data
    course_exists: bool
    resources: Mapping[str, str]                    # slug -> ref
    questions: Mapping[str, str]                    # slug -> version
    time_slots: Mapping[str, str]                   # slug -> ref
    calendar_events: Mapping[tuple[int, str], ServerEvent]

def plan_push(local: LocalState, server: ServerState) -> Iterator[PushOp]: ...
```

New ops, each carrying the whole value rather than re-flattening its fields:

```python
@dataclass(frozen=True)
class UpsertTimeSlot:      slot: TimeSlot
@dataclass(frozen=True)
class DeleteTimeSlot:      slug: str
@dataclass(frozen=True)
class UpsertCalendarEvent: event: Event
@dataclass(frozen=True)
class DeleteCalendarEvent: week: int; time_slot: str
```

Diff rules:

- A slot whose `ref` differs from `server.time_slots[slug]`, or is absent, is
  upserted; a server slug absent locally is deleted.
- An event is upserted when `(ref, kind)` differs from the server's pair at the
  same `(week, timeSlot)`. `ref` hashes title and description only, so it cannot
  see a date that stops being a class and becomes a holiday, or the reverse:
  same slot, same title, different `kind`. Preflight already carries `kind`, so
  comparing both costs nothing and is the only way that flip converges. Now
  written into the mapping document, "Calendar events".
- A server event whose `kind` is `CANCELLED` is neither upserted nor pruned,
  whatever the local file says.
- A server event at a key no local event holds is deleted.
- The four writes go out in exactly this order: delete events, delete slots,
  upsert slots, upsert events. An event references its slot, so a slot cannot be
  deleted while an event still points at it; and two slots may not overlap on one
  weekday, so a renamed slug cannot be created while the old one still holds its
  hour. This order is the only one that satisfies both -- see the mapping's
  "Deletion and pruning". (Corrected 2026-09-24: the first version of this
  handoff said slots before events, which cost a second push on any rename.)
- A slot the preflight shows carrying a `CANCELLED` event is NOT deleted, even
  when no local `days:` entry accounts for it. The cancelled event is never
  pruned, so it pins the slot, and the server refuses to orphan it. Warn, naming
  the slot and the event, and move on.

### Changed: `codehood/push/run.py`

- `ServerState` moves to `plan.py`; `fetch_server_state` stays and additionally
  reads `list_timeslot` and `list_calendar_event`. The mapping's
  `cli.course.preSync` RPC does not exist on the server (no such path in the
  document); list endpoints projected down to markers are the same contract at
  one extra round trip. ROADBLOCKS entry, not a blocker.
- The server's TimeSlot carries no `ref` column, so `fetch_server_state`
  recomputes each slot's ref from the fields it did return, via the same
  `TimeSlot` dataclass. A slot the CLI did not write still compares correctly.
- `_run_op` grows four branches. `UpsertTimeSlot` -> `upsert_timeslot`,
  `DeleteTimeSlot` -> `delete_timeslot`, `UpsertCalendarEvent` ->
  `upsert_calendar_event`, `DeleteCalendarEvent` -> `delete_calendar_event`.

### Changed: `codehood/cli/push.py`

- Drops the `read_edition` call. Course dates come from `calendar.md`; the doc
  is explicit, and the edition's dates are a different thing (an institutional
  term, not this course's span). A missing or unparsable `calendar.md` is an
  `Exit(1)` before any network call, same as a slug collision.
- Prints `Allocation.warnings`, one `warning  ...` line each, before the plan.
- `_describe` grows the four new ops.

## Acceptance criteria

1. `parse_calendar` round-trips the mapping document's own example: `days`
   entry -> `TimeSlot(slug="mon", day="MONDAY", start=14:00, duration=2h,
   title="Lecture")`; the `## Course overview` h2 -> a `Section` whose
   description is the bullet list, stripped.
2. Two slots on one weekday get `mon-14_00`/`mon-18_00`; one gets `mon`.
   Reordering `days:` in the file changes no output at all.
3. A holiday falling on a slot yields a `HOLIDAY` event and shifts every
   following section by one date. A holiday whose `Month, Day` falls outside
   `start`..`end` yields a warning and nothing else: no event, no date consumed,
   and week 0 unmoved -- in particular, a holiday dated before `start` does not
   become the week anchor.
4. An event whose title and description are unchanged but whose `kind` flipped
   between `REGULAR` and `HOLIDAY` is still upserted.
5. `## Title (2026-03-10)` pins that section; the sections around it keep the
   remaining dates in order.
6. A `CANCELLED` server event at a key the local file also fills produces
   neither an upsert nor a delete.
7. A second `plan_push` against the state the first one wrote yields only
   `UpsertCourse`. Convergence is the property worth fuzzing.
8. `codehood push` against the live dev server writes the calendar, and a
   second run reports nothing but the course row.
9. `ruff check`, `ruff format --check`, `mypy codehood`, `pytest` all clean.

## Testing strategy

- Property-based (hypothesis; the repo already has `codehood/hypothesis.py`):
  - A generated `Calendar` allocates events onto distinct `(week, timeSlot)`
    keys, every one of them a real slot slug, weeks non-negative and starting
    at 0.
  - `len(events) == len(sections allocated) + len(holidays on a slot)`, and
    allocated sections never exceed available dates.
  - Idempotence: `plan_push(local, state_after(local))` yields exactly one op.
  - Slot ordering invariance: shuffling `days:` leaves `allocate` output equal.
- Table-driven examples for the parser: every `days`/`holidays` spelling,
  slug-collision suffixing, a dated h2, a malformed entry per error case. Pure
  function, so a table is the right shape.
- `plan_push` diff rules as focused examples: the `CANCELLED` case, prune,
  ref-match skip, kind flip.
- `run.py` against `httpx.MockTransport`, asserting method, path and body for
  one slot and one event. No live server in the suite.
- One integration test marked the way `tests/test_api_integration.py` already
  marks its own, hitting `localhost:4321` as `ada`, skipped when it is down.

## Boundaries

Questions and exams keep their current behavior. They move only because
`plan_push`'s signature changed; their diff rules, slugs and payloads do not.
