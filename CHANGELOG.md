# Changelog

Changelog of releases of Codehood CLI.

## Unreleased

- `codehood push` syncs `exams/`: every MDQ file under it, at any depth, is an
  exam. The slug is the MDQ `id` (front matter or H1) or the path; `quiz` and
  `practice` in a path set the type; a `_` makes a draft, otherwise a `start`
  schedules it. `include:` resolves by slug, by unique filename stem or by
  path, `includeAll:` by tag query (with `max` it is an error), and inline
  questions are pushed as questions named `<exam>-<id>` or `<exam>-q<n>`. A
  broken include makes the exam `invalid` (exit code 1) and the server copy,
  and its questions, stay. A `duration` or `start` the file omits is never
  blanked, an exam the server moved to `ONGOING` or `COMPLETED` keeps its
  status, and `penalty`, `grading`, `shuffle` and `attachments` are warned
  about and not sent. `FileType.EXAM` replaces the three `exams/{draft,
  practice,published}` types.
- The "not pushed (no handler)" report of `codehood push` follows git's ignore
  rules in a git repository (nested `.gitignore`, `.git/info/exclude`,
  `core.excludesFile`). New `.codehoodignore` (gitignore syntax) hides paths
  from the report; inside `questions/` and `resources/` it works like
  `[push] exclude`. `roster.csv` reads `not synced yet (codehood roster)`.
- `codehood push` is a three-way sync. It compares the repository, the base
  of the last sync (`.local/codehood/`, created by `ch init` or the first push, replaces
  `.codehood/`) and the server. It sends only local changes and reports
  server-side changes without writing them: `pull` (a write that came from no CLI, such as a web edit or creation),
  `conflict` (both sides changed, exit code 1) and `other cli` (pushed from
  another checkout, run `git pull`). `--ours <kind>/<key>` settles conflicts
  and `other cli` entries with the local version, in dependency order. An
  entity created on the server without a `rev` is no longer pruned. Writing
  server changes into the files (`ch pull`, `ch sync`) comes later. Push
  creates the base's `.gitignore` itself, and sends `rev` for questions, so an
  edit from another CLI is told from a web edit.
- `codehood push` sends an ordering question with no `[extra]`, `[accept]` or
  `[reject]` section. `mdq` models default those lists to `[]`, which the
  server refused with `400 ... esperado que array tivesse >=1 itens`.
- `Plan(writes, notices)` replaces the flat list of actions. `diff_keyed`
  compares entities by key and each entity has its own merge. A rejected
  question comes out as `invalid`, not `failed`, and notices print before the
  writes run.
- `CourseKey` identifies a course across commands.
- `read_course_readme`: a README without an H1 now gives the description.

- A resource that is not Markdown keeps its extension in the slug
  (`aabb.py`, `aabb.png`), so files that differ only in extension coexist.
  Existing non-Markdown resources move to the new slug on the next push.
- A struck-through h2 in `calendar.md` (`## ~~Title~~`) is a cancelled
  lesson, pushed as `CANCELLED`. A push never undoes a cancellation.
- The course row carries a `rev` and is skipped when unchanged, so a push with
  nothing new executes nothing.
- The course description is the README's first paragraph, or `description`
  in `[course]` of `codehood.toml`. The rest of the README goes up as the
  `MD` resource `readme`, titled by its H1.
- `codehood push` rewrites the links and images inside an `MD` resource that
  point to other resources (`![](repl.png)`, `[rubrica](../projeto/rubrica.md)`)
  to their pages on the server. A failed resource upload names the lesson
  whose link it breaks.
- `codehood push` no longer aborts on a question `mdq` refuses: the file
  fails alone, the rest goes up, the server copy is kept, and the push exits
  non-zero (`--dry-run` lists it as `invalid`).
- `codehood push` sends a question's status: `DRAFT` for a `_` file or
  directory, `PUBLISHED` otherwise, without the `_` in the slug. It never
  moves a status back, so a question published or hidden on the web stays
  that way, and a `_` file over a published question only warns.
- `codehood push` reads `.url` files as `LINK` resources (a text/uri-list:
  the first URI is the link, the first comment the title, the others the
  description) and a folder's `info.yaml` as the metadata of its files
  (`title`, `description`, and `language` or `mime` to force `CODE` or
  `FILE`). A malformed one stops the push before any request.
