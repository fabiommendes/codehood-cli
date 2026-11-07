---
type: spec
status: draft
tags: [codehood-cli, push, exams, questions, mdq, sync]
relatedTo: [codehood-cli, push, push-questions]
---

# `codehood push`: syncing exams

The third slice of `codehood push`. The first two shipped the course row,
`resources/` and `questions/` ([push.md](../to-review/push.md),
[push-questions.md](../to-review/push-questions.md)); the calendar shipped
alongside them ([push-calendar.handoff.md](../to-review/push-calendar.handoff.md)).
`exams/` has never been touched: there is no `scan_exams`, no exam op in the
`PushOp` union, and nothing in `codehood/` calls an exam parser. `ch init`
scaffolds the directory and the push ignores it.

The authority for every mapping decision below is
[mapping-local-filesystem.md](../../../docs/design/mapping-local-filesystem.md),
sections "Exams" and "Questions".

## Scope

In:

- Every MDQ file under `exams/`, recursively. Created, updated and deleted.
- Inline questions, pushed as questions in their own right and referenced
  from the exam by slug.
- `include:` references, resolved against the local question set before
  anything is sent.
- The parts of the mapping's "Questions" section the current
  `scan_questions` does not yet honour (below, "Questions reconciliation").
- Migrating off the `mdq` API that no longer exists.

Out, and why:

- **Tag-driven question inclusion for practice exams.** The mapping's
  `tags` footnote defers it to a section that has not been written.
- **`extraTime`.** On `Exam` but not on `ExamCreate`. Server-owned.
- **Promoting an exam past `SCHEDULED`.** The repository has no vocabulary
  for `ONGOING`/`COMPLETED`; those are instructor actions.

## Prerequisites

Two, both outside this slice's code.

**The `mdq` public API changed under us.** `mdq/__init__.py` now exports
`load`, `parse`, `Loaded`, `Diagnostic`, `Severity`, `InvalidDocument`, and
no longer exports `parse_question` or `parse_exam`. `push/question.py` calls
`mdq.parse_question`, so `mypy codehood` already fails on it. The slice
starts by migrating `push/question.py`, `push/errors.py`,
`tests/test_push_plan.py` and `tests/test_push_run.py` to
`mdq.parse(source, kind="question")` / `mdq.InvalidDocument`.
`cli/show.py` and `widgets/questions/base.py` import from `mdq.parser`
directly and keep working untouched.

**`Exam` needs a `ref`.** Being added server-side with the `Resource.ref`
contract: opaque to the server, written by the client on create and upsert,
returned verbatim by `readExam` and `listExam`, never interpreted or
recomputed. Without it there is no convergence -- see "An exam's ref is
computed from the local file alone".

## Design decisions

### An exam's slug comes from its MDQ id, then from its path

MDQ accepts the id in the frontmatter or inline in the H1
(`# [midterm] Midterm Exam`), frontmatter winning. When the parsed exam
carries an id, that is the slug. Otherwise the slug is the flattened
relative path under `exams/` with the MDQ suffix dropped, by the same
`slugify` that resources and questions use: `exams/part1/exam.md` becomes
`part1-exam`.

A leading `_` on the filename or on any path component is stripped from the
slug rather than slugified into it. A slug collision stops the push, the way
a resource or question collision already does.

### Type precedence is positional, and read left to right

`quiz` or `practice` appearing in any path component or in the filename
sets the type; the first occurrence in the path-then-filename reading order
wins; `EXAM` otherwise. `practice/midterm-quiz.md` is `PRACTICE`, because
`practice` comes first.

This is what lets an instructor sort exams into `exams/quiz/`,
`exams/practice/` and `exams/exam/` and have the layout mean something. It
is also why `file_tracker.scan_files` has to be rewritten for exams: it
currently hardcodes `exams/draft`, `exams/practice` and `exams/published`
as the only three directories, does not recurse, and maps them onto
`FileType.EXAM_DRAFT`/`EXAM_PRACTICE`/`EXAM_PUBLISHED`, which correspond to
nothing in the mapping. One `FileType.EXAM` replaces all three; type and
status are derived from the path, not encoded in the `FileType`.

### Status is derived, never chosen, and never demotes a live exam

In order: `DRAFT` if the filename or any path component starts with `_`;
otherwise `SCHEDULED` if the exam declares a start; otherwise `DRAFT`.
Deleting the file means `ARCHIVED`.

