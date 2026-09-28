---
type: note
status: active
tags: [codehood-cli, mdq, tests, push]
relatedTo: [codehood-cli, push-questions]
---

# CLI tests fail against the current `mdq-py`

24 tests fail, most with `AttributeError: module 'mdq' has no attribute
'parse_question'`. `mdq-py` dropped or renamed `parse_question`, and the push
code and the question widgets still call it.

Affected files: `tests/test_push_question.py`, `tests/test_push_plan.py`,
`tests/test_push_run.py`, `tests/test_cli_push.py`,
`tests/test_widgets_questions.py`.

The `cli` CI job stays red until this is fixed.
