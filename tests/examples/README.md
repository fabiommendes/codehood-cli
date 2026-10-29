---
type: doc
status: active
tags: [codehood-cli, fixtures, testing, dev-server, course-repository]
relatedTo: [codehood-cli, push-questions]
---

# Example course repositories

Course repositories the test suite reuses, and that you can point at the
dev server by hand. Each one maps to a real `(discipline, instructor,
edition)` the dev server already has, so `ch push` works against them
without an admin creating anything first.

| Fixture      | Course                | Login       | Pushes clean? |
| :----------- | :-------------------- | :---------- | :------------ |
| `ada-basic`  | `cs101/ada_2026-1`    | `ada`/`ada` | yes           |
| `ada-full`   | `cs101/ada_2026-2`    | `ada`/`ada` | no, 2 blocked |
| `alan-small` | `cs201/alan_2026-1`   | `alan`/`alan` | yes         |
| `bob`        | --                    | `bob`/`bob` | n/a           |

## One token per server

`~/.codehood/credentials.toml` stores one token per server URL, so `ada`
and `alan` cannot both be logged in to `http://localhost:4321` at once.
Pushing `alan-small` while holding Ada's token fails at the first read:

```
error: could not read the server's current state: Client error '403 Forbidden'
for url 'http://localhost:4321/api/course/cs201/alan_2026-1'
```

Run `ch login` as the right instructor first. A test that touches both
instructors has to swap tokens between them.

## `ada-basic`

What `ch init` writes, plus a second question and two resources. Use it
when you want a repository that is real but has nothing interesting in
it -- the baseline the other fixtures are a delta from.

- `questions/example.md`, `questions/fat.md` -- both multiple-choice.
- `resources/example.md` (`MD`), `resources/example-file.json` (`CODE`).
- The stock `exams/example.md` and `calendar.md` from `init`.

`tests/test_push_integration.py` copies `questions/` from here.

## `ada-full`

A term's worth of content, arranged to hit the edges. Every case below
is deliberate; if you change one, change this list.

**Question types.** All seven the server accepts, one file each:
multiple-choice (`example.md`, `variables/type-of-literal.md`,
`Sorting Basics.md`), multiple-selection (`variables/naming-rules.md`),
true-false (`control-flow/loop-invariant.md`), numeric
(`control-flow/range-length.md`), short-answer
(`functions/default-args.md`), essay (`functions/docstring-purpose.md`,
with an answer key), and fill-in (`recursion/base-case.md`, mixing a
choice blank, a short-answer blank, and a numeric blank).

**Slugs.** `questions/` is four levels of subdirectory deep, and slugs
flatten: `variables/type-of-literal.md` becomes
`variables-type-of-literal`. `Sorting Basics.md` becomes
`sorting-basics`, exercising the case and space rules.

**Extensions.** `functions/fib-implementation.mdq` uses `.mdq` rather
than `.md`; both are question extensions.

**Files that are not questions.** `questions/notes.txt` is flagged
`FileType.WARNING` by `repo.file_tracker.scan_files` and skipped by
`push.question.scan_questions`. It must not become a question and must
not abort the push.

**Blocked on the server.** `resources/handout.pdf` is a `FILE` resource,
whose upload the server does not accept (see `ROADBLOCKS.md`).

So a full `ch push` here reports exactly one failure and exits 1:

```
summary: 17 operation(s) executed, 1 failed, 0 skipped
failures:
  resource handout (FILE): blocked: the server accepts no FILE upload yet (...)
```

That is the point of the fixture: it proves a failure does not stop the
push. A second `ch push --dry-run` replans the course row and that blocked
item, and nothing else.

**Resources.** `MD` with front-matter title and description
(`syllabus.md`), `CODE` in three languages across two subdirectories
(`week1/hello.py`, `week1/greet.js`, `week2/schema.sql`), and the blocked
`FILE`. Note `week1/greet.js` is named so it does *not* collide with
`week1/hello.py`: both `hello.*` would flatten to `week1-hello` and abort
the whole push. Slug collisions belong in unit tests with `tmp_path`, not
in a fixture that has to stay pushable.

**Other.** `README.md` has a second heading after the description, so the
"the README's H1 is ignored and the description stops at the next
heading" rule has something to bite on. `roster.csv` and `calendar.md`
are tracked file types nothing consumes yet.

## `alan-small`

A second instructor, a second discipline, no edge cases: four questions
(multiple-choice, true-false, numeric, multiple-selection), two resources
(`MD` and `CODE`), one published exam. Pushes clean, converges on the
second run.

Use it when a test needs a course that is *not* Ada's -- permissions,
cross-instructor isolation, or just proof the CLI is not hardcoded to one
course.

## `bob`

Empty but for its own README. `bob` is the pre-seeded student enrolled in
Ada's `cs101`; the student workflow has no repository layout yet, so
there is nothing to scaffold. The folder is a placeholder.

## Exams do not parse yet

`exams/` in every fixture holds real MDQ exams, but nothing in the CLI
reads them -- `codehood/` never calls `mdq.parse_exam`. They are there so
the directory layout is realistic and so the exam slice has content to
start from.

They also do not resolve standalone. `mdq.loaders.FileLoader` looks for
`.mdq.md` and `.mdq`, while `ch init` writes questions as plain `.md`, so
an `include:` naming a `.md` question raises `IncludeNotFound`:

```
IncludeNotFound: cannot resolve included question 'example':
looked for .mdq.md/.mdq under .../questions
```

`FileLoader` also does not recurse, so an include naming a question in a
subdirectory would not resolve either. Both need settling as part of the
exam slice; see `BACKLOG.md`.
