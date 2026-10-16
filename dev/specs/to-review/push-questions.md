---
type: spec
status: draft
tags: [codehood-cli, push, questions, mdq, sync]
relatedTo: [codehood-cli, push]
---

# `codehood push`: syncing questions

The second slice of `codehood push` (see [push.md](push.md) for the first:
the course row and `resources/`). This one syncs `questions/` — created,
updated, and deleted — so the server's question bank for a course matches
the repository.

Exams stay out. They reference questions by slug, so they only make sense
once questions land, and they need their own delivery/scheduling design.

## Scope

In:

- Every MDQ file under `questions/`, recursively.
- Created, updated, and deleted, the same three-way diff `resources/` gets.
- Parsing and validation, client-side, via the `mdq` package.

Out, and why:

- **Exams.** Next slice.
- **`ordering` questions.** `mdq` parses them; the server's `question`
  union has no `ordering` member. Planned, refused at execution with a
  clear message, the way a `FILE` resource already is.

## Design decisions

### A question's slug is its flattened path under `questions/`

`questions/week1/big-o.md` has the slug `week1-big-o`.

The prompt asked for `<subfolder>/<filename>`. The server will not take
it: `slug` is constrained to `^[a-z0-9][a-z0-9._-]*$` and served as a
single path segment, so a `/` cannot survive the round trip. The
flattening rule is therefore the one `resources/` already uses
(`push.resource.slugify`): drop the extension, lowercase, replace every
run of characters outside `[a-z0-9._-]` with a single `-`, strip leading
and trailing `-`.

Collisions refuse the whole push, before any file is read or any request
is sent, naming every file that wants the contested slug. `questions/` and
`resources/` are separate namespaces on the server, so they are checked
separately and never collide with each other.

`repo/file_tracker.py` globs `questions/*`, which neither recurses nor
yields anything inside a subdirectory. That is fixed here, the same way
`resources/` was: the scan recurses, and only files become questions.

### The hash rides in `version`, not `contentHash`

The prompt specified a `contentHash` field. The server's `Question` has
no such field — `contentHash` exists only on `CalendarEvent`. What
`Question` does have is `version`, a free-form non-empty string the
server stores and hands back on every read, exactly the role `ref` plays
for a resource.

So `version` carries the digest: `md5:<hex>`, the md5 of the question
file's bytes, as the prompt asked for md5. The `md5:` prefix names the
recipe, so changing it later invalidates old versions loudly instead of
colliding with them.

This differs from a resource's `ref`, which digests the *parsed* fields.
A question hashes the *file*, which is cheaper, and means a whitespace-only
edit re-pushes. That is the trade the prompt asked for and it is the
conservative direction: a spurious push is a no-op, a missed push is a
bug.

`listQuestion` already returns `version`, so one `GET` gives the whole
`slug -> version` map and nothing is pushed twice. The hash-to-slug
manifest endpoint the prompt anticipates would replace that one call and
nothing else.

### Parsing happens in the core, `mdq` is the parser

`QuestionCreate.question` is a structured, discriminated union — the
server takes a parsed question, not Markdown. The `mdq` package (a
sibling project, already a dependency) is the parser of record.

`push/question.py` is pure: it reads files, parses them, hashes them, and
yields `QuestionFile`s. A `mdq.ParseError` is reported against the file
that caused it and refuses the whole push, for the same reason a slug
collision does: push does not upload half a question bank on the way to
an error.

### `weight` and `grading` are dropped on the wire

`mdq`'s models carry two fields the server's schema forbids
(`additionalProperties: false`): `weight` and `grading`. Sending them
gets `400 Unrecognized keys`.

They are dropped in `push/run.py`, the one place that already translates
the core's types into generated request models. Dropped explicitly, by
name, not by filtering to an allowlist — an allowlist would silently
swallow the next field `mdq` grows, where an explicit drop list lets it
fail loudly.

This is a server gap, not a CLI preference: per-question weight and
grading policy have nowhere to live server-side. Recorded in
`ROADBLOCKS.md`.

Every other `mdq` field already serializes to the name the server wants —
`mdq` sets a camelCase alias generator, so `model_dump(by_alias=True)`
gives `answerKey`, `decimalPlaces`, `openEnded`, and friends for free.

### Status defaults to `DRAFT`

`QuestionCreate.status` is one of `DRAFT`/`PUBLISHED`/`ARCHIVED`. A
repository has no vocabulary for it yet, so every pushed question is
`DRAFT`, and a question already `PUBLISHED` on the server stays that way
unless its content changed. Promoting a question is a server-side action
until the repository grows a way to say so.

### `[push] exclude` keeps files out of a push

`codehood.toml` takes an optional `[push]` table with `exclude`, a list of
gitignore-like patterns relative to the repository root (`codehood/globs.py`):
`*` and `?` stay inside one path segment, `**` crosses directories, a pattern
naming a directory covers everything under it, no negation. Patterns are
anchored at the root, not matched at any depth.