- A resource with no declared title gets its file name in title case
  (`janela-minima.py` is "Janela Minima").
- Slugs drop accents the way the server does (`laços/herança.md` is
  `lacos-heranca`). The next push archives the old accented slugs and
  creates the new ones.
- A question's `id` in its front matter is its slug, for excluded files too.
- `ch init` writes the example exam with `start` and `duration`, which push
  reads, instead of `meta.codehood.scheduled_at`/`duration_min`.

- `codehood push` uploads `FILE` resources (PDF, images, any opaque file).
  It asks the server which blobs it lacks and sends the bytes only then, in
  the same request as the resource.

- `CODEHOOD_TOKEN`: when set, the CLI uses it as the API key for any server
  and does not read `~/.codehood/credentials.toml`.
- `codehood push` lists the files it did not push because no stage reads
  them (`not pushed (no handler): exams/prova1.md`), next to the excluded
  ones.
- `seed/pyxel101/`: a full course repository used by the server's
  `pnpm run db:seed:cli`, with `seed/GAPS.md` listing what it asks for and
  the platform does not do yet.
- `repositories/`: each subfolder is pushed as a course repository, honoring
  its nested `.gitignore` files and `[push] exclude`. Only files the server
  lacks are uploaded. `-m/--message` sets the commit message. A folder that
  disappears is kept on the server (with a warning) unless
  `--drop-repositories` is given. Links from `calendar.md` to
  `repositories/<slug>[/<path>]` attach the repository to the lesson and point
  to its page. `ch init` creates `repositories/`.
- An unreachable server, a connection lost mid-push, or a command run before
  `codehood login` ends with one `error:` line and exit code 1 instead of a
  traceback.
- `codehood login` stores the login name beside the key and says when it
  replaces the stored login of another user for the same server (there is one
  credential per server); `codehood logout` says which login it forgot.
  Existing `credentials.toml` files keep working.
- When the course row cannot be written (for example, the edition does not
  accept new courses), `codehood push` stops there: the remaining operations
  are listed as not attempted instead of failing one by one with `404`.
- `[push] exclude` in `codehood.toml` keeps questions and resources out of a
  push, with gitignore-like patterns. Excluded files are not parsed, are
  listed by `codehood push`, and what the server holds for them is never
  updated or pruned.
- `codehood push` works again with the current `mdq-py`. A new `push/wire.py`
  translates each question to what the server stores: `shuffle: "inherit"` is
  omitted, fields the server does not know (`diacritics`, `unmatched`,
  `incorrectFeedback`, `weight`, `grading`) are dropped and a fill-in's
  short-answer `accept` patterns become `oneOf`. Before, every question
  without an explicit `shuffle` was refused with `400`. `ordering` questions
  are still refused: the server has no such type.
- A failed push line shows the server's reason (`400 question.shuffle: ...`)
  instead of the bare URL.
- Question widgets no longer shuffle the choices when `shuffle` is the default
  `"inherit"`, which fixes the flaky widget tests.
- `[server].url` in `codehood.toml` defaults to `https://` when it has no
  scheme, and plain `http://` is refused except for `localhost`, so a login
  never sends the password unencrypted. `codehood login` offers the course's
  instructor as the default login.
- `codehood push` syncs grade columns. `codehood.toml` declares them in
  `[[grades.column]]` tables (`slug`, `title`, `kind` of `number` or `label`),
  in the order the Grades tab shows them. A column's values come from
  `grades.py`, whose `grade(student)` is called once per enrolled student
  with their exam results and `grades.csv` scores, and otherwise from the
  `grades.csv` column with the same header. `grades.csv` identifies students
  by `school_id`, `username`, `github` or `email`, takes `;` as delimiter and
  `,` as decimal separator, and a row for nobody enrolled is reported and
  skipped. A column is sent whole and only when it changed, and one the file
  no longer declares is deleted. A mistake in `grades.py`, `grades.csv` or
  the declared columns refuses the grade columns, leaves the server's alone
  and still pushes the rest, with exit code 1.
- `codehood grades` prints the table a push would send and writes nothing.
- `codehood.grades` exports `Student` and `ExamResult`, the types a
  `grades.py` is written against.
- The OpenAPI snapshot follows the server again: `ref` became `rev`, a
  resource has an `event`, and a question is a union. The generator maps a
  component that is a bare union to the union of its members.
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