With one guard. `Exam.status` also holds `ONGOING` and `COMPLETED`, which
the server reaches on its own as an exam runs. Pushing a derived
`SCHEDULED` over a server-side `ONGOING` would drag a running exam
backwards. So `status` is omitted from the payload when the server reports
the exam as `ONGOING` or `COMPLETED`, and the CLI warns instead.

This is the same shape as the calendar's `CANCELLED` rule: a state the
server owns, which the CLI recognises and refuses to overwrite. It is why
`ServerExam` carries two fields rather than one hash.

### `duration` and `scheduledAt` are never blanked

Both may be set by an instructor action server-side, so a local file that
omits them must not overwrite with `null` -- the mapping's footnotes are
explicit. They are therefore omitted from the payload rather than sent as
`null`, which also keeps them out of the `ref` (next decision).

`duration` is an ISO duration in MDQ, a `timedelta` on the parsed model,
and `{hours, minutes}` on the wire. The conversion is a plain total with no
24-hour wrap: a two-day take-home is `{hours: 48}`.

`start` is a `datetime | date` on the parsed model. A bare date becomes
midnight; a naive datetime is read as UTC, the same convention
`plan._timestamp` already uses for the course row.

### `meta.codeRun` maps to `allowCodeRun`, and absence is `null`

The repository declares whether the exam lets students run code in the
browser with `meta: { codeRun: true|false }` in the exam's frontmatter. The
mapper sends it as `allowCodeRun` (`ExamCreate`/`ExamUpdate`). Without
`meta.codeRun` it sends `allowCodeRun: null`, which means "follow the exam
type's default". Unlike `duration` and `scheduledAt`, the key is always
present: the repository owns this value (ADR 0012), so removing the key from
the file must clear a previous `true`/`false` on the server. Any non-boolean
`meta.codeRun` is a local error that stops the push. `allowCodeRun` takes
part in the `ref`.

### An exam's ref is computed from the local file alone

Sha-256 over a canonical JSON rendering of the fields the local file
actually declares -- the same recipe as `resource.content_ref`, reusing its
prefix discipline so a change of recipe invalidates loudly.

Fields the local file omits do not enter the digest. That is what makes the
previous decision work: a server-set `duration` cannot perturb the ref, so
it is never re-pushed and never blanked.

The ref therefore means "the local file has not changed", not "local and
server agree" -- exactly the contract `Resource.ref` already has. An
instructor who edits an exam's title server-side keeps that edit until the
local file changes. Accepted, and the same trade every other entity makes.

### Includes resolve against the local question set, through a loader

The mapping's resolution ladder, first match wins:

1. exact slug match;
2. filename match, if that filename is unique across the question set;
3. path match, if the id looks like a relative path -- resolved first
   relative to the including exam's own directory under `exams/`, then
   relative to `questions/`, then from the repository root. Separators are
   `/` in the file and normalised to the platform's.

No match is an error that stops the push, before any network call.

`mdq` delegates resolution entirely to a `QuestionLoader`, so this is a
loader built over the `QuestionFile`s `scan_questions` already yields. Two
things follow that are worth stating, because both are easy to get wrong:

- **`mdq.loaders.FileLoader` is not used, and its bug is not ours.**
  `BACKLOG.md`'s "Exam includes do not resolve" is about `FileLoader`
  looking for `.mdq.md`/`.mdq` while `ch init` writes `.md`. We never call
  it. The entry can be closed as not-applicable rather than fixed.
- **Passing no loader is not an option.** `loading._resolve_include` emits
  a hard `include-not-found` error when the loader is `None`, which makes
  `Loaded.document` `None`. An exam with an include cannot be parsed
  without a loader, so the CLI cannot "leave includes alone and read the
  ids off the raw dict".

### Provenance of a resolved include rides in `meta`

The exam payload wants `questions: [{slug}]` -- references. But `mdq`
inlines a resolved include into `Exam.questions` and drops the fact that it
came from an include, so after parsing, position *n* gives no way to tell
"included, use the question's own slug" from "inline, mint
`<exam-slug>-<id>`".

`QuestionLoader.load` may return an already-parsed `Mapping` instead of
source text. The loader therefore returns the question's parsed dict with
`meta["codehood.slug"]` set to the slug it resolved, and the exam mapper
reads that key back off each parsed question to recover the distinction.

