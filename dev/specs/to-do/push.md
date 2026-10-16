# `codehood push`: syncing a course repository

`codehood push` makes the server's copy of a course match the local
repository. The repository is the source of truth; the server holds a
projection of it.

This spec covers the first slice: the course's own description, and its
resources. Questions, exams and the calendar are separate specs.

## Scope

In:

- The course row itself, created if the server does not have it.
- `README.md`'s body as the course description.
- `resources/`, synced in full: created, updated, and deleted.

Out, and why:

- **`FILE` resources.** Blocked on the server: uploads now fold into the
  resource endpoint as `multipart/form-data`, and that branch is not
  implemented (see `ROADBLOCKS.md` item 1). The planner still plans them, so
  the work lands as one interpreter branch when the upload does.
- **`LINK` resources.** No natural file shape to infer one from. Waiting on
  the resource manifest in `BACKLOG.md`.
- **Questions, exams, calendar, roster.** Later roadmap items.

## The contract

The server repository's `dev/requirements/03-content-sync.md` is
authoritative. The requirements this slice leans on:

- **FR-SYNC-004** — the server never infers deletions. The CLI plans; the
  server executes what it is told.
- **FR-SYNC-005** — a sync is not atomic. An interrupted push leaves a
  partial but coherent state, and re-running converges.
- **FR-SYNC-006** — concurrent pushes are last-write-wins.
- **FR-SYNC-010** — content is addressed by a natural key derived from its
  path.
- **FR-SYNC-011** — a rename is a delete plus a create.
- **FR-SYNC-013** — deleting a resource deletes the blob and leaves the URL
  as a tombstone.

## Design decisions

### The README's H1 is ignored

`README.md`'s body, everything after the H1 up to the next heading, becomes
the course's `description`. The H1 itself goes nowhere.

The server has no course name. A name lives on `Discipline.name`, shared
across every edition of `cs101` and every instructor teaching it, and
instructors do not manage disciplines. A per-course file must not rename a
shared row, so the H1 stays a local title for whoever reads the repository.

`repo/_layout.py`'s `render_readme` docstring currently claims otherwise and
is corrected as part of this work.

### The course is created when absent, updated when present

A course is addressed by its natural key,
`/api/course/{discipline}/{instructor}_{edition}`, built offline from
`codehood.toml`. This is the same shape as the `Course URL` in
`GLOSSARY.md`.

Push `PUT`s the course, which creates it when absent and updates it
otherwise, copying `startAt`/`endAt` from the edition, since the calendar
that would supply real dates is a later slice. If the discipline or the edition does not exist, push fails and says
so: creating either is an admin's job, not a side effect of a sync.

### A resource's slug is its flattened path under `resources/`

`resources/week1/slides.pdf` has the slug `week1-slides`. Subdirectories are
preserved in the repository, because instructors will build them whatever the
CLI does, and flattened on the way out, because the server constrains `slug`
to `^[a-z0-9][a-z0-9._-]*$` and serves it as a single path segment.

The derivation: drop the extension, lowercase, replace every run of characters
outside `[a-z0-9._-]` with a single `-`, and strip leading and trailing `-`.
`week1/Slides (final).pdf` becomes `week1-slides-final`.

Flattening collides where the tree did not: `week1/slides.md` and
`week1-slides.md` both want `week1-slides`, as do `week1/slides.pdf` and
`week1/slides.md`. Any collision refuses the whole push, naming every file
that wants the contested slug. Push does not guess, and does not push a
partial repository on the way to an error.

`repo/file_tracker.py` currently globs `resources/*`, which yields
subdirectories as resources. That is a bug and is fixed here: the scan
recurses, and only files become resources.

### Type is inferred from the extension

| Extension                | Type   | Fields                                      |
| :----------------------- | :----- | :------------------------------------------ |
| `.md`, `.markdown`       | `MD`   | `data` is the body, front matter stripped   |
| Known source extensions  | `CODE` | `data` is the body, `extra` is the language |
| Anything else            | `FILE` | `fileId` points at the uploaded blob        |

Title, in order: the `title` key in an `.md` file's YAML front matter, then
its first H1, then the filename stem. Description comes from a
`description` key in front matter, and is otherwise null.

An explicit manifest declaring all of this, and `LINK` resources with it,
is in `BACKLOG.md`.

### There is no local state

Push hashes the repository, asks the server what it holds, and plans the
difference. `.codehood/` stores nothing, and deleting it changes nothing.

A local cache of "what was last pushed" is only ever an optimisation, and
one nobody has measured a need for: a course repository is Markdown and a
few PDFs, and hashing it is milliseconds. A cache that can disagree with the
server can also make push silently wrong, which is a bad trade for one
saved round-trip.

