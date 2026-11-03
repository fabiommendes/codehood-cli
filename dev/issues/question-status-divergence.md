---
type: issue
status: todo
tags: [codehood-cli, push, questions]
relatedTo: [push-questions]
---

# Decide what push does when a question's status diverges

A question's `status` (`DRAFT`/`PUBLISHED`) is written from two places: the
push and the server's web UI, which has a status control in the question bank.
The server accepts both and does not arbitrate (server repository, ADR
`dev/adr/0011-contrato-de-sync-entre-cli-e-servidor.md`). The rule for when
they disagree belongs here.

## Problem

Push always sends `status="DRAFT"` (`codehood/push/run.py:632`), and the
server's update writes it as is (`src/db/services/question.service.ts:607` in
the server repository). So an instructor publishes a question on the web, edits
its file, pushes, and the question silently goes back to `DRAFT`. The spec
(`dev/specs/to-review/push-questions.md`, "Status defaults to `DRAFT`") says a
published question "stays that way unless its content changed", which is the
same behaviour stated as intent.

## To decide

- Does the repository get a vocabulary for status (front matter field,
  directory, `codehood.toml`)? If so, which side wins when the server differs:
  the file, the server, or push stops and asks.
- Without one, push should omit `status` on update, so the server keeps
  whatever the web set, and send `DRAFT` only on create.

## Acceptance

- [ ] A test in `tests/test_push_run.py` for a question `PUBLISHED` on the
      server whose content changed: the chosen rule holds.