The marker never reaches the wire: questions are pushed from
`scan_questions`, which parses the files independently, and the exam
payload carries only slugs. If a question file declares its own `meta`, the
key is merged in rather than replacing it.

This is the only provenance channel `mdq` exposes. If it grows a real one,
this is the single place that changes.

### Inline questions are pushed as questions

An inline question gets slug `<exam-slug>-<question-id>`, or
`<exam-slug>-q<n>` when it declares no id, where *n* is its 1-based
position among all of the exam's questions -- not a counter that advances
only over the unidentified ones. `version` is the md5 of the exam file's
bytes, since that is the file the question actually lives in.

Because the exam references them by slug, they must exist as `Question`
rows before the exam is written. See the op order below.

### Deletion soft-deletes, and the listing is filtered to compensate

`deleteExam` archives rather than removes, the way `deleteQuestion` does.
An unfiltered `listExam` would keep reporting an archived exam as present,
the CLI would re-plan its deletion on every run, and convergence would
fail. So `fetch_server_state` lists with the statuses a repository can
still account for and treats `ARCHIVED` as gone -- the workaround already
in place for questions, recorded in `ROADBLOCKS.md`.

**Unverified.** The dev server was down when this was written, so
`deleteExam`'s actual behaviour is inferred from the mapping and from
`deleteQuestion`'s confirmed behaviour. Confirm it live before trusting it,
and if it hard-deletes, drop the filter.

## Questions reconciliation

Three places `scan_questions` predates the mapping's "Questions" section.
All three are in scope here, because nothing parsed an exam before and so
none of them could be exercised.

| Mapping rule | Today | Fix |
| :--- | :--- | :--- |
| `id` → `slug`, flattened path only as fallback | Always the flattened path | Prefer the parsed `id` |
| `DRAFT` for a `_`-prefixed file or directory, `PUBLISHED` otherwise | Always `DRAFT` | Derive from the path; strip the `_` from the slug |
| Title falls back to the title-cased filename, `-`/`_` → space | No fallback | Fill it in when MDQ declares no title |

The status change supersedes `push-questions.md`'s "Status defaults to
`DRAFT`", which was written before the repository had any vocabulary for
status. The `_` prefix is that vocabulary.

## Architecture

Unchanged: functional core, imperative shell.

| Module | Role |
| :--- | :--- |
| `push/exam.py` | Pure: `scan_exams`, `ExamFile`, `exam_ref`, the slug/type/status derivations |
| `push/question.py` | Pure: gains the id/status/title rules and the `QuestionIndex` the loader resolves against |
| `push/plan.py` | Pure: `UpsertExam`/`DeleteExam`/`WarnExamLive` ops, planned by diff |
| `push/run.py` | Shell: projects `listExam` into `ServerExam`, executes the ops |
| `cli/push.py` | Shell: wiring, `describe`, exit code |
| `repo/file_tracker.py` | The `exams/` walk, rewritten |

`LocalState` gains `exams: tuple[ExamFile, ...]`. `ServerState` gains
`exams: Mapping[str, ServerExam]`, where `ServerExam` is `(ref, status)`.

### Op order

Questions before exams, and deletions before writes:

1. resources, questions (including the ones derived from exams)
2. delete exams
3. upsert exams
4. the calendar block, unchanged

An exam references its questions by slug, so a question it needs must
exist first. This is the same class of constraint the calendar's
slot-before-event ordering solves, and the same cost for getting it wrong:
not corruption, but a one-push change turning into a two-push one.

## CLI surface

No new command, no new flag. `--dry-run` prints exam ops; `--prune/--no-prune`
governs exam deletions like every other deletion.

```
planned  question midterm-factorial
planned  exam midterm (EXAM, SCHEDULED)
planned  delete exam stale-quiz
planned  exam finals kept (server reports ONGOING)
```

## Acceptance

- `ch push` against a repository with exams leaves the server holding
  exactly the exams the filesystem accounts for, with their questions
  resolved and present.
- A second `ch push` immediately after plans **nothing but the course row**.
  This is the property most likely to be quietly wrong and the one worth
  the most test pressure.
- Verified against the live dev server, not only against mocks. Two spec
  bugs in the calendar slice survived a full green unit suite and surfaced
  on the first real push.
- `ruff check`, `ruff format --check`, `mypy codehood` and `pytest` clean.
- Server gaps recorded in `ROADBLOCKS.md`; `CHANGELOG.md` updated; this
  spec moved to `dev/specs/to-review/`.