- Applies to files under `questions/` and `resources/`, the two trees pushed
  file by file. `exams/` is not pushed yet.
- An excluded file is never read or parsed, so a draft that does not parse or
  an `ordering` question (still refused, see "Out, and why") no longer blocks
  the push.
- The server is left alone: the plan skips the delete of a slug whose local
  file is excluded, so `--prune` never removes it, and nothing is upserted.
  Dropping a pattern later makes the file an ordinary local file again.
- Push prints one `excluded  <path>` line per file and `, N excluded` at the
  end of the summary. Excluded files never make the exit code non-zero.
- An excluded resource cannot be linked from `calendar.md`: the link is an
  error, as for any file not pushed.

## Architecture

Unchanged from `push.md`: functional core, imperative shell.

| Module                | Role                                                       |
| :-------------------- | :--------------------------------------------------------- |
| `push/question.py`    | Pure: `scan_questions`, `question_version`, `QuestionFile`  |
| `push/plan.py`        | Pure: `UpsertQuestion`/`DeleteQuestion` ops, planned by diff |
| `push/run.py`         | Shell: reads server state, executes ops, translates payloads |
| `cli/push.py`         | Shell: wiring, output, exit code                             |

`plan_push` grows two parameters (`questions`, `server_questions`) and
yields the two new op types after the resource ops. It stays a generator
and stays pure.

`fetch_server_state` grows a third return value: `{slug: version}` from
`listQuestion`, empty when the course does not exist yet.

## CLI surface

No new command and no new flag. `--dry-run` prints question ops alongside
resource ops; `--prune/--no-prune` governs question deletions the same way
it governs resource deletions. A failed question does not stop the push,
and the exit code is 1 if anything failed.

```
planned  question week1-big-o
planned  delete question stale-warmup
```

## Acceptance

Against `tests/examples/ada-basic`, which holds exactly two questions
(`example.md`, `fat.md`): `ch push` leaves the server's question bank for
`cs101/ada_2026-1` holding exactly those two, whatever it held before. A
second `ch push` immediately after plans zero question operations.

## The contract both halves build against

```python
# codehood/push/question.py  -- pure
type AnyQuestion = mdq.Question  # the discriminated union mdq.parse_question returns

@dataclass(frozen=True)
class QuestionFile:
    slug: str            # flattened path, `push.resource.slugify`
    version: str         # "md5:<hex>" over the file's bytes
    question: AnyQuestion
    path: Path

def question_version(raw: bytes) -> str: ...
def scan_questions(root: Path) -> Iterator[QuestionFile]: ...
    # Raises SlugCollisionError (eagerly, before any parse) and
    # QuestionParseError (on the first file mdq refuses).

# codehood/push/errors.py
class QuestionParseError(Exception):
    def __init__(self, path: Path, cause: Exception) -> None: ...
    # .path, .cause

# codehood/push/plan.py  -- pure
@dataclass(frozen=True)
class UpsertQuestion:
    slug: str
    version: str
    question: AnyQuestion
    path: Path

@dataclass(frozen=True)
class DeleteQuestion:
    slug: str

type PushOp = (
    UpsertCourse | UpsertResource | DeleteResource | UpsertQuestion | DeleteQuestion
)

def plan_push(
    discipline: str,
    course: str,
    readme_text: str,
    edition_dates: tuple[str | None, str | None],
    resources: Iterable[ResourceFile],
    server_course_exists: bool,
    server_resources: Mapping[str, str],
    *,
    questions: Iterable[QuestionFile] = (),
    server_questions: Mapping[str, str] = MappingProxyType({}),
) -> Iterator[PushOp]: ...
    # Yields, in order: UpsertCourse, then resource upserts, then resource
    # deletes, then question upserts, then question deletes. A question
    # whose `version` equals `server_questions[slug]` is skipped.

# codehood/push/run.py  -- shell
@dataclass(frozen=True)
class ServerState:
    course_exists: bool
    resources: Mapping[str, str]   # slug -> ref
    questions: Mapping[str, str]   # slug -> version

def fetch_server_state(
    discipline: str, course: str, client: httpx.Client
) -> ServerState: ...
    # Replaces the old `(bool, Mapping)` tuple. A course that does not
    # exist reports no resources and no questions.

def run_plan(...) -> Iterator[OpResult]: ...
    # UpsertQuestion -> generated.upsert_question with
    #   UpsertQuestionRequest(slug=..., status="DRAFT", version=...,
    #                         question=<payload>)
    # DeleteQuestion -> generated.delete_question
    # The payload is
    #   op.question.model_dump(mode="json", by_alias=True, exclude_none=True)
    # minus the keys `weight` and `grading`.
    # An `ordering` question yields a failed OpResult, never a request.
```

`cli/push.py` describes the new ops as `question <slug>` and
`delete question <slug>`.
