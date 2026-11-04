# Local files to Codehood

This document describes how local files are mapped to Codehood entities,
detailing the structure, conventions, and processes involved in synchronizing
local filesystem with server.

`ch init` creates a initial configuration and sets up the following filesystem 
structure:

```
├── .codehood/
├── questions/
│   ├── intro/
│   │   └── q1.md
│   └── multiple-choice.md
├── exams/
│   ├── practice/
│   │   └── part1.md
│   ├── quiz/
│   │   └── week1.md
│   └── exam/
│       ├── midterm.md
│       └── final.md
├── resources/
├── codehood.toml
├── calendar.md
├── roster.csv
└── README.md
```

Bellow is a minimal `codehood.toml` configuration:

```toml
[course]
discipline = "cs101"
instructor = "ada"
edition = "2026-1"

[server]
url = "http://localhost:4321"
```

It specifies where course is located and very basic course information.


## Entity map

### Course

Course payload is shown bellow:

```json
{
    "discipline": "cs101",
    "edition": "2026-2",
    "startAt": "2026-01-05T00:00:00.000Z",
    "endAt": "2026-05-15T00:00:00.000Z",
    "description": "Course description."
}
```

It maps to the following local information:

- `discipline` and `edition` correspond to config fields.
- `description` is the first paragraph of the local README.md (after its H1,
  when it has one),
  or `description` in the `[course]` table of `codehood.toml` when set. Error
  if README.md is missing.
- The README itself, without its H1 and titled by it, is pushed as the `MD`
  resource `readme`, so grading, bibliography and policies reach the server
  too. Its links are rewritten like any `MD` resource's. A README holding
  only the paragraph that describes the course is not pushed. A file under
  `resources/` that also slugs to `readme` is a slug collision.
- `startAt` and `endAt` are read from the calendar.md file. Error if the file is missing.

The course row is pushed with a `rev` that digests its description and dates,
and skipped when the server's `rev` matches, so a push with nothing new
writes nothing.



### Resource

Resource payload is shown below:

```json
{
    "title": "Title",
    "description": "description",
    "slug": "foo",
    "ref": "abc",
    "data": MD | FILE | LINK | CODE
}
``` 

All entries are derived from the contents of the `resources/` directory. Each file
in this folder or subdirectories represents a resource. The mechanism is
shown bellow:

- The slug is extracted from the relative path. A Markdown file
  (`.md`, `.markdown`) drops its extension, so `resources/foo/bar.md` is
  `foo-bar`; any other file keeps it, so `resources/foo/bar.py` and
  `resources/foo/bar.png` are `foo-bar.py` and `foo-bar.png` and live side by
  side.
  Accents are dropped as the server drops them (NFKD, then the combining
  marks removed), so `laços/herança.md` is `lacos-heranca`. Letters NFKD
  does not decompose (`ß`, `æ`, `ø`) are not transliterated.
- Slug collisions are errors and stop the sync process, as everywhere else.
- The data field is derived from the contents of the resource file, by extension:
  - `.md` files are treated as Markdown content (`MD`).
  - `.py, .js, .c, .json, .yaml, .txt, etc.` (any programming language/text format with syntax highlighting) are treated as CODE.
  - Files with an `.url` extension are treated as external links (`LINK`).
  - Other files are treated as FILE.
- `resources/` and any subdirectories can define a `info.yaml` file to provide
  metadata for the resources within that directory. This metadata takes
  precedence over any default way of deriving the resource information.
- `ref` is the md5 hash of the resource's pushable fields (title, description
  and data). Every content hash in Codehood is md5.

#### Resource metadata (`info.yaml`)

`info.yaml` is a mapping from local files to their corresponding metadata (title/description).
It is never a resource itself. Keys are file names in the same directory, and
each entry may only set `title`, `description`, `language` and `mime`, all
strings. Anything else, or an entry for a file that does not exist, is an
error that stops the sync process.

Example `info.yaml`:

```yaml
foo.md:
  title: "Foo Title"
  description: "Description for foo.md"

# It allows overriding the "language" field of CODE data and mime-type of FILE data.
# The existence of those fields overrides the type inference based on the file extension.
foo.pl:
    language: "prolog"
foo.txt:
    mime: "text/plain"
```

