---
type: spec
status: to-do
tags: [push, grades, grade-column, python-hook, instructor]
relatedTo: [course-grade, push, codehood-toml]
---

# `codehood push`: grade columns

The server does not compute a course's final grade. The instructor computes
it on their own machine and push sends the result as grade columns, which
the server shows beside the exams. This spec is the CLI's half. The server's
half is `dev/specs/to-do/course-grade.md` in the server repository, which is
authoritative for the endpoints.

## Scope

In:

- `[[grades.column]]` in `codehood.toml`: the columns the course has.
- `grades.csv`: scores the instructor keeps outside Codehood.
- `grades.py`: the instructor's function, called once per student.
- Grade columns synced in full by `codehood push`: created, updated, deleted.
- `codehood grades`, which prints the computed table and writes nothing.

Out, and why:

- **Releasing a column to students.** That happens on the web, on purpose:
  a push never changes what students see of a column that was hidden.
- **A function over the whole class**, for a curve or a rank. The function
  gets one student. A second entry point can come when a course needs it.
- **Hooks into other tasks.** This is the first place the CLI calls the
  instructor's Python. A general mechanism waits for a second case.
- **Running the function in another interpreter.** See "The function runs
  inside the CLI".

## The files

```
├── codehood.toml
├── grades.csv      # optional
└── grades.py       # optional
```

A course with no `[[grades.column]]` has no grade columns, and push deletes
whatever the server holds. `grades.csv` and `grades.py` are both optional,
but a declared column needs a value from one of them.

### `codehood.toml`

```toml
[[grades.column]]
slug = "assignments"
title = "Assignments"
kind = "number"

[[grades.column]]
slug = "total"
title = "Weighted total"

[[grades.column]]
slug = "final"
title = "Final grade"
kind = "label"
```

- `slug` matches the server's slug rule, `^[a-z0-9][a-z0-9._-]*$`, and is
  unique in the file.
- `title` defaults to the slug.
- `kind` is `number` or `label`, and defaults to `number`.
- The order in the file is the order on the Grades tab.

### `grades.csv`

One row per student. The first column identifies the student and its header
says how: `school_id`, `username`, `github` or `email`. Every other column
is a score, and its header is the key the function reads it by.

```csv
school_id,assignments,final-project
190012345,82.5,90
190054321,,40
```

- The delimiter is `;` when the header line contains one, and `,` otherwise.
- An empty cell is `None`. A cell that reads as a number is a `float`, with
  `,` accepted as the decimal separator. Anything else is a `str`.
- A row whose id matches no enrolled student is reported and skipped. A
  class list has students who never joined the course on Codehood, and
  deleting their rows by hand before every push is a chore.
- An id that appears twice, or an unknown id header, refuses the grades
  part of the push.
- An enrolled student with no row reads `None` for every score.

`codehood init` writes no `grades.csv`. The file exists once the instructor
has scores to keep in it.

### `grades.py`

```python
from codehood.grades import Student

def grade(student: Student) -> dict[str, float | str | None]:
    ...
```

Push imports `grades.py` from the repository root and calls `grade` once per
enrolled student, dropped ones included. The function returns the student's
value for each column it computes, keyed by column slug. `None` means the
student has no value in that column.

```python
@dataclass(frozen=True)
class Student:
    username: str
    name: str
    email: str
    school_id: str | None
    github: str | None
    status: Literal["active", "dropped"]
    exams: Mapping[str, ExamResult]
    scores: Mapping[str, float | str | None]

@dataclass(frozen=True)
class ExamResult:
    score: float | None
    state: Literal["graded", "pending", "in_progress", "missed", "not_held"]
```

- `exams` has one entry per exam of the server's Grades tab, by slug: every
  `EXAM` and `QUIZ` that is neither a draft nor archived. Reading a slug that
  is not there raises `KeyError`, which is how a typo surfaces.
- `score` is a percentage, from -100 to 100, the scale of the web and of the
  CSV download. It is a number only when `state` is `graded`. In every other
  state it is `None`, and `state` says why: answers still waiting for a
  grade, an attempt still open, an exam the student missed, or an exam with
  no attempt that has not closed yet.
- `scores` has one entry per score column of `grades.csv`, `None` where the
  student has no row or the cell is empty.

The reference case of the server's spec, in full:

```python
from codehood.grades import Student

WEIGHTS = {"p1": 0.3, "p2": 0.3, "p3": 0.2}
BANDS = [(90, "SS"), (70, "MS"), (50, "MM"), (30, "MI"), (0.1, "II")]
ORDER = ["SR", "II", "MI", "MM", "MS", "SS"]


def grade(student: Student) -> dict[str, float | str | None]:
    exams = {slug: student.exams[slug].score or 0.0 for slug in WEIGHTS}

    # The substitute exam replaces the lowest score when it beats it.
    substitute = student.exams["sub"].score
    if substitute is not None:
        lowest = min(exams, key=lambda slug: exams[slug])
        exams[lowest] = max(exams[lowest], substitute)

    assignments = student.scores["assignments"] or 0.0
    total = 0.2 * assignments + sum(
        exams[slug] * weight for slug, weight in WEIGHTS.items()
    )

    letter = next((label for floor, label in BANDS if total >= floor), "SR")
    project = student.scores["final-project"] or 0.0
    if project >= 70 and ORDER.index(letter) < ORDER.index("MM"):
        letter = "MM"

    return {"total": round(total, 1), "final": letter}
```

