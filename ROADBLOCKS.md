# Road blocks

This document contains a list of roadblocks from the server component or other
libraries that prevent implementation of certain features. Document a roadblock
telling what is it preventing from being implemented, why, which system is
affected and propose actionable steps to resolve it. The docs are very brief and
contain a checkmark for implemented (but not yet reviewed or verified) solutions.

The checkbox can be in an intermediate state `[-]` to indicate work in progress.

Nothing here is fixable in this repository. Entries are verified against the dev
server at `http://localhost:4321`; the date of the last check is noted where it
matters.


## REST API Roadblocks

- [ ] A `FILE` resource cannot be uploaded over JSON. **Blocks `codehood push`
  for every `FILE` resource.** `ResourceCreate.data`'s `FILE` member is
  documented as `{"type": "string", "format": "binary"}`, but
  `src/core/schemas/base.ts` defines it as `z.instanceof(Buffer)`, which
  rejects every value `JSON.parse` can produce. The multipart route is gone
  too: `inMultipart`/`readMultipart` do not exist in `src/`, and no operation
  documents `multipart/form-data`. Only in-process callers can hand the service
  a real `Buffer`, which is why the seeded `syllabus` resource exists and
  nothing the CLI sends can join it. **Unblocks it**: decode before
  validating (`z.string().base64().transform(Buffer.from)`), or add and
  document a multipart branch. Base64 is the smaller change and matches what
  the spec already advertises. Until then push plans `FILE` resources and
  refuses to execute them, naming the blocker. (Verified 2026-09-20.)

- [ ] `cli.course.preSync` is a stub, and is not in the OpenAPI document at
  all. **Not blocking any more, but it costs a round trip per entity type.**
  `src/rpc/cli.ts` resolves the course, has its only query commented out, and
  returns `{resources: []}` unconditionally. **Worked around** in
  `push/run.fetch_server_state`, which reads the four list endpoints instead
  and projects each down to the markers `plan_push` compares; the wasted
  bandwidth is every full entity body, fetched only to compare one string. The CLI needs
  it to report `slug -> ref` for resources, exams and time slots,
  `slug -> version` for questions, and `(week, timeSlot) -> {ref, kind}` for
  calendar events -- markers only, never entity bodies. `kind` is what lets the
  CLI leave a `CANCELLED` event alone, which we have taken on as a client-side
  responsibility. This supersedes the manifest entry below. Full write-up in
  `dev/specs/to-do/calendar-exams.handoff.md`, item 3. (Verified 2026-09-23.)

- [ ] `TimeSlot` has no `ref` (nor `contentHash`) column, so there is nothing
  server-side to compare a local time slot against. Every other synced entity
  carries a marker the CLI writes and the server returns verbatim. **Worked
  around** in `push/run.fetch_server_state`, which recomputes each slot's ref
  from the fields the listing did return, through the same `push.calendar.
  TimeSlot` dataclass the local half uses -- so the recipe has to stay a pure
  function of `(slug, day, start, duration, title)` and nothing else.
  A `ref` column would drop that constraint. (Verified 2026-09-23.)

- [ ] Two time-slot constraint violations answer `500`, not `4xx`. **Not
  blocking; it costs the CLI a readable error.** `PUT .../time-slot` with a slug
  that overlaps an existing slot on the same weekday answers
  `{"code":"internal-error","status":500,"message":"This slot overlaps slot
  \"mon-14_00\" on MONDAY."}`, and `DELETE .../time-slot/{slug}` for a slot a
  calendar event still references answers a bare `500` with no message at all.
  Both are the server correctly refusing an invalid write, so the status is
  simply wrong: these are the client's fault and belong in the `4xx` range with a
  machine-readable code, the way the rest of the API reports a refusal.
  `push` surfaces them as `failed: Server error '500 Internal Server Error'`,
  which tells an instructor nothing. **Unblocks it**: map both to `409 Conflict`
  with a code like `slot-overlap` / `slot-in-use`. The CLI now orders its writes
  to avoid provoking either (see `docs/design/mapping-local-filesystem.md`,
  "Deletion and pruning"), so this is about the error surface, not the outcome.
  (Verified 2026-09-24.)

- [ ] `Question` has no `contentHash` field, only a free-form `version`
  string (`contentHash` exists solely on `CalendarEvent`). `codehood push`
  works around this by stuffing an `md5:<hex>` digest of the question
  file's raw bytes into `version` -- the same role `ref` plays for a
  resource, but hashing the file instead of the parsed fields. A real
  `contentHash` field, hashed the same way across every content type,
  would let push drop this special case.

