---
type: spec
status: review
tags: [codehood-cli, push, exams, questions, mdq, sync]
relatedTo: [codehood-cli, push, push-questions, sync-fase-1]
---

# `codehood push`: syncing exams

`exams/` is the last directory `ch init` scaffolds that `ch push` ignores.
There is no `scan_exams`, no exam entity in `plan_sync`, and
`repo/file_tracker.py` still maps `exams/{draft,practice,published}` onto
three `FileType`s that correspond to nothing in the mapping.

The authority for the mapping is
[mapping-local-filesystem.md](../../../docs/design/mapping-local-filesystem.md),
sections "Exams" and "Questions". The sync rules are those of
[sync-fase-1.md](../to-review/sync-fase-1.md): exams join `plan_sync` as one
more entity kind, with a base, a projection and the three-way decision
table.

This rewrite replaces the draft written before sync phase 1 and before
`mdq` kept include blocks unresolved. Both prerequisites of that draft are
gone: `mdq.parse` is already in use, and the server stores `Exam.rev`.

## Scope

In:

- Every MDQ file under `exams/`, recursively. Created, updated, archived.
- Inline questions, pushed as questions in their own right and referenced
  from the exam by slug.
- `include:` and `includeAll:` blocks, resolved against the local question
  set before anything is sent.
- Rewriting the `exams/` walk in `repo/file_tracker.py`.

Out:

- **`includeAll` with `max`.** Random selection per push would never
  converge. A local error until the server can hold a question pool.
- **`penalty`, `grading`, `shuffle`, `attachments`.** MDQ exam fields with
  no column on `ExamCreate`, and no server code that would apply them. A
  non-default value is a warning (`IgnoredExamPolicy`), not an error, and
  goes to `ROADBLOCKS.md`. A handoff to the server proposes one nullable
  `Exam.policy` JSON column with `{penalty, grading, shuffle}`, applied by
  grading and by question order. Once it is in the OpenAPI document, the
  CLI sends it and it enters the `rev`.
- **`extraTime`, exceptions, rubrics.** Server-owned.
- **Promoting an exam past `SCHEDULED`.** Instructor actions.
- **`If-Match` on writes.** Pending for every entity in the sync RFC, not
  specific to exams.

## Design decisions

### Slug: MDQ id, then the path

The parsed exam's `id` (front matter or H1) is the slug, through
`slugify_text`. Without one, the flattened path under `exams/` with the
suffix dropped, through `slugify`: `exams/part1/exam.md` is `part1-exam`. A
leading `_` on any component is stripped first, as `question_slug` does. A
collision stops the push before any network call, as for questions.

### Type: first `quiz`/`practice` in path order

`quiz` or `practice` as a word in any path component or in the filename
sets the type; the first one in path-then-filename order wins; `EXAM`
otherwise. `practice/midterm-quiz.md` is `PRACTICE`. "As a word" means a
`-`/`_`/`.`-separated token, so `quizzical.md` is an `EXAM`.

### Status: derived from the file, never demotes a running exam

`DRAFT` if any component starts with `_`; `SCHEDULED` if the exam declares
`start`; `DRAFT` otherwise. A deleted file is a `Prune`, which the server
turns into `ARCHIVED` (`exam.service.ts`, soft delete, confirmed in code).

The server also moves an exam to `ONGOING` and `COMPLETED`. Status order is
`DRAFT < SCHEDULED < ONGOING < COMPLETED`; when the server is at
`ONGOING` or `COMPLETED`, the push keeps the server's status and warns
(`KeptExamLive`), the same shape as `join_status` for questions. Below
that, the file wins in both directions: removing `start` from a
`SCHEDULED` exam sends it back to `DRAFT`. Status stays out of the
three-way comparison, as it does for questions (sync R10).

### `duration` and `scheduledAt` are never blanked

An instructor action may set either server-side. When the file omits one,
it is never sent as `null`, and what the comparison sees depends on the
base:

- The base holds the key (the CLI wrote it before): the local payload takes
  the base's value, so dropping `start` is "no change" for `scheduledAt`.
  Declaring a new value later is a plain local change, not a conflict, and
  an instructor change while the file omits the key is a `Pull`.
- The base lacks it: the key is dropped from base and server payloads
  before the comparison. A value only the server ever set never shows as a
  change.

Removing `start` still moves the status to `DRAFT`; status is compared
apart (below).

`duration` is a `timedelta` in MDQ and `{hours, minutes}` on the wire, a
plain total with no 24 h wrap. `start` is `datetime | date`: a bare date is
midnight, a naive datetime is UTC, as `plan._timestamp` does.

### Other fields

| MDQ | Wire | Rule |
| :-- | :--- | :--- |
| `title` | `title` | Fallback: title-cased filename, as for questions |
| `description` | `description` | `null` when absent |
| `instructions` | `preamble` | `null` when absent |
| -- | `format` | `MARKDOWN` |
| `tags` | `tags` | `[]` when absent |
| `meta.codeRun` | `allowCodeRun` | `null` when absent; non-boolean is a local error |

These are repository-owned (ADR 0012): absence clears the server value.

### Questions: `{slug, version: null}`

The exam sends each question as `{slug, version: null}`, which the server
reads as "the question's latest version". Pinning the version would make
every question edit re-push every exam that holds it, and an `ONGOING`
exam could not take a typo fix. Not pinning means the exam payload depends
only on the exam file and the slugs it resolves to.