This deletes `repo/history.py` and the `history` parameter threaded through
`find_diffs`.

Until the server grows the manifest endpoint FR-SYNC-002 requires, push
reads `GET /api/course/{discipline}/{course}/resource` and ignores every
field but `slug` and `contentHash`.

### Deletion is part of the sync

A resource on the server whose file is gone locally is deleted. The
repository is the source of truth: a mistake is fixed by fixing the
repository and pushing again.

This destroys blobs and leaves tombstones (FR-SYNC-013), so push prints
what it will delete before doing it.

### `contentHash` mirrors the server's own importer

The server's `src/commands/import-resources.ts` computes the hash the CLI
must produce. Reproduced exactly, key order included, or every resource
reads as changed on every push:

- `FILE`: the blob's sha-256 as `file`, everything else as below.
- Every type: sha-256, hex, over the JSON serialisation of
  `{type, title, description, data, extra, file}`, with absent fields as
  `null` and no whitespace between tokens.

A test pins the CLI's output against a vector taken from the importer.

## Architecture

Functional core, imperative shell, per `CLAUDE.md`. New package
`codehood/push/`.

The core is a pure generator. It receives the repository's files and the
server's current state, and yields a plan: a sequence of frozen dataclasses
describing side effects, containing no client, no ids, and no `run()`.

```python
PushOp = UpsertCourse | UpsertResource | DeleteResource
```

There is no separate upload operation. The server's `blob-attachments.md`
folds bytes into the resource endpoint as `multipart/form-data`, with `data`
carrying the payload for every type: a URL for `LINK`, the text for `MD` and
`CODE`, the bytes for `FILE`. So one `UpsertResource` describes a resource
whole, whatever its type, and the interpreter picks `application/json` or
`multipart/form-data` from the payload it holds.

Every write is a `PUT`. The server registered upsert on 2026-09-14, so push
never branches on create-versus-update: `upsertCourse` keys on
`/api/course/{discipline}/{course}`, `upsertResource` on
`/api/course/{discipline}/{course}/resource/{slug}`. Both are idempotent per FR-SYNC-003, which is what makes FR-SYNC-005's
"re-running converges" hold without the CLI tracking anything.

That removes the one data dependency a push had. Until 2026-09-14 a `FILE`
meant `UploadFile -> fileId -> UpsertResource`, and the plan carried a
`FileRef(hash)` the interpreter resolved against a `dict[str, int]`. With
bytes travelling inside the resource write, the plan is a flat list of
independent operations and neither the indirection nor any sequencing
combinator is needed.

The shell is one function, `run_plan(ops, client)`, yielding one result per
op. It is the only thing in the package that touches HTTP.

Consequences worth the trade:

- `--dry-run` is "print the plan, don't call `run_plan`".
- Every planning test asserts on a list of dataclasses. No HTTP, no mocks.
- FR-SYNC-005's "re-running converges" is a property test over the planner:
  applying a plan and re-planning yields an empty plan.

`codehood/actions/` is left untouched by this work. Its `Action`/`Seq`/`Try`
combinators have no caller, and `Seq` discards its first action's result by
design, so it cannot express the one dependency push has.

## CLI surface

```
codehood push [PATH] [--dry-run] [--no-prune]
```

- `PATH` defaults to the current directory and must be a course repository.
- `--dry-run` prints the plan and exits 0 without a single write.
- `--no-prune` plans deletions and reports them but does not execute them.
  Deletion is on by default: the repository is the source of truth.

Output is one line per operation, in plan order, with its outcome. A push
where every operation succeeds and nothing changed prints nothing but a
summary.

Exit codes: 0 when every operation succeeded, 1 when any failed. A failure
does not stop the push (FR-SYNC-005): remaining operations still run, and
the failures are listed at the end. The exception is the course row: every
other operation hangs off it, so when its `PUT` fails (say, the edition does
not accept new courses) the rest are reported as `skipped ... not attempted`,
none is sent, and the summary counts them apart from the failures.

## Proof

- Planner unit tests: a repository fixture plus a fake server state in,
  an expected list of ops out.
- Convergence: plan, apply against a fake, re-plan, assert the second plan
  is empty.
- Hash vector pinned against `import-resources.ts`.
- Collision, missing discipline, and missing edition each produce a named
  error, not a traceback.
- End-to-end against the dev server on `localhost:4321`: `init` a course,
  push it, screenshot `/cs101/ada_2026-1/resources`, delete a local file,
  push again, screenshot the resource gone.

The end-to-end run covers `MD` and `CODE` resources. `FILE` waits on the
upload endpoint.
