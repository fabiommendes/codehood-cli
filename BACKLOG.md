# Backlog

Those are issues and vague future plans for the project. Items in the
backlog are not necessarily prioritized or scheduled for implementation. Pick
the items in the BACKLOG and move them to the ROADMAP once a milestone is set
and a rough schedule is agreed upon for a set of backlog items.

Backlog items are categorized in sections, not on priority.

## Small issues

* **The generated client sends explicit nulls.** `api/generate.py` emits
  `model_dump(by_alias=True)` with no `exclude_none`, so every optional
  field a caller left unset goes on the wire as `null`. The server's zod
  schemas reject that (`expected string, received null`), which is why
  `push/run.py` builds `UpsertQuestionRequest` with `model_construct` and
  a suppressed pydantic warning rather than the plain constructor. Fixing
  it in the generator needs a way to distinguish "not provided" from
  "explicitly null" -- `UpsertCourse` really does mean to send a null
  `startAt` -- so it is not a one-line `exclude_none=True`.

* **`ShapeRegistry` never walks inside a `$ref`, so a component's own
  nested shapes go unnamed.** `_collect` stops at a `$ref`, so the inline
  objects inside a component schema are registered only because some path
  happens to inline an identical copy of them. Remove the copy and
  generation dies: `ENDPOINTS = {"createExam", "readExam"}` today raises
  `KeyError` on `ExamCreate.questions`'s item shape, because only the
  `$ref`ed body reaches it. This is pre-existing -- the `$ref` early return
  and the unguarded `self._names[...]` lookup both predate the naming work
  -- and the announced spec refresh will detonate it: once `upsertX` `$ref`s
  `XCreate` instead of inlining a body, nothing inline reaches
  `ExamCreate.questions[]`, `ResourceCreate.data`, or `TimeSlotCreate.start`
  again. Fix is to walk `$ref`ed component schemas as collection roots,
  which also changes some names, so it wants its own slice and its own
  verification.

* **A projection is only recognised when the server names the property
  after the component.** `{slug, day, start, duration}` under a property
  called `timeSlot` becomes `TimeSlotAtCalendarEvent`; the same shape under
  a property called anything else keeps its property name. Subset-plus-
  equal-shapes alone is far too loose to name by -- a bare `{id}` is a
  strict subset of eight components -- so the property name is what makes a
  match unambiguous. A projection reached through an *array* is also missed,
  because an array item's candidate is `{Property}Item`, not `{Property}`.
  Neither case exists in today's spec; revisit if one appears.

* **`api.generate` ignores the repo's own spec copy.** With no argument it
  tries `./openapi.json`, then falls back to the live dev server, and never
  looks at `resources/openapi/codehood.json` -- the copy `AGENTS.md` names
  as the one that should be in sync. The default should be the repo copy, so
  a regeneration is reproducible with the server down.

* **`api.generate` does not format what it writes.** The generator emits
  single-quoted, tightly spaced source; the committed `generated.py` is the
  `ruff format` of that. Regenerating without remembering the second step
  produces a 1000-line cosmetic diff. Either format in the generator or make
  it a documented two-step.


## Features

* **`resources/` refs are sha-256, the mapping says md5.**
  `docs/design/mapping-local-filesystem.md` states that every content hash in
  Codehood is md5; `push/resource.content_ref` predates that line and uses
  sha-256, while `push.calendar` follows the mapping. A `ref` is free-form
  server-side, so nothing is broken and neither recipe is wrong -- but two
  recipes for one job is one too many. Switching `content_ref` to md5
  invalidates every stored resource ref, which costs one extra full push and
  nothing else. `REF_PREFIX` exists precisely so that change is loud.

* **`ch init` writes a provisional `calendar.md`.** `repo/_layout.render_calendar`
  was written before the calendar mapping settled and says so in its docstring.
  It needs a pass against `docs/design/mapping-local-filesystem.md`, "Calendar":
  a real `holidays:` entry in `Month, Day, Title` form, and enough h2 sections
  that a scaffolded repository's first `codehood push` does not immediately warn
  about unallocated dates.

* **Two API tests depend on the machine's real credentials file.**
  `tests/test_api_generated.py::test_list_resource_with_no_filters_sends_no_query_string`
  and `..._sends_the_filters_it_was_given` fail after a `ch logout`, because they
  read `~/.codehood/credentials.toml` instead of a fixture. Found the hard way
  during a live end-to-end push: logging out to clean up broke two tests that
  have nothing to do with authentication. They should build their own client
  against a temp credentials path, so the suite does not depend on whether the
  developer happens to be logged in.

## Maintainability

* **Permanent:** go through the FIXME/TODO items. If it is an easy fix, fix it.
  Otherwise, remove the comment and save it in the corresponding section in the
  backlog.
* **Permanent:** review all code comments and ensure they are up-to-date and
  relevant. Refactors can make comment drift, so we need to keep them in sync
  with the code. If a comment is no longer relevant, remove it. 
* **Permanent:** fix any typos and grammatical errors throughout the codebase,
  including comments, documentation, and variable and function names. Make
  sure not breaking any call site when editing the later two.