- [ ] The question schema is `additionalProperties: false` and the server keeps
  an old copy of the MDQ schema, so it rejects fields `mdq` now emits (`weight`,
  `grading`, `diacritics`, `unmatched`, `incorrectFeedback`, a short-answer
  blank's `accept`/`reject`) and has no `ordering` type. `codehood push`
  translates each question in `codehood/push/wire.py`: it drops what the server
  cannot store and refuses `ordering`. See
  `dev/issues/server-mdq-atrasado-em-relacao-ao-mdq-py.md` in the server.

- [ ] `DELETE .../question/{slug}` soft-deletes: the row survives with
  `status: ARCHIVED` and is still returned by `GET .../question` with no
  status filter. Worked around in `fetch_server_state` by requesting only
  `statuses=["DRAFT", "PUBLISHED"]`, so an archived question reads as gone
  and a second `push` does not try to delete it again. Confirmed against
  the dev server: `DELETE .../question/big-o-warmup` returns
  `{"deleted": true}`, yet `GET .../question/big-o-warmup` immediately
  after still returns the row, unchanged but for `status`.

- [ ] Astro's cross-site guard refuses a bodyless `DELETE`. Nothing is blocked
  now, but the workaround is load-bearing and undocumented server-side.
  `DELETE .../resource/{slug}` carries no body, so `httpx` sends no
  `Content-Type`; Astro's `checkOrigin` reads that as an HTML form submission
  and answers `403 "Cross-site DELETE form submissions are forbidden"` before
  the route runs. These requests carry `Authorization: Bearer <key>` and no
  cookie, so there is no cross-site request to forge. **Worked around** in
  `api/base.get_client`, which sets `Content-Type: application/json` on every
  request (see `DEFAULT_HEADERS`). **Unblocks it properly**: exempt
  bearer-authenticated requests from `checkOrigin`.

- [-] No per-course manifest endpoint (FR-SYNC-002): "The server MUST expose a
  manifest endpoint per course listing the content it holds -- identifiers and
  modification markers, no bodies -- so the CLI can diff locally."
  `GET /api/course/{discipline}/{course}/resource` is the workaround: it
  answers the question but ships every full row -- titles, descriptions, whole
  `data` bodies -- to compare one string per resource. `cli.course.preSync` is
  the agreed answer; see the entry above.


## Resolved

- [x] Calendar events are reachable by natural key (2026-09-23).
  The collection is course-scoped at
  `/api/course/{discipline}/{course}/calendar-event`, and an event is keyed by
  `(week, timeSlot)`: `.../calendar-event/{week}/{timeSlot}` serves `GET`,
  `PATCH` and `DELETE`. No numeric course id is exposed to the CLI.

- [x] `/api/*/` implements `PUT` for upserting (2026-09-14). Satisfies
  FR-SYNC-003, so push never branches on create-versus-update. The mounting
  changed on 2026-09-20: `PUT` now sits on the *collection*
  (`PUT /api/course`, `PUT /api/course/{discipline}/{course}/resource`) with
  the natural key in the body, and is gone from the by-key paths.
- [x] Courses use natural primary keys (2026-09-13).
  `GET /api/course/{discipline}/{course}`, where `{course}` is
  `{instructor}_{edition}`. Same shape as the `Course URL` in `GLOSSARY.md`,
  so the CLI builds it offline from `codehood.toml`.
- [x] Resources addressed by natural key (2026-09-14), at
  `/api/course/{discipline}/{course}/resource/{slug}`. The CLI never learns an
  internal id (FR-SYNC-010).
- [x] Path parameters use `{id}` syntax with real `parameters` arrays
  (2026-09-13). `dev/issues/server-spec-omits-path-parameters.md` can close.
- [x] A resource's modification marker is the CLI's own (2026-09-20).
  `contentHash` is gone; `Resource.ref` is `z.string()`, stored and returned
  verbatim. The CLI owns the recipe outright -- see `push/resource.py`'s
  `content_ref` -- rather than reproducing the server importer's byte for
  byte. `src/commands/import-resources.ts` no longer constrains us.


## Not blockers, but constraints the CLI has absorbed

- **A course has no name.** `Course` carries `description` only; the name
  lives on `Discipline.name`, shared across every edition. So `push` sends the
  README's body as the description and ignores its H1 -- instructors do not
  manage disciplines.
- **Slugs are one flat segment.** A nested repository path cannot be a slug
  as-is, so `push/resource.slugify` flattens it.
- **A resource's type is no longer its own field.** `type` moved inside
  `data`, as the tag of the union member. There is no way to change a
  resource's type without replacing its `data` wholesale, which upsert does
  anyway.
- **`LINK` has no file to scan.** It is a member of the server's union that
  the repository cannot express until `.url` files land (see
  `docs/design/mapping-local-filesystem.md`).