`mime` only forces the type to `FILE`: the server derives the type it serves
from the filename, so the value itself is not sent.

#### Inference based on file name/data

**MD**

If the markdown has a frontmatter section, strip it before sending to the server.
If the frontmatter defines `title` or `description`, use them to override the corresponding fields in the resource metadata.

A link or image whose target is another resource points at that resource's
page, `/<discipline>/<course>/resources/<slug>`, once pushed. The target is
read from the file's own folder, as a Markdown viewer reads it
(`![](repl.png)`, `[rubrica](../projeto/rubrica.md)`); a `resources/...`
target that names no file there is read from the course root, as in a
lesson. The address of a `FILE` or `LINK` redirects to its bytes or URL, so
images and `.url` links work. A relative target under `resources/` that names
no resource is an error that stops the sync process.

If a resource fails to upload, the push says which lesson links to it: the
lesson goes out first, and its link is broken until the resource uploads.

**CODE**

`language` is inferred from extension. There is no special mechanism to declare
title or description. CODE content is sent as text, so a file that does not
decode as UTF-8 is an error that stops the sync process: either the extension is
wrong or the file belongs in FILE, and both are the instructor's to fix.

**FILE**

`mimeType` is inferred from extension. There is no special mechanism to declare title or description.

**LINK**

Encoded as a [text/uri-list](https://mamund.com/hypermedia/urilist/). Takes the
first URI listed in the file and sends it as `{"type": "LINK", "url": ...}`.
uri-lists accept comments (lines starting with `#`). The first comment line is
the title. The following comment lines, joined by newlines, are the
description. Strip the leading `#`, then any leading and trailing whitespace,
from both, and drop comment lines left empty. A file with no URI, or whose
first URI is not `http(s)`, is an error that stops the sync process.


**Fallback**

If `title` and `description` were not provided. Convert the file name to title
case and use it as the `title`. It should separate words on hyphens,
underscores, and camel case. The `description` remains blank.


### Calendar

Calendar is a markdown file like bellow:

```md
---
# YAML frontmatter
start: 2026-01-01
end:   2026-06-01
days:
  - Mon 14:00 2h, Lecture
holidays:
  - Oct, 12, Childrens Day
---

# Schedule

## Course overview

What we will cover, how grading works.

* Course presentation
* Instructor contact
* Office hours
```

It sets information in several different entities:

- `start` and `end` define the Course duration (`startAt` and `endAt` fields).
- `days` define the TimeSlot entities (see below).
- `holidays` lists the dates that are considered holidays, as `Month, Day,
  Title`. The year is deliberately absent: it is inferred from the course's
  `start`/`end` range, so an instructor copying a calendar into a new edition
  does not have to rewrite every holiday. A course spanning a new year may match
  a `Month, Day` pair in either year; take the occurrence that falls inside the
  range, and if both do, it is an error the instructor resolves by splitting the
  entry. A holiday matching no date inside the range is a warning and is
  ignored: a date outside `start`/`end` is not this course's concern, so it
  becomes no event, occupies no slot, and takes no part in numbering weeks.
  Holidays are skipped when allocating h2 sections to dates, and each holiday
  that falls on a valid time slot becomes a CalendarEvent of its own with
  `kind=HOLIDAY`, titled after the holiday entry. A holiday that falls on no
  time slot produces nothing.

#### Time slots

Each entry of `days` has the form `- WeekDay HH:MM Duration, Title` and maps to
one TimeSlot:

| Entry part | TimeSlot field | Example                        |
| ---------- | -------------- | ------------------------------ |
| `WeekDay`  | `day`          | `Mon` -> `"MONDAY"`            |
| `HH:MM`    | `start`        | `14:00` -> `{hour: 14, minute: 0}` |
| `Duration` | `duration`     | `2h` -> `{hours: 2, minutes: 0}`   |
| `Title`    | `title`        | `Lecture` -> `"Lecture"`       |

Entries are sorted by ISO weekday, then by start time, so reordering `days` in
the file never changes the resulting entities. The slug is the three-letter
lowercase weekday (`mon`, `tue`, `wed`, ...). If two slots fall on the same
weekday, every colliding slug is suffixed with its start time, `_` replacing the
colon: `mon-14_00`, `mon-18_00`.

#### Calendar events

Each h2 section corresponds to a CalendarEvent. The mapping is done as follows:

- The h2 section title is used as the `title` of the CalendarEvent. The title
  might have an optional `YYYY-MM-DD` date like so: `## Event Title
  (YYYY-MM-DD)`, parenthesis required. If present, this fixes this event on that
  specific date. If date is not legal for the course, (e.g. not within the
  `start` and `end` range, in a holiday or not on a legal time slot), issue
  warning and ignore it.
- Description is taken from the content of the h2 section, excluding the title
  line. Strip any leading and trailing whitespace.
- `ref` is the md5 hash of the string constructed as `${title}#${description}`.
- Events carry no duration of their own: it is derived from their time slot.
- `kind` is `REGULAR` for an event derived from an h2 section, `CANCELLED` when
  the title is struck through (`## ~~Functions~~`, the `~~` left out of the
  title), and `HOLIDAY` for the events derived from the `holidays:` list. A
  cancelled lesson takes its date like any other; the makeup class is an h2 of
  its own, usually with a fixed date.

A push only moves an event forward to `CANCELLED`, never back, the way a
question's status only moves forward: the web cancels too, and a push must
not undo it. Nothing server-side stops a push from overwriting it, so not
overwriting it is the CLI's job: an event the sync preflight reports as
`CANCELLED` is never written and never pruned, and dropping the `~~` does not
restore it. Note the consequence: a cancelled date stays occupied, so the
local allocation and the server's disagree from that date on until the
instructor restores the event on the web or edits `calendar.md`.

How to allocate CalendarEvent instances:

- Create a list of available dates using all time slots available between `start` and `end`.
- Remove any holidays and dates that have explicitly set in the H2 title from the list of available dates.
- Allocate the remaining available dates to the CalendarEvent instances in the
  order they appear in the file.
- If there are fewer events than available dates, issue a warning and leave the
  trailing dates unallocated. If there are more events than available dates,
  issue a warning and truncate the extra events.

An event is rewritten when its `ref` *or* its `kind` differs from what the sync
preflight reported at the same `(week, timeSlot)`. `ref` hashes the title and
the description only, so it cannot see a date that stops being a class and
becomes a holiday, or the reverse: same slot, same title, different `kind`.
Preflight already carries `kind`, so comparing both costs nothing and is the
only way that flip converges.

`(week, timeSlot)` is the event's primary key, both in the payload and in the
URL (`/api/course/{discipline}/{course}/calendar-event/{week}/{timeSlot}`). An
event has no slug of its own. The server computes each event's date from that
pair, so the payload carries no date field, and the CLI sends `week` plus the
slug of the TimeSlot the event landed on; an explicitly dated H2 is resolved
locally to the `(week, timeSlot)` pair covering that date. `week` counts from
zero at the week of the *first event*, not the course's `start`, so a course
whose first class is not in its first time slot needs no special case. Weeks are
ISO weeks: first day starts at MONDAY.

### Exams

Below is an example exam file:

```md
---
course: CS101
author: Fábio Macêdo Mendes
locale: pt-BR
start: 2026-03-15T14:00:00
duration: 2h
---

# [midterm] Midterm Exam

Answer every question. You have two hours.

---
include: recursion-01
---

---
id: factorial
---

Converta este algoritmo iterativo em um recursivo.

[essay]

===

Julgue as afirmações.

* [V] Todo algoritmo iterativo pode ser implementado recursivamente.
* [F] Recursão tende a ser mais eficiente em memória que iteração.
```

We need to map the exam in a JSON payload to be sent to the REST API. 

```md
{
    "slug": "midterm",
    "type": "EXAM",
    "status": "SCHEDULED",
    "title": "Midterm Exam",
    "description": "Midterm exam covering the course material.",
    "preamble": "Answer every question. You have two hours.",
    "duration": { "hours": 2 },
    "tags": ["loops"],
    "questions": [
      { "slug": "recursion-01" },
      { "slug": "midterm-factorial" }
    ]
}
```

The `slug` is derived from the `id` field of the parsed MDQ Exam, not
necessarily from the front matter: MDQ accepts the id in the front matter or
inline in the H1 (`# [midterm] Midterm Exam`), and the front matter takes
precedence. If the parsed exam has no id, the slug is derived from the filename
and its relative path within the `exams/` tree: remove the extension (`.md`,
`.mdq` or `.mdq.md`) and slugify the remaining path. For instance
`exams/part1/exam.md` will have the slug `part1-exam`.

If the filename or any path component starts with a leading underscore `_`, the
`_` is ignored when constructing the slug and the exam is treated as a draft,
uploaded with "status=DRAFT". A leading `_` on a directory makes every exam
under it a draft. An `_` anywhere else in a name has no effect.

Status otherwise follows the schedule: "SCHEDULED" if the exam defines a start
time, "DRAFT" if it does not. When an exam file is deleted in the filesystem, we
mark for soft deletion with "status=ARCHIVED".

A slug collision is always an error that stops the sync process.

Codehood defines 3 types of exams: QUIZ, EXAM and PRACTICE. By default, all
exams are considered to be of the EXAM type by default. If "quiz" or "practice"
appears in the filename or a path component, the exam type is set accordingly.

Users may use this behavior to sort exams by their type in the filesystem:

```
├── exams/
│   ├── practice/
│   │   └── part1.md
│   ├── quiz/
│   │   └── week1.md
│   └── exam/
│       ├── midterm.md
│       └── final.md
```

The structure guarantees that exams are organized by their type. If there is a
conflict, e.g., a file named `./practice/midterm-quiz.md`, the first item
that appears in the filename or path component has precedence. The example
therefore would be classified as "PRACTICE". 

The table summarizes the mapping between the exam's fields from a parsed MDQ
document and the REST API JSON payload:

| Exam Model Field | REST JSON Field | Description                                                    |
| ---------------- | --------------- | -------------------------------------------------------------- |
| `title`          | `title`         | The title of the exam.                                         |
| `description`    | `description`   | A brief description of the exam (optional in the frontmatter). |
| `preamble`       | `preamble`      | The content after title and before questions.                  |
| `duration`       | `duration`      | `{hours, minutes}`.[^exam-duration]                            |
| `start`          | `scheduledAt`   | The start time of the exam.[^exam-start]                       |
| `format`         | `format`        | From MDQ. `MARKDOWN` when the document does not say otherwise. |
| `tags`           | `tags`          | Tags associated with the exam.[^tags]                          |
| `questions`      | `questions`     | The list of questions included in the exam.                    |


[^exam-duration]: MDQ carries the duration as a canonical ISO duration. `hours`
is not limited to a 24 hour range, so the conversion is a plain total: a
two-day take-home is `{hours: 48}`, and nothing is lost. This field is optional
in both, but may be set by the server if the exam starts from a instructor
action. This means that it is not safe to rewrite this field with "null" if it
is not set in the local files.
[^exam-start]: The same observation applies here.
[^tags]: Tags are used to automatically include questions for practice exams. 
This is described in a separate section.

The include questions are referenced by their slugs. Resolution is local: the
tool resolves every reference against the local question files first, and only
then pushes. It is an error if no local question carries that slug. Codehood
accepts a level of fuzzy matching for question slugs. The discovery algorithm
tries the first of those approaches that yields a match.

* exact slug match.
* slug match only for the file name, if it is unique in the question set.
* path match if "id" looks like a relative path and the path exists. Path
  separators are UNIX-style (`/`), but are normalized to the system's format.
  The path is resolved relative to the including exam's own directory under
  `exams/` (so `../questions/recursion/01.md` is legal), then relative to
  `questions/`, and finally from the root directory.

If no match is found, the tool reports an error to the user and stops.


### Questions

The method for association questions with slugs is the same as to the one used
for exams (except that questions use the root `questions/` directory as the
base).

Inline questions are included in the exam as if they were declared in separate
files. The slug is a composition of the question id and the exam's slug:
`<exam-slug>-<question-id>`. If question do not define a id, the tool assigns
`q1`, `q2`, and so on for subsequent questions. The index is relative to the
question position in the exam, not an index that increases only for
non-identified questions.

A typical question file is shown bellow

```md
---
title: Question 1
---

[capitals] What is the capital of France?

- [ ] Berlin
- [*] Paris
- [ ] Madrid
```

It maps to a payload like so:

```json
{
    "slug": "capitals",
    "status": "PUBLISHED",
    "version": "md5-content-hash",
    "question": {} // The MDQ payload, verbatim.
}
```

The table summarizes the mapping between the question file's fields and the REST API JSON payload:

| Question File Field | REST JSON Field | Description                                          |
| ------------------- | --------------- | ---------------------------------------------------- |
| `id`                | `slug`          | The slug of the question[^question-slug].            |
| `*`                 | `question`      | The parsed MDQ content of the question, verbatim.    |
| `version`           | `version`       | MD5 hash of the file content.                        |
| --                  | `status`        | `DRAFT` for a `_`-prefixed file or directory, `PUBLISHED` otherwise[^question-status]. |

The question has no top-level `title` field: in the REST payload the title
lives inside the MDQ `question` object, which is sent whole. In MDQ, the `title`
is optional. If not provided, we use a title cased version of the question's
filename as the title where hyphens and underscores are replaced with spaces.

A question file that `mdq` refuses fails on its own: push reports it, sends
the rest, and exits non-zero. Whatever the server holds under that slug is
kept, not pruned.

[^question-slug]: If not provided, use the slug algorithm described above.

[^question-status]: The web also writes the status, so a push only moves a
    question forward through `DRAFT`, `PUBLISHED` and `HIDDEN`: the status
    sent is the later of the file's and the server's. Dropping the `_`
    publishes a draft. Only the web hides a question (to withdraw one
    published by mistake) or brings it back, and no file undoes either. A
    `_` file whose question the server holds `PUBLISHED` stays published,
    and the push warns. `ARCHIVED` is a deleted question, outside this
    order: it comes back when its file does.


## Sync preflight

Every decision a push makes -- create, update, delete, skip -- is taken against
what the server already holds, and the CLI learns that in a single call to the
`cli.course.preSync` RPC method, keyed by the course's natural key. One call,
before any write.

What that call returns is deliberately thin: identifiers and modification
markers, never entity bodies. Comparing one hash per entity is the whole job,
and shipping titles, descriptions and content bodies to do it wastes a round
trip's worth of bandwidth on data the CLI already has on disk.

- resources, exams, time slots: `slug -> ref`
- questions: `slug -> version`
- calendar events: `(week, timeSlot) -> {ref, kind}`

`kind` is the one field that is not a hash, and it is there for a reason: it is
how the CLI recognises a `CANCELLED` event it must leave alone. Anything else a
future entity needs should follow the same rule -- a marker, not a payload.

## Deletion and pruning

Deleting a local file removes the corresponding server entity. The mechanism
depends on the entity:

- **Questions and resources**: deleted by slug.
- **Exams**: soft-deleted, `status=ARCHIVED`, so past submissions keep their
  referent.
- **Time slots and calendar events**: hard-deleted. An entry removed from
  `calendar.md`'s `days:` or an h2 section removed from the file is gone from
  the server on the next push.

The order these four writes go out in is not free, because the server enforces
two constraints the CLI can see coming. A calendar event references its time
slot, so a slot cannot be deleted while any event still points at it; and two
slots may not overlap on the same weekday, so a slot whose slug changed cannot
be created while the old slug still holds its hour. One order satisfies both:

1. delete calendar events
2. delete time slots
3. upsert time slots
4. upsert calendar events

Getting this wrong does not corrupt anything -- every write is idempotent, so a
second push repairs it -- but it turns a one-push change into a two-push one,
and the mapping's promise is that a push converges in a single pass.

The `CANCELLED` rule interacts with step 2. A cancelled event is never pruned,
so it pins its time slot indefinitely: deleting that slot would orphan an event
the CLI has promised not to touch, and the server refuses it. A slot the
preflight shows carrying a `CANCELLED` event is therefore left in place, with a
warning naming both. The instructor resolves it by restoring or deleting the
event server-side; the CLI does not get to decide that a cancellation is stale.

Pruning is what a push does when the server holds an entity no local file
accounts for. It covers questions, resources, time slots and calendar events.
The one exception is a calendar event the server reports as `kind=CANCELLED`,
which a push neither rewrites nor prunes.