### Includes resolve through a `QuestionBank` over `scan_questions`

`mdq.parse(..., kind="exam")` keeps `Include`/`IncludeAll` entries
unresolved, so provenance is free: an `Include` contributes the slug it
resolves to, an inline question contributes its minted slug. `Exam.resolve`
is not called; the CLI walks `exam.questions` itself.

`include: <id>` follows the mapping's ladder, first match wins:

1. exact slug;
2. filename stem, if unique across `questions/`;
3. relative path, if the id contains `/` or ends in an MDQ suffix: relative
   to the exam's own directory, then to `questions/`, then to the root.

`includeAll: <query>` uses `mdq`'s query over a `QuestionBank` built from
the scanned `QuestionFile`s (ids are slugs, tags from the parsed
question), all matches, sorted by slug, skipping slugs the exam already
holds. With `max` it is a local error (see Scope).

An unresolved include, or one that points at an `InvalidQuestion` or at a
question under `[push] exclude`, makes the exam an `InvalidExam`: reported,
the push continues, the server's copy is kept (`Keep`), exit code non-zero.
Same contract as `InvalidQuestion`.

### Inline questions are questions

Slug `<exam-slug>-<id>`, or `<exam-slug>-q<n>` with *n* the 1-based
position among all entries. They join `LocalState.questions` as ordinary
`QuestionFile`s with `path` set to the exam file, status following the
exam's `_` rule, and `version` the md5 of the canonical JSON of the parsed
question, so editing one inline question does not bump its siblings.

An inline `code` question resolves its linked test sources against the exam
file's directory, through the existing `question.resolve_exam_sources`.

An inline slug that collides with a file under `questions/` stops the push,
as any slug collision does.

### Three-way sync

`exam` joins `EntityKind`, `BaseState.exams`, `ServerState.exams` and
`write_rank`. `exam_payload(file)` is the wire payload without `rev`;
`project_exam(read model)` maps `Exam` back to it (sync R3) and drops
`status`. Tags are sorted on both sides: the server reads them in primary
key order. `rev` is the sha-256 of the canonical payload with the
`REF_PREFIX` discipline of `resource.content_ref`.

`fetch_server_state` lists exams with `statuses=DRAFT,SCHEDULED,ONGOING,COMPLETED`:
an `ARCHIVED` exam is gone, as for questions. An exam under that slug
coming back is an `upsert`, which the server revives because the push
sends a status.

### Op order

`write_rank` puts exam deletions after question writes and exam upserts
after both, so every slug an exam references exists when it is written.
The server does not stop the deletion of a question an exam still holds,
so the plan does: a question held by an exam the plan keeps (`InvalidExam`,
or `KeptExamLive` whose file is gone), by that exam's base or server
payload, is never pruned. Its decision becomes `Skip`. An inline question
of an invalid exam, or an included file deleted under a kept exam, would
otherwise be pruned.

## Architecture

| Module | Change |
| :--- | :--- |
| `push/exam.py` | New, pure: `scan_exams`, `ExamFile`, `InvalidExam`, `exam_slug`, `exam_type`, `exam_status`, `exam_payload`, `exam_rev`, the local `QuestionBank` |
| `push/question.py` | `QuestionFile` from an inline question |
| `push/wire.py`, `push/project.py` | `exam_payload`, `project_exam` |
| `push/base.py` | `BaseState.exams` |
| `push/plan.py` | `UpsertExam`, `DeleteExam`, `KeptExamLive`, `_sync_exams`, `write_rank` |
| `push/run.py` | list exams, execute `upsertExam`/`deleteExam` |
| `cli/push.py` | `describe` for the new ops and notices |
| `repo/file_tracker.py`, `repo/diff.py` | One `FileType.EXAM`, recursive walk |
| `tests/examples/*/exams` | Move `published/`, `draft/` to the new layout |

## CLI surface

No new command or flag.

```
planned  question midterm-factorial
planned  exam midterm (EXAM, SCHEDULED)
planned  delete exam stale-quiz
kept     exam finals status ONGOING (file says SCHEDULED)
invalid  exam exams/broken.md: include 'nope' matches no question
```

## Tasks

- T1. `push/exam.py` pure core: slug, type, status, payload, rev, bank,
  include ladder, inline questions. Unit + Hypothesis (slug/type laws).
- T2. Base, projection, `_sync_exams`, `write_rank`. Property test for
  sync R3 on exams; plan tests for the status guard and the omitted
  `duration`/`scheduledAt`.
- T3. Shell: `fetch_server_state`, executor, `describe`, `file_tracker`.
- T4. Fixtures and the integration test against the live dev server.

## Acceptance

- `ch push` on a repository with exams leaves the server holding exactly the
  exams the filesystem accounts for, with their questions present.
- A second `ch push` right after plans nothing.
- A server-set `duration` on an exam whose file omits it survives a push.
- An exam moved to `ONGOING` on the server keeps that status through a push.
- Verified live against the dev server.
- `ruff check`, `ruff format --check`, `mypy codehood`, `pytest` clean.
- `ROADBLOCKS.md` (exam fields without a column), `CHANGELOG.md`, the
  BACKLOG entry "Exam includes do not resolve" closed, spec moved to
  `dev/specs/to-review/`.