The other substitute policy, replacing an exam the student missed with a
justification, reads `student.exams[slug].state == "missed"` and a
`justified` column of `grades.csv`.

## Design decisions

### A column's value comes from the function, then from the CSV

For each student, a declared column takes the value the function returned
for its slug. A column the function does not return takes the CSV score
with the same header. So an `assignments` column kept in `grades.csv`
reaches the Grades tab with no code, and a course with no `grades.py` at
all can still push columns.

Only declared columns are pushed. A CSV score that is not declared is input
for the function and nothing else.

### Mistakes refuse the grades part, and only it

Each of these refuses every grade operation of the push, with a message that
points at the cause:

- The function raises. The message carries the student's username and the
  traceback.
- The function returns a key that is not a declared column. A typo in a
  slug would otherwise drop a column of grades in silence.
- A declared column is neither returned by the function for any student nor
  a header of `grades.csv`.
- A value does not fit its column: a `number` column takes an `int` or a
  `float` that is finite and not a `bool`, a `label` column takes a `str`
  of 1 to 32 characters.

The rest of the push still runs, and the exit code is 1.

### The function runs inside the CLI

Push loads `grades.py` with `importlib` and calls `grade` in its own
process. The script is the instructor's, runs on their machine and reads
only their own course, so it raises no security question.

The cost: the script can import the standard library and whatever is
installed beside the CLI, and nothing else. An instructor who wants pandas
installs the CLI with `uv tool install --with pandas`. The alternative, a
subprocess under the instructor's own interpreter talking JSON, removes
that limit and adds a protocol to design and keep compatible. Not worth it
for a function that mostly adds and compares a dozen numbers per student.

### Students are matched by the CLI

The server takes usernames. Push reads `GET .../grades`, which lists every
enrolled student with their username, school id, GitHub username and email,
and resolves the id column of `grades.csv` against it. No roster file is
involved, so this does not wait for `codehood roster`.

### `rev` is a hash of the column

`rev` is the sha-256, in hex, of the JSON serialisation of
`{title, kind, position, values}`, with `values` as a list of
`[username, value]` pairs sorted by username and no whitespace between
tokens. Push reads the server's columns, and a column whose `rev` matches
gets no operation. There is no local state, as everywhere else in push.

### Deletion is part of the sync

A column on the server that `codehood.toml` no longer declares is deleted,
with its values. `--no-prune` reports the deletion and does not execute it.

## Architecture

Two new operations join `PushOp`:

```python
UpsertGradeColumn(slug, title, kind, position, rev, values)
DeleteGradeColumn(slug)
```

- `UpsertGradeColumn` is a `PUT` on
  `/api/course/{discipline}/{course}/grade-column`, carrying the whole
  column: the server replaces its values with the ones sent.
- `DeleteGradeColumn` is a `DELETE` on `.../grade-column/{slug}`.

The planner stays pure. It receives the declared columns, the computed
values and the server's columns, and yields operations. Computing the values
is a pure function too: declared columns, the parsed CSV, the students from
the server and the instructor's `grade` in, a table or a list of errors out.
The shell reads the files, fetches `GET .../grades` and
`GET .../grade-column`, and imports `grades.py`.

New module `codehood/grades.py` holds `Student` and `ExamResult`, which is
what the instructor's script imports. The planning code lives in
`codehood/push/grades.py`.

## CLI surface

```
codehood push [PATH] [--dry-run] [--no-prune]
codehood grades [PATH]
```

- `push` plans grade columns after everything else. Each operation prints
  one line, with the number of values it carries.
- `grades` prints the table push would send: one row per student, one
  column per declared grade column. It makes no write. It is how the
  instructor checks the function before pushing, though a pushed column is
  hidden from students anyway until released on the web.

## Proof

- Value computation: declared columns, a CSV and a function in, an expected
  table out. One test per refusal in "Mistakes refuse the grades part".
- CSV parsing: both delimiters, the decimal comma, each id header, a
  duplicate id, an unknown id.
- Planner: a table plus a fake server state in, an expected list of
  operations out. Convergence: plan, apply against a fake, re-plan, assert
  the second plan is empty.
- The reference function above runs in a test against fixture students,
  including the substitute replacement and the raised letter grade.
- End-to-end against the dev server: declare two columns, push, screenshot
  the Grades tab as the instructor, release one on the web, screenshot the
  student's course home, remove a column from `codehood.toml`, push again,
  screenshot it gone.
