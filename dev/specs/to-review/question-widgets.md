# Interactive question widgets

Reusable Textual widgets for answering one MDQ question, plus `codehood show
<file>`, a provisional command that opens a single question file in the
right widget so the library can actually be exercised by hand.
`ROADMAP.md`'s `codehood push` only needs to parse and validate
`questions/`/`exams/`, and there is no student-facing "take an exam in the
terminal" command on the roadmap -- so the widget library itself
(`src/widgets/*` per `AGENTS.md`'s file layout) is built for whatever future
command needs it (an authoring-time preview, or a real exam-taking screen),
and `show` is a manual-testing tool, not that future command.

## Scope

- One `QuestionWidget` subclass per implemented MDQ type: `multiple-choice`,
  `multiple-selection`, `true-false`, `numeric`, `short-answer`, `essay`,
  `fill-in`. (`associative` and `repository question`, mentioned in
  `mdq.spec/README.md`, have no schema or parser support in `mdq` yet, so
  there is nothing to build a widget against.)
- A small typed `Response` per question type
  (`src/codehood_cli/widgets/questions/responses.py`), capturing only what
  the student marked -- never a score or a correctness judgement.
- Five reusable `Control` widgets, shared across question types wherever the
  input shape is the same: single-choice, multi-choice, per-statement
  true/false, numeric text, short text.
- `on_response`: a constructor callback every `QuestionWidget` accepts,
  called with the built `Response` when the student submits. Nothing else
  happens by default -- grading, feedback, and persistence are all the
  caller's job.
- `codehood show <file>` (`cli/show.py`): parses a single-question MDQ file,
  mounts the matching widget as a standalone Textual app via `on_response`
  set to `self.exit`, and prints whatever `Response` comes back. Rejects an
  exam file outright rather than guessing which question to show.

## Design decisions

### `on_response` is a plain callback, not a Textual message

Textual's own convention (see `cli/api.py`'s `Button.Pressed`/
`DataTable.RowSelected` handlers) is a bubbled `Message` a parent `App` or
`Screen` handles via `on_<widget>_<event>`. That pattern earns its keep when
something between the widget and its eventual handler needs to intercept or
re-dispatch the event. Nothing here does: a `QuestionWidget` has exactly one
interested party, given directly at construction time. A constructor
callback is the more literal reading of "callback hook" and is usable
without subclassing `App`.

### The widget never reads a question's answer key

`mdq` itself has no grading logic -- only parsing and validation (see
`mdq/validator.py`, `mdq/parser.py`; there is no `mdq.grade` or equivalent).
So a `QuestionWidget` never touches a choice's `score`/`answer`, a
short-answer's `oneOf`/`regex`, an essay's `answerKey`, or any other
answer-key field, even though the parsed document sitting in
`self.document` carries them. `build_response` reports only what the
student did; grading is entirely the `on_response` callback's business,
whenever a future caller needs it.

### Fill-in blanks render below the stem, not inline

See `docs/adr/0001-fill-in-blanks-render-below-the-stem.md`.

### Numeric responses keep the raw text alongside the parsed value

`NumericResponse` carries both `text` (exactly what the student typed) and
`value` (the parsed `float`, or `None`). `mdq.spec/CONTEXT.md` names this
distinction directly: a *malformed response* ("a response the question
cannot represent... rejected before grading, so never a wrong answer") is
not the same thing as a response that's simply incorrect. Collapsing
unparseable input straight to `0.0` would silently misrepresent a malformed
response as a wrong numeric one. The numeric domain also isn't just
`float`-shaped -- `a/b` fraction text (`domain: fraction`) is parsed
separately by `parse_numeric_text`.

### Composition over an inheritance hierarchy for reuse

The five `Control` widgets (`ChoiceControl`, `MultiChoiceControl`,
`TrueFalseControl`, `NumericControl`, `ShortAnswerControl`) hold all the
type-specific input logic and are what's actually shared: `multiple-choice`
and `fill-in`'s choice blanks both use `ChoiceControl`; `numeric` and
`fill-in`'s numeric blanks both use `NumericControl`; and so on. Each
concrete `QuestionWidget` subclass is a thin `compose_body`/`build_response`
pair over one control. An intermediate abstract class grouping
`multiple-choice`/`multiple-selection`/`true-false` was considered, but the
three don't actually share behavior beyond "render a list of choices" --
that part already lives in each control -- so the extra inheritance layer
would add ceremony without adding reuse.

## Proving it works

- `App.run_test()` + `Pilot` drives each widget: for every type, simulate
  picking/typing an answer and pressing submit, and assert the exact
  `Response` passed to `on_response`.
- **Abstention**: a `true-false` widget submitted with one statement never
  clicked produces a `TrueFalseResponse` missing that statement's key, not a
  `False` entry.
- **Skip**: a `multiple-choice` widget submitted with nothing selected
  produces `MultipleChoiceResponse(choice_id=None)`.
- **Malformed numeric input** (`"abc"`) produces
  `NumericResponse(text="abc", value=None)`, not a parsed `0.0`.
- `parse_numeric_text` round-trips plain floats and `a/b` fractions, and
  returns `None` for anything else.
- **`fill-in`**: submitting a short-answer blank and a numeric blank
  produces a `FillInResponse` whose `blanks` dict holds the right typed
  sub-response per blank id.

## Out of scope

- **Tests for `codehood show` itself.** It's a thin, provisional wrapper
  used to exercise the widgets by hand; the widgets it dispatches to already
  carry the real proof (see "Proving it works"). It's not on `ROADMAP.md`
  and isn't the future command the widget library is actually built for --
  that's a separate spec once a real consumer (a preview tool, an
  exam-taking screen) exists.
- `codehood show` handling an exam file. It refuses one outright rather than
  guessing which question to open first.
- Grading, scoring, or showing correct/incorrect feedback -- see "The widget
  never reads a question's answer key" above.
- `associative` and `repository question` types -- not implemented in `mdq`.
