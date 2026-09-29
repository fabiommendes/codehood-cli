# Changelog

Changelog of releases of Codehood CLI.

## Unreleased

- The Textual apps (`chill`, `show`, `api`) use Codehood's themes: Forest
  (dark, the default) and Cerrado (light), switchable from the command
  palette. Rich output uses role styles (`error`, `success`, `primary`,
  `muted`, ...) mapped to the 16 ANSI colors, so it follows the terminal's
  palette. The definitions live in `codehood/theme.py`.
- Questions are parsed with `mdq.parse(..., kind="question")`, which replaced
  `mdq.parse_question`. A file `mdq` rejects now raises `InvalidDocument`
  rather than `ParseError`, and `codehood show` gives widgets a document with
  an id on every choice.
- The CLI now lives in `cli/` of the server repository. `mdq` resolves from
  `../../mdq/mdq-py`, and `scripts/copy-openapi.py` looks in the parent
  repository first.
- `codehood push` now syncs `calendar.md`. A new pure core parses the file
  into time slots, holidays and h2 sections, then allocates every section a
  date from the slots the course's range actually offers. Holidays that land
  on a slot become `HOLIDAY` events and push the sections after them along;
  an h2 titled `## Something (2026-03-10)` pins itself to that date. Slugs
  follow the weekday (`mon`), suffixed with the start time when two slots
  share a day (`mon-14_00`, `mon-18_00`), so reordering `days:` changes
  nothing on the wire.
- The course's `startAt`/`endAt` now come from `calendar.md`, not from the
  edition. An edition is an institutional term shared across courses; a
  course's own span is the instructor's to set. `README.md` and
  `calendar.md` are both mandatory as a result -- they are the only source
  of the course's description and dates.
- A calendar event is diffed on `(ref, kind)`, not `ref` alone. `ref` hashes
  title and description only, so a date that stops being a class and becomes
  a holiday is invisible to it and would never converge.
- An event the server reports as `CANCELLED` is never rewritten and never
  pruned, and it pins its time slot: the slot survives a push that no longer
  declares it, with a `WarnTimeSlotPinned` naming both. Deleting it would
  orphan an event the CLI has promised not to touch, and the server refuses
  it. The instructor resolves it server-side.
- The four calendar writes go out as delete events, delete slots, upsert
  slots, upsert events. An event references its slot, and two slots may not
  overlap on one weekday, so any other order costs a second push whenever a
  slug changes -- renaming `mon-14_00` back to `mon` took three before.
- `plan_push` takes a `LocalState` and a `ServerState` instead of nine
  positional arguments. `slug -> ref` and `slug -> version` are the same
  type and mean different things; naming them as fields of distinct records
  is what stops a caller from swapping them silently.
- `api/generated.py` covers the time-slot and calendar-event endpoints.
  Generating them surfaced another `api/generate.py` bug: the server spells
  some names as prose (`Calendar Event`, `createCalendar-event`) and the
  generator emitted them verbatim, producing `def create_calendar-event` and
  `class Calendar Event`. Names are now sanitized into identifiers.
- The `mdq` path dependency pointed at `../mdq.spec`, which no longer
  exists. Nothing in the repository could resolve dependencies until it was
  retargeted at `../mdq/mdq-py`.

- `codehood push` now syncs `questions/` too: every MDQ file under it,
  recursively, created, updated, and deleted, parsed client-side by the
  `mdq` package. A question's slug is its flattened path, the way a
  resource's is, and the md5 of its file rides in the server's `version`
  field -- `Question` has no `contentHash` (see `ROADBLOCKS.md`).
  `ordering` questions are planned but refused: the server's schema has no
  such type.
- `api/generated.py` covers the question endpoints. Generating them
  surfaced two bugs in `api/generate.py`: an untyped schema node
  (`{"nullable": true}`, the free-form `meta` map) crashed instead of
  mapping to `object`, and a tagged union whose tags carry separators
  minted illegal class names (`QuestionMultiple-choice`). Tags are now
  capitalized word by word, giving `QuestionMultipleChoice`.
- The hypothesis strategy builder draws from `oneOf` the same way it draws
  from `anyOf`, instead of refusing it. Every union in the document is
  discriminated by a single-valued `type` enum, so drawing one member is
  exactly right.

- `codehood push` syncs a course repository's description and `resources/`
  (`MD`/`CODE`) to the server: `--dry-run`, `--no-prune`, one line per
  operation, converges on re-run. `FILE` resources are planned but refused,
  and `LINK` waits on the resource manifest -- see `ROADBLOCKS.md`.
- Regenerated `api/generated.py` against the rewritten server API. A
  resource's `type` moved inside `data`, now a union tagged by it;
  `contentHash` became a free-form `ref` the CLI alone gives meaning to
  (`push/resource.content_ref`); `PUT` moved from each by-key path to its
  collection, with the natural key in the body; and `readEdition` takes
  `slug` rather than `id`.
- The generated client no longer sends query parameters the caller left
  unset. `httpx` renders `None` as `?types=`, which the server reads as a
  present-but-empty filter and rejects -- `codehood push` could not list
  resources at all.
- Every request now declares `Content-Type: application/json`. Without it a
  bodyless `DELETE` trips Astro's cross-site guard, so `--prune` failed
  with `403` on every deletion.
- The generator names a tagged union's members after their tag --
  `DataMd`, `DataCode`, `DataFile` -- instead of numbering them `Data`,
  `Data2`, `Data3` by the order the server happened to declare them in.

## 0.1.0

- Minimal viable product. It can init a course, push changes to the server and
  download assignments.


