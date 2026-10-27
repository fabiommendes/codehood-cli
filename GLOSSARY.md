# Glossary

## Admin

Type: domain
Code: `Role.ADMIN`

The [Role](#role) that sees and manages everything. Admins invite instructors,
and the first one is created outside the app by `manage create-user` or the dev
seed, since nothing exists yet to invite them.

## API key

Type: domain

A long-lived bearer token for non-browser clients, of kind `CLI` or `BOT`. Shown
once at creation and stored only as a SHA-256 hash, revocable individually, and
sent as `Authorization: Bearer <key>`. A request authenticated by one acts as
the key's owner.

## Classroom invite

Type: domain 
Code: `InviteKind.CLASSROOM`

A reusable join code for one course, redeemable by anyone holding the link.
`email` is null, the role is fixed to `STUDENT`, and `maxUses` caps enrollment
or is null for unlimited. Contrast [Personal invite](#personal-invite).

## CLI

Also: `codehood` 
Type: domain

The command-line tool instructors use to author a course locally and push it to
the server. It is the reason course content is a Git repository of plain text
rather than something typed into web forms. Sync is one-way — there is no
`codehood pull`, because the server never modifies content.

## Content hash

Type: domain
Code: `contentHash`

The sha-256 a [Resource](#resource) carries so the [CLI](#cli) can tell what
changed without downloading anything. Supplied by the CLI and opaque to the
server, which never recomputes or interprets it. For a `FILE` it covers the
blob's bytes; for every type it covers the resource's own fields, so a
retitled resource hashes differently even when its body did not move.

## Course

Also: course edition 
Type: domain 
Code: `Course`, `CourseService`

One offering of a [Discipline](#discipline) by one instructor in one
[Edition](#edition). Those three fields are its unique key and also its
[Course URL](#course-url), so it owns everything that varies between runs:
schedule, exams, enrollments, and passphrases.

## Course URL

Type: platform 
Code: `src/utils/course-url.ts`

The address `/<discipline-slug>/<username>_<edition>`, e.g. `/cs101/ada_2026-1`.
It is built from the columns of `Course`'s unique key, so no extra id is stored
and the [CLI](#cli) can construct it offline. There is no `/courses/` prefix,
which is why [Reserved slug](#reserved-slug) exists. Everything about the
course hangs off it: `/exams`, `/resources`, `/schedule`, and, for its
instructor only, `/roster` and `/manage` — one tab strip, on every page,
built by `courseTabs()`.

## Discipline

Also: subject 
Type: domain 
Code: `Discipline`

The stable subject a course teaches, identified by a slug such as `cs101`. A
discipline outlives the [Courses](#course) that instantiate it and owns the
[Remote question](#remote-question) bank shared across them.

## Edition

Type: domain
Code: `Edition`, `EditionService`

An academic term, created by an admin, that separates repeated runs of the same
discipline by the same instructor. Its slug is a four-digit year with an
optional term number (`2026`, `2026-1`) and appears in every course URL, so it
never changes; its window says when new courses may be created for it, and
closing that window leaves existing courses alone.

## Enrollment

Type: domain
Code: `Enrollment`

A student's membership in a [Course](#course), with an `ACTIVE` or `DROPPED`
status; only an active one grants access to course contents. Managed through
`CourseService` methods rather than a service of its own, since it is a join
table with no identity of its own.

## Event

Type: domain 
Code: `Event`

One dated occurrence of a [Time slot](#time-slot) — a single class meeting in a
given week, with its own title and description, or flagged as a holiday. This is
what the calendar renders.

## Grading bot

Also: bot 
Type: domain 
Code: `ApiKeyKind.BOT`

An automated client that grades submissions through the
[REST API](#rest-api) using an [API key](#api-key). A bot currently acts as the
instructor who issued its key and therefore sees everything that instructor
sees; narrowing that is open work.

## Group

Type: domain 
Code: `Group`, `GroupMembership`

A set of users who share ownership of [Remote questions](#remote-question), so a teaching team
can maintain a bank together. Membership carries its own `isAdmin` flag,
independent of the user's global [Role](#role).

## Instructor

Type: domain 
Code: `Role.INSTRUCTOR`

The [Role](#role) that owns courses: authors content locally, pushes it with the
[CLI](#cli), and invites students. An instructor sees only the courses they
teach plus any they are enrolled in — there is no course catalog.

## Invite

Type: domain 
Code: `Invite`, `InviteRedemption`, `InviteService`

The only way an account comes into existence, since there is no public sign-up.
An invite fixes the [Role](#role) it grants and expires; redeeming it at
`/invite/[token]` is what creates the [User](#user). Comes in two kinds:
[Personal](#personal-invite) and [Classroom](#classroom-invite).

## Local exam

Also: MDQ exam 
Type: domain 
Code: `mdq` (package)

The Markdown file in a course repo's `exams/` directory, recognised by its H1
title and validated against the [MDQ](#mdq) spec. `codehood push` turns it into
a [Remote exam](#remote-exam); nothing about it lives in the database until
then. Contrast [Remote exam](#remote-exam).

## Local question

Also: MDQ question 
Type: domain 
Code: `mdq` (package)

The Markdown file in a course repo's `questions/` directory, identified by its
`id` (the filename stem, unless overridden) and validated against the
[MDQ](#mdq) spec. `codehood push` turns it into a
[Remote question](#remote-question); nothing about it lives in the database
until then. Contrast [Remote question](#remote-question).

## Management command

Also: `manage` 
Type: platform 
Code: `src/commands/`

A Commander.js script for operator tasks that have no UI, such as
`manage create-user` and `manage reset-password`. Commands go through the
[Service](#service) layer like everything else, never straight to Prisma.

## Manifest

Type: platform

The list of what the server holds for one [Course](#course) -- identifiers and
[Content hashes](#content-hash), no bodies -- that a [Push](#push) diffs the
repository against (FR-SYNC-002). The server never computes the difference
itself; it answers what it has and executes what the CLI decides.

## MDQ

Type: domain 
Code: `mdq` (`../mdq.spec`, sibling project)

The Markdown-based file format for [Local questions](#local-question) and
[Local exams](#local-exam), parsed and validated by the `mdq` package. Its own
glossary (`mdq.spec/CONTEXT.md`) uses "question" and "exam" unqualified, since
it has no server-side counterpart to disambiguate from; this glossary adds the
"local"/"remote" qualifiers because both senses coexist here.

## Passphrase

Type: domain 
Code: `Passphrase`

A short expiring secret scoped to one [Course](#course), unique across the
system. Reserved for in-class check-in style flows; nothing reads it yet.

## Permission pair

Type: platform 
Code: `src/auth/permissions.ts`

The two encodings every visibility rule needs: a predicate over a loaded row
(`canViewCourse`) for `findOne` and the UI, and a Prisma `where` fragment
(`courseVisibility`) that `findMany` pushes into SQL. They are written adjacent
and pinned together by a test asserting the two agree, because a drifted pair is
invisible.

## Personal invite

Type: domain 
Code: `InviteKind.PERSONAL`

A single-use invite addressed to one email, which the invitee must match
exactly. Used instructor→student and admin→instructor. Contrast
[Classroom invite](#classroom-invite).

## Practice session

Type: domain

A timestamp on a [Response](#response) marking it as self-study rather than part
of a [Remote exam](#remote-exam). Responses carry either an exam or a practice
session, never both.

## Public id

Type: platform 
Code: `publicId`

A random ten-character URL-safe string on rows whose identifier appears in a URL
but should not be guessable. Primary keys stay auto-incrementing integers; the
`publicId` is generated with nanoid in the service layer, not the database.

## Push

Also: `codehood push`, sync
Type: domain

The one-way sync that makes the server's copy of a [Course](#course) match the
local repository. Not atomic and not transactional: an interrupted push leaves
a coherent partial state, and running it again converges (FR-SYNC-005). The
repository is the source of truth, so content the repository no longer has is
deleted from the server rather than kept.

## Push plan

Type: platform
Code: `codehood/push/`

The sequence of operations a [Push](#push) intends to perform, built before
any of them run. It is inert data -- no client, no server ids -- which is what
lets `--dry-run` print it and tests assert on it. The interpreter that
executes it is the only part of the CLI that talks to the server.

## Remote exam

Type: domain 
Code: `Exam`, `ExamType`, `ExamStatus`

A set of [Remote questions](#remote-question) assigned to a course, of type
`PRACTICE`, `QUIZ`, `EXAM`, or `FINAL`. Its status moves `DRAFT` →
`SCHEDULED` → `ONGOING` → `COMPLETED` (or `ARCHIVED`), and only `ONGOING`
accepts submissions. Each question is pinned to a
[Remote question version](#remote-question-version) so the paper does not
change under the students taking it. Contrast [Local exam](#local-exam), the
MDQ file it is pushed from.

## Remote question

Also: question ref 
Type: domain 
Code: `QuestionRef`

The stable identity of a question once pushed to the server: its author,
discipline, type (`MULTIPLE_CHOICE`, `MULTIPLE_SELECTION`, `TRUE_FALSE`,
`ESSAY`), status (`DRAFT`, `PUBLISHED`, `ARCHIVED`), and tags. The text lives
in its [versions](#remote-question-version) instead, so the reference stays
lightweight and editing never rewrites history. Contrast
[Local question](#local-question), the MDQ file it is pushed from.

## Remote question version

Type: domain 
Code: `QuestionData`

One immutable revision of a question's content — title, stem, and a
type-specific JSON payload — identified by a hash. Editing appends a version
and repoints `QuestionRef.latest`; exams and courses may pin an older one.

## Repository

Type: domain
Code: `Repository`, `RepositoryService`

A git repository of a [Course](#course), pushed by the [CLI](#cli) from a
folder under `repositories/` (the folder name is the slug). The server keeps
one commit per push and serves it to `git clone` over HTTP.

## Reserved slug

Type: platform 
Code: `RESERVED_SLUGS`

A top-level name a [Discipline](#discipline) may not take, because
[Course URLs](#course-url) live in the root namespace. Astro prefers static
routes over dynamic ones silently, so a discipline named `login` would not
error — its courses would just become unreachable. Adding a top-level route
means adding its name to this list in the same commit.

## Resource

Type: domain
Code: `Resource`, `ResourceType`, `ResourceService`

One of the four things a [Course](#course) hands its students — a `FILE` to
download, a `LINK` to follow, an `MD` note, or a `CODE` snippet — grouped by
type on `/resources` in a fixed, unauthored order. Pushed by the [CLI](#cli)
only, never authored in the web app; visible to everyone who may see the
course's contents, with no separate "unpublished" state. A `FILE` resource
points at a [File](#resource-file) it does not own — the same bytes may back
resources in more than one course.

## Resource file

Also: File, blob
Type: domain
Code: `File`, `FileService`

The bytes behind a `FILE` [Resource](#resource), addressed by `slugHash` — a
sha-256 of its own content, which doubles as the URL token
(`/files/<slugHash>/<name>`) and the on-disk storage path. Content-addressed,
so two courses pushing the same bytes share one row; removing a resource
removes the file only once nothing else points at it, at which point it
becomes a [Resource tombstone](#resource-tombstone). Served with no
authentication check, on the understanding that nothing whose disclosure
matters ever becomes a resource (FR-NFR-032).

## Resource slug

Type: domain
Code: `Resource.slug`

A [Resource](#resource)'s natural key: its path under the repository's
`resources/` directory, extension dropped and the whole thing flattened to one
segment, so `resources/week1/slides.pdf` is `week1-slides`. Derived from the
path rather than assigned by the server (FR-SYNC-010), which is why renaming a
file is a delete plus a create and never an update (FR-SYNC-011). Two files
that flatten to the same slug are an error, not a merge.

## Resource tombstone

Type: domain
Code: `File.deletedAt`

What a [Resource file](#resource-file)'s row becomes once its bytes are
removed from disk and nothing else points at it: the row and its `slugHash`
survive with `deletedAt` stamped, so the blob route can answer `410 Gone` and
explain what happened instead of a bare `404`.

## Response

Type: domain 
Code: `Response`

One student's answer slot for one question, in a [Remote exam](#remote-exam) or a
[Practice session](#practice-session). It holds no answer itself: it collects
[Submissions](#submission) and decides, via `acceptingSubmissions`, whether more
may arrive.

## REST API

Type: platform 
Code: `src/pages/api/` (routes), `src/api/` (controllers)

The HTTP surface the [CLI](#cli) and [Grading bots](#grading-bot) use,
authenticated by [API key](#api-key) rather than session cookie. Like
[Actions](#action), its handlers are thin wrappers over
[Services](#service).

## Role

Type: domain 
Code: `Role`

The account-wide permission level — [Admin](#admin), [Instructor](#instructor),
or [Student](#student) — fixed by the [Invite](#invite) that created the
account. Per-course authority is decided by ownership and
[Enrollment](#enrollment), not by role alone.

## Service

Also: service class, db service 
Type: platform 
Code: `src/db/`

The class wrapping Prisma for one model, exposing `create`, `findOne`,
`findMany`, `update`, and `delete`, and holding every business rule and access
check for it. Services do not leak Prisma types upward, and every other layer —
[Actions](#action), [REST API](#rest-api), [Management commands](#management-command) —
is a thin wrapper over them. A method that returns different results to
different people takes an [Actor](#actor) and applies the rule itself.

## Session

Type: domain 
Code: `Session`, `SessionService`

A browser login, represented by a 256-bit opaque token in an httpOnly cookie and
stored only as a SHA-256 hash. Not a JWT, so it can be revoked by deleting the
row. Expiry slides over 30 days, refreshed once past halfway to avoid writing on
every request.

## Spec

Type: process 
Code: `dev/specs/`

The document a feature is designed in before it is built, stating requirements
and naming the design decisions taken. Non-implemented specs live in
`dev/specs/to-do/`. It moves to `dev/specs/to-review/` when the work lands.
Longer-lived conventions live in `docs/design/` instead, and bugs go to
`dev/issues/`.

## Student

Type: domain 
Code: `Role.STUDENT`

The [Role](#role) that consumes a course through the web app: sees courses they
have an active [Enrollment](#enrollment) in, answers questions, and cannot list
classmates. The [CLI](#cli) works for students too, but is never required.

## Submission

Type: domain 
Code: `Submission`

One attempt at a [Response](#response), carrying the answer payload plus grade,
feedback, and status (`PENDING_GRADE`, `WILL_NOT_GRADE`, `GRADED_AUTOMATICALLY`,
`GRADED_MANUALLY`). Attempts accumulate rather than overwrite, so a response
keeps its full history.


## Git

Type: platform

Most common version control system. The codehood CLI must be compatible with
git workflow, but it does not require it or interact with it in any meaningful 
way. The user may manage version control on their own.