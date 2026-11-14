"""
Tests for the attachments of questions and exams: a file linked from an
`## [attachments]` section is read from disk, hashed, versioned with the
document, and uploaded with the `PUT` that needs it. See
`dev/specs/to-do/anexos-de-questoes-e-provas.md`, R21 to R25.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.cli.base import app
from codehood.push.errors import QuestionSourceError
from codehood.push.exam import ExamFile, exam_payload, scan_exams
from codehood.push.question import (
    QuestionFile,
    question_version,
    scan_questions,
)
from codehood.push.wire import canonical_question

push_module = importlib.import_module("codehood.cli.push")

#: The server's upload limit for one file (R24).
MAX_UPLOAD_BYTES = 16 * 1024 * 1024

DISCIPLINE = "cs101"
COURSE = "ada_2026-1"
BASE = f"/api/course/{DISCIPLINE}/{COURSE}"

TESTS_ELM = """module Tests exposing (suite)

suite = test "adds" (\\_ -> 1 + 1 |> Expect.equal 2)
"""

#: A `code` question whose tests are linked and that has no linked attachment.
CODE_NO_ATTACHMENT = """---
id: soma
---

Write `add`.

[code]

## [tests]

[testes](Tests.elm)

## [attachments]

```csv inline.csv
a,b
```
"""

#: The same question with two linked attachments, `b.csv` before `a.csv`.
CODE_TWO_ATTACHMENTS = """---
id: soma
---

Write `add`.

[code]

## [tests]

[testes](Tests.elm)

## [attachments]

[b](b.csv)

[a](a.csv)
"""

CHOICE = """---
id: {id}
---

What is 2 + 2?

- [ ] 3
- [*] 4

## [attachments]

[data]({origin})
"""

PLAIN_CHOICE = """---
id: pick
---

What is 2 + 2?

- [ ] 3
- [*] 4
"""

#: Exams with no attachment. The `rev` and the version of the inline question
#: are what the code produced before attachments existed.
EXAM_PLAIN = """# [plain] Plain

Read carefully.

---
id: soma
---

Write `add`.

[code]

## [tests]

```elm
suite = 1
```
"""
EXAM_PLAIN_REV = "v1:76d6b831a79792694dfa128edbd6faf55edb966aa8d1d0f4408d3b09f07b32ed"
EXAM_PLAIN_INLINE_VERSION = "md5:be2abb82728b7c9c2a310c0c4067345a"

EXAM_EMPTY = """# [empty] Empty

Read.

---
id: pick
---

What is 2 + 2?

- [ ] 3
- [*] 4
"""
EXAM_EMPTY_REV = "v1:f6e3faf61ac00323c28adf2e54895a6c24e337cf38ddc5d7c1c94f998da70e1d"
EXAM_EMPTY_INLINE_VERSION = "md5:ca68f978b340e1d85038024c7b6fd125"

#: An exam with one attachment of its own and one inline question that links
#: `d.csv` too.
EXAM_WITH_LINKS = """# [mid] Midterm

Read carefully.

## [attachments]

[exam data](e.csv)

---
id: linked
---

What is 2 + 2?

- [ ] 3
- [*] 4

## [attachments]

[data](d.csv)

---
id: free
---

What is 3 + 3?

- [ ] 5
- [*] 6
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(root: Path, relative: str, text: str | bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


def scan_one(root: Path) -> QuestionFile:
    (found,) = list(scan_questions(root))
    assert isinstance(found, QuestionFile), found
    return found


def exams_of(root: Path) -> dict[str, ExamFile]:
    questions = list(scan_questions(root))
    found = {e.slug: e for e in scan_exams(root, questions)}
    assert all(isinstance(e, ExamFile) for e in found.values()), found
    return found  # type: ignore[return-value]


def canonical_version(question) -> str:
    """The version an inline question has when it has no linked attachment."""
    canonical = json.dumps(
        canonical_question(question),
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    return question_version(canonical.encode("utf-8"))


#
# R21: questions in a file
#
def test_a_question_with_only_fenced_attachments_keeps_the_digest_of_its_file(tmp_path):
    path = write(
        tmp_path,
        "questions/pick.md",
        PLAIN_CHOICE + "\n## [attachments]\n\n```csv inline.csv\na,b\n```\n",
    )

    found = scan_one(tmp_path)

    assert found.version == question_version(path.read_bytes())


def test_a_code_question_with_linked_tests_and_no_attachment_link_keeps_its_recipe(
    tmp_path,
):
    path = write(tmp_path, "questions/soma.md", CODE_NO_ATTACHMENT)
    write(tmp_path, "questions/Tests.elm", TESTS_ELM)

    found = scan_one(tmp_path)

    expected = question_version(path.read_bytes() + b"\0" + TESTS_ELM.encode())
    assert found.version == expected


def test_linked_attachments_follow_the_tests_in_the_order_of_the_document(tmp_path):
    path = write(tmp_path, "questions/soma.md", CODE_TWO_ATTACHMENTS)
    write(tmp_path, "questions/Tests.elm", TESTS_ELM)
    write(tmp_path, "questions/a.csv", b"a-bytes")
    write(tmp_path, "questions/b.csv", b"b-bytes")

    found = scan_one(tmp_path)

    expected = question_version(
        path.read_bytes()
        + b"\0"
        + TESTS_ELM.encode()
        + b"\0"
        + b"b-bytes"
        + b"\0"
        + b"a-bytes"
    )
    assert found.version == expected


def test_editing_only_a_linked_attachment_changes_the_version_and_the_hash(tmp_path):
    write(tmp_path, "questions/pick.md", CHOICE.format(id="pick", origin="data.csv"))
    csv = write(tmp_path, "questions/data.csv", b"x,y\n1,2\n")
    before = scan_one(tmp_path)

    csv.write_bytes(b"x,y\n1,3\n")
    after = scan_one(tmp_path)

    assert before.files == {"data.csv": sha256(b"x,y\n1,2\n")}
    assert after.files == {"data.csv": sha256(b"x,y\n1,3\n")}
    assert before.version != after.version


def test_the_link_is_relative_to_the_question_file_in_a_subdirectory(tmp_path):
    write(tmp_path, "questions/sub/pick.md", CHOICE.format(id="pick", origin="d.csv"))
    write(tmp_path, "questions/sub/d.csv", b"nested")
    write(tmp_path, "questions/d.csv", b"decoy")

    found = scan_one(tmp_path)

    assert found.files == {"d.csv": sha256(b"nested")}


def test_a_question_without_a_link_has_no_files(tmp_path):
    write(tmp_path, "questions/pick.md", PLAIN_CHOICE)

    assert scan_one(tmp_path).files == {}


def test_a_missing_attachment_file_is_an_error_naming_the_link(tmp_path):
    write(tmp_path, "questions/pick.md", CHOICE.format(id="pick", origin="nope.csv"))

    with pytest.raises(QuestionSourceError) as raised:
        list(scan_questions(tmp_path))

    assert raised.value.origin == "nope.csv"
    assert raised.value.path == tmp_path / "questions" / "nope.csv"


def test_an_attachment_of_exactly_the_limit_is_read(tmp_path):
    write(tmp_path, "questions/pick.md", CHOICE.format(id="pick", origin="big.csv"))
    big = write(tmp_path, "questions/big.csv", b"\0" * MAX_UPLOAD_BYTES)

    assert scan_one(tmp_path).files == {"big.csv": sha256(big.read_bytes())}


#
# R22: questions inline in an exam
#
def test_an_inline_question_without_a_link_keeps_its_version(tmp_path):
    write(tmp_path, "exams/empty.md", EXAM_EMPTY)
    write(tmp_path, "exams/plain.md", EXAM_PLAIN)

    found = exams_of(tmp_path)

    (empty,) = found["empty"].inline
    (plain,) = found["plain"].inline
    assert empty.version == EXAM_EMPTY_INLINE_VERSION
    assert plain.version == EXAM_PLAIN_INLINE_VERSION


def test_an_inline_question_with_a_link_adds_files_to_its_canonical_json(tmp_path):
    write(tmp_path, "exams/sub/mid.md", EXAM_WITH_LINKS)
    write(tmp_path, "exams/sub/d.csv", b"inline-bytes")
    write(tmp_path, "exams/sub/e.csv", b"exam-bytes")
    write(tmp_path, "exams/d.csv", b"decoy")

    exam = exams_of(tmp_path)["mid"]

    linked, free = exam.inline
    files = {"d.csv": sha256(b"inline-bytes")}
    assert linked.files == files
    expected = json.dumps(
        {**canonical_question(linked.question), "files": files},
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    assert linked.version == question_version(expected.encode("utf-8"))
    assert free.files == {}
    assert free.version == canonical_version(free.question)


def test_editing_a_linked_file_changes_only_the_version_of_its_inline_question(
    tmp_path,
):
    write(tmp_path, "exams/mid.md", EXAM_WITH_LINKS)
    write(tmp_path, "exams/e.csv", b"exam-bytes")
    csv = write(tmp_path, "exams/d.csv", b"one")
    before = exams_of(tmp_path)["mid"]

    csv.write_bytes(b"two")
    after = exams_of(tmp_path)["mid"]

    assert before.inline[0].version != after.inline[0].version
    assert before.inline[1].version == after.inline[1].version


def test_an_inline_question_with_a_missing_link_is_an_error(tmp_path):
    write(tmp_path, "exams/mid.md", EXAM_WITH_LINKS)
    write(tmp_path, "exams/e.csv", b"exam-bytes")

    with pytest.raises(QuestionSourceError) as raised:
        exams_of(tmp_path)

    assert raised.value.origin == "d.csv"


def test_an_included_question_resolves_its_links_against_its_own_file(tmp_path):
    write(tmp_path, "questions/x/q.md", CHOICE.format(id="q", origin="d.csv"))
    write(tmp_path, "questions/x/d.csv", b"from-the-question")
    write(tmp_path, "exams/d.csv", b"beside-the-exam")
    write(tmp_path, "exams/mid.md", "# [mid] Mid\n\n---\ninclude: q\n---\n")

    questions = list(scan_questions(tmp_path))
    (question,) = questions
    assert isinstance(question, QuestionFile)
    exam = exams_of(tmp_path)["mid"]

    assert question.files == {"d.csv": sha256(b"from-the-question")}
    assert exam.questions == ("q",)
    assert exam.inline == ()
    assert exam.files == {}


#
# R23: the exam
#
def test_an_exam_without_attachments_sends_empty_fields_and_keeps_its_rev(tmp_path):
    write(tmp_path, "exams/empty.md", EXAM_EMPTY)
    write(tmp_path, "exams/plain.md", EXAM_PLAIN)

    found = exams_of(tmp_path)

    for slug, rev in (("empty", EXAM_EMPTY_REV), ("plain", EXAM_PLAIN_REV)):
        payload = exam_payload(found[slug])
        assert payload["attachments"] == []
        assert payload["files"] == {}
        assert found[slug].rev == rev


def test_an_exam_with_attachments_sends_them_and_hashes_them_into_the_rev(tmp_path):
    write(tmp_path, "exams/mid.md", EXAM_WITH_LINKS)
    write(tmp_path, "exams/d.csv", b"inline-bytes")
    csv = write(tmp_path, "exams/e.csv", b"one")
    before = exams_of(tmp_path)["mid"]

    csv.write_bytes(b"two")
    after = exams_of(tmp_path)["mid"]

    payload = exam_payload(before)
    attachments = payload["attachments"]
    assert isinstance(attachments, list)
    assert [(a["name"], a["origin"]) for a in attachments] == [("e.csv", "e.csv")]  # type: ignore[index]
    assert payload["files"] == {"e.csv": sha256(b"one")}
    assert exam_payload(after)["files"] == {"e.csv": sha256(b"two")}
    assert before.rev != after.rev
    assert before.rev != EXAM_EMPTY_REV


def test_the_exam_attachments_are_not_reported_as_ignored(tmp_path):
    write(tmp_path, "exams/mid.md", EXAM_WITH_LINKS)
    write(tmp_path, "exams/d.csv", b"inline-bytes")
    write(tmp_path, "exams/e.csv", b"exam-bytes")

    assert exams_of(tmp_path)["mid"].ignored == ()


def test_a_fenced_exam_attachment_needs_no_file_and_no_files_entry(tmp_path):
    write(
        tmp_path,
        "exams/mid.md",
        "# [mid] Mid\n\nRead.\n\n## [attachments]\n\n```csv n.csv\na,b\n```\n",
    )

    payload = exam_payload(exams_of(tmp_path)["mid"])

    assert [a["name"] for a in payload["attachments"]] == ["n.csv"]  # type: ignore[index, union-attr]
    assert payload["files"] == {}


def test_an_exam_with_a_missing_attachment_file_is_an_error(tmp_path):
    write(
        tmp_path,
        "exams/mid.md",
        "# [mid] Mid\n\nRead.\n\n## [attachments]\n\n[x](nope.csv)\n",
    )

    with pytest.raises(QuestionSourceError) as raised:
        exams_of(tmp_path)

    assert raised.value.origin == "nope.csv"


#
# `ch push`
#
@dataclass
class Call:
    method: str
    path: str
    content_type: str
    body: dict | None
    parts: dict[str, bytes] | None


def parts_of(request: httpx.Request) -> dict[str, bytes]:
    boundary = request.headers["content-type"].split("boundary=")[1].encode()
    parts: dict[str, bytes] = {}
    for chunk in request.content.split(b"--" + boundary)[1:-1]:
        chunk = chunk.removeprefix(b"\r\n").removesuffix(b"\r\n")
        head, _, body = chunk.partition(b"\r\n\r\n")
        parts[head.split(b'name="')[1].split(b'"')[0].decode()] = body
    return parts


class FakeServer:
    """
    A server with no course yet. `missing` is the set of hashes it lacks,
    `None` meaning every hash it is asked about; `too_large` the slugs of
    the questions it refuses with a 413.
    """

    def __init__(
        self,
        missing: Collection[str] | None = None,
        too_large: Collection[str] = (),
    ) -> None:
        self.missing = missing
        self.too_large = set(too_large)
        self.calls: list[Call] = []

    def client(self, base_url=None) -> httpx.Client:
        return httpx.Client(
            base_url=base_url or "http://localhost:4321",
            transport=httpx.MockTransport(self.handle),
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        content_type = request.headers.get("content-type", "")
        body: dict | None = None
        parts: dict[str, bytes] | None = None
        if content_type.startswith("multipart/form-data"):
            parts = parts_of(request)
            body = json.loads(parts["json"])
        elif request.content:
            body = json.loads(request.content)
        self.calls.append(Call(method, path, content_type, body, parts))

        if path == "/api/blob/missing":
            assert body is not None
            hashes = body["hashes"]
            lacking = (
                hashes
                if self.missing is None
                else [h for h in hashes if h in self.missing]
            )
            return httpx.Response(200, json={"missing": lacking})
        if method == "GET" and path == BASE:
            return httpx.Response(404, json={"message": "not found"})
        if method == "GET":
            return httpx.Response(200, json=[])
        assert body is not None, (method, path)
        if path == "/api/course" or path.endswith(f"/{COURSE}") and method == "PUT":
            return httpx.Response(200, json=course_json())
        if path == f"{BASE}/question":
            if body["slug"] in self.too_large:
                return httpx.Response(413, json={"message": "payload too large"})
            return httpx.Response(200, json=stored_question(body))
        if path == f"{BASE}/exam":
            return httpx.Response(200, json=stored_exam(body))
        return httpx.Response(200, json=course_json())

    def puts(self, kind: str) -> list[Call]:
        return [
            c for c in self.calls if c.method == "PUT" and c.path == f"{BASE}/{kind}"
        ]

    def missing_calls(self) -> list[Call]:
        return [c for c in self.calls if c.path == "/api/blob/missing"]

    def index(self, call: Call) -> int:
        return next(i for i, c in enumerate(self.calls) if c is call)


def course_json() -> dict:
    return {
        "description": "A course.",
        "discipline": {"slug": DISCIPLINE, "name": "Intro to CS"},
        "edition": {
            "slug": "2026-1",
            "name": "2026-1",
            "startAt": "2026-01-01T00:00:00Z",
            "endAt": "2026-06-01T00:00:00Z",
            "createdAt": "2026-01-01T00:00:00Z",
        },
        "instructor": {"name": "Ada Lovelace", "username": "ada"},
        "enrollmentCount": 0,
        "rev": None,
        "startAt": "2026-01-01T00:00:00Z",
        "endAt": "2026-06-01T00:00:00Z",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "joinedAt": "2026-01-01T00:00:00Z",
    }


def stored_question(body: dict) -> dict:
    return {
        "slug": body["slug"],
        "id": 1,
        "status": body.get("status", "PUBLISHED"),
        "version": body.get("version"),
        "rev": body.get("rev"),
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "question": body["question"],
    }


def stored_exam(body: dict) -> dict:
    return {
        "slug": body["slug"],
        "type": "EXAM",
        "status": body.get("status", "DRAFT"),
        "title": body["title"],
        "description": None,
        "preamble": body.get("preamble"),
        "format": "MARKDOWN",
        "scheduledAt": None,
        "duration": None,
        "extraTime": None,
        "allowCodeRun": None,
        "answerHistory": None,
        "gradesReleasedAt": None,
        "author": "ada",
        "rev": body.get("rev"),
        "tags": [],
        "questions": body["questions"],
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def token(monkeypatch, tmp_path_factory):
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)
    base_module.save_token("http://localhost:4321", "test-token")


def course(root: Path) -> Path:
    write(
        root,
        "codehood.toml",
        '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
        '\n[server]\nurl = "http://localhost:4321"\n',
    )
    write(root, "README.md", "# CS101\n\nA description.\n")
    write(
        root,
        "calendar.md",
        "---\nstart: 2026-01-01\nend: 2026-06-01\ndays: []\nholidays: []\n---\n\n"
        "# Schedule\n\n## Overview\n\nText.\n",
    )
    return root


def push(monkeypatch, server: FakeServer, root: Path, *args: str):
    monkeypatch.setattr(push_module, "get_client", server.client)
    return CliRunner().invoke(app, ["push", str(root), *args])


def flat(output: str) -> str:
    return " ".join(output.split())


def test_a_dry_run_does_not_report_linked_attachments_as_not_pushed(
    tmp_path, monkeypatch
):
    root = course(tmp_path)
    write(root, "questions/pick.md", CHOICE.format(id="pick", origin="data.csv"))
    write(root, "questions/data.csv", b"x,y\n")
    write(root, "exams/mid.md", EXAM_WITH_LINKS)
    write(root, "exams/d.csv", b"inline-bytes")
    write(root, "exams/e.csv", b"exam-bytes")

    result = push(monkeypatch, FakeServer(), root, "--dry-run")

    assert result.exit_code == 0, result.output
    assert "pick" in result.output
    assert "not pushed" not in result.output
    assert ".csv" not in result.output


def test_push_with_a_missing_attachment_fails_before_any_request(tmp_path, monkeypatch):
    root = course(tmp_path)
    write(root, "questions/pick.md", CHOICE.format(id="pick", origin="nope.csv"))
    server = FakeServer()

    result = push(monkeypatch, server, root)

    assert result.exit_code == 1
    assert "nope.csv" in flat(result.output)
    assert server.calls == []


def test_push_with_a_question_attachment_over_the_limit_fails_before_any_request(
    tmp_path, monkeypatch
):
    root = course(tmp_path)
    write(root, "questions/pick.md", CHOICE.format(id="pick", origin="big.csv"))
    write(root, "questions/big.csv", b"\0" * (MAX_UPLOAD_BYTES + 1))
    server = FakeServer()

    result = push(monkeypatch, server, root)

    assert result.exit_code == 1
    text = flat(result.output)
    assert "big.csv" in text
    assert re.search(r"16\s?MiB", text)
    assert server.calls == []


def test_push_with_an_exam_attachment_over_the_limit_fails_before_any_request(
    tmp_path, monkeypatch
):
    root = course(tmp_path)
    write(root, "questions/pick.md", CHOICE.format(id="pick", origin="small.csv"))
    write(root, "questions/small.csv", b"ok")
    write(
        root,
        "exams/mid.md",
        "# [mid] Mid\n\nRead.\n\n## [attachments]\n\n[x](big.csv)\n",
    )
    write(root, "exams/big.csv", b"\0" * (MAX_UPLOAD_BYTES + 1))
    server = FakeServer()

    result = push(monkeypatch, server, root)

    assert result.exit_code == 1
    text = flat(result.output)
    assert "big.csv" in text
    assert re.search(r"16\s?MiB", text)
    assert server.calls == []


def test_push_accepts_an_attachment_of_exactly_the_limit(tmp_path, monkeypatch):
    root = course(tmp_path)
    write(root, "questions/pick.md", CHOICE.format(id="pick", origin="big.csv"))
    data = b"\0" * MAX_UPLOAD_BYTES
    write(root, "questions/big.csv", data)
    server = FakeServer(missing=[])

    result = push(monkeypatch, server, root)

    assert result.exit_code == 0, result.output
    (put,) = server.puts("question")
    assert put.body is not None and put.body["files"] == {"big.csv": sha256(data)}


@pytest.fixture
def full_course(tmp_path) -> tuple[Path, dict[str, str]]:
    """
    A file question, an included question, an exam with an inline question,
    all with an attachment of their own. `a.csv` and `d.csv` share their
    bytes, so four links make three hashes.
    """
    root = course(tmp_path)
    write(root, "questions/a.md", CHOICE.format(id="a", origin="a.csv"))
    write(root, "questions/a.csv", b"shared")
    write(root, "questions/x/b.md", CHOICE.format(id="b", origin="b.csv"))
    write(root, "questions/x/b.csv", b"included")
    exam = EXAM_WITH_LINKS.replace(
        "---\nid: free", "---\ninclude: b\n---\n\n---\nid: free"
    )
    write(root, "exams/mid.md", exam)
    write(root, "exams/d.csv", b"inline")
    write(root, "exams/e.csv", b"shared")
    hashes = {
        "shared": sha256(b"shared"),
        "included": sha256(b"included"),
        "inline": sha256(b"inline"),
    }
    return root, hashes


def test_push_asks_the_server_once_about_every_hash_and_writes_the_exam_last(
    full_course, monkeypatch
):
    root, hashes = full_course
    server = FakeServer()

    result = push(monkeypatch, server, root)

    assert result.exit_code == 0, result.output
    (asked,) = server.missing_calls()
    assert asked.body is not None
    assert len(asked.body["hashes"]) == len(set(asked.body["hashes"]))
    assert set(asked.body["hashes"]) == set(hashes.values())
    questions, (exam,) = server.puts("question"), server.puts("exam")
    assert {q.body["slug"] for q in questions if q.body} == {
        "a",
        "b",
        "mid-linked",
        "mid-free",
    }
    assert server.index(asked) < min(server.index(q) for q in questions)
    assert server.index(exam) > max(server.index(q) for q in questions)


def test_push_uploads_each_missing_blob_once_with_the_first_put_that_cites_it(
    tmp_path, monkeypatch
):
    root = course(tmp_path)
    write(root, "questions/q1.md", CHOICE.format(id="q1", origin="shared.csv"))
    write(root, "questions/shared.csv", b"shared")
    write(root, "questions/q2.md", CHOICE.format(id="q2", origin="other.csv"))
    write(root, "questions/other.csv", b"other")
    write(
        root,
        "exams/mid.md",
        "# [mid] Mid\n\nRead.\n\n## [attachments]\n\n[x](shared.csv)\n\n"
        "---\ninclude: q1\n---\n",
    )
    write(root, "exams/shared.csv", b"shared")
    h1, h2 = sha256(b"shared"), sha256(b"other")
    server = FakeServer(missing=[h1])

    result = push(monkeypatch, server, root)

    assert result.exit_code == 0, result.output
    carriers = [c for c in server.calls if c.parts is not None and h1 in c.parts]
    (carrier,) = carriers
    assert carrier.path == f"{BASE}/question"
    assert carrier.body is not None and carrier.body["slug"] == "q1"
    assert set(carrier.parts or {}) == {"json", h1}
    assert carrier.parts[h1] == b"shared"  # type: ignore[index]
    assert carrier.body["files"] == {"shared.csv": h1}
    assert all(h2 not in (c.parts or {}) for c in server.calls)
    (exam,) = server.puts("exam")
    assert exam.parts is None
    assert exam.content_type == "application/json"
    assert exam.body is not None and exam.body["files"] == {"shared.csv": h1}
    assert server.index(carrier) < server.index(exam)
    (q2,) = [c for c in server.puts("question") if c.body and c.body["slug"] == "q2"]
    assert q2.content_type == "application/json"
    assert q2.body is not None and q2.body["files"] == {"other.csv": h2}


def test_push_sends_json_when_the_server_lacks_nothing(full_course, monkeypatch):
    root, hashes = full_course
    server = FakeServer(missing=[])

    result = push(monkeypatch, server, root)

    assert result.exit_code == 0, result.output
    writes = server.puts("question") + server.puts("exam")
    assert len(writes) == 5
    assert all(c.content_type == "application/json" for c in writes)
    assert all(c.parts is None for c in writes)
    sent = {h for c in writes for h in (c.body or {}).get("files", {}).values()}
    assert sent == set(hashes.values())


def test_a_413_fails_that_question_and_the_push_goes_on(tmp_path, monkeypatch):
    root = course(tmp_path)
    write(root, "questions/big.md", CHOICE.format(id="big", origin="huge.csv"))
    write(root, "questions/huge.csv", b"h" * 100)
    write(root, "questions/small.md", CHOICE.format(id="small", origin="tiny.csv"))
    write(root, "questions/tiny.csv", b"t")
    write(root, "exams/mid.md", "# [mid] Mid\n\nRead.\n")
    server = FakeServer(too_large=["big"])

    result = push(monkeypatch, server, root)

    assert result.exit_code == 1
    text = flat(result.output)
    assert re.search(r"16\s?MiB", text)
    assert "huge.csv" in text
    assert {c.body["slug"] for c in server.puts("question") if c.body} == {
        "big",
        "small",
    }
    assert len(server.puts("exam")) == 1


class StatefulServer(FakeServer):
    """
    A `FakeServer` that keeps the course and the questions it was sent and
    answers with them, so a second push sees what the first one wrote.
    """

    def __init__(self) -> None:
        super().__init__(missing=[])
        self.stored: dict[str, dict] = {}
        self.has_course = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        if method == "GET" and path == BASE and self.has_course:
            return httpx.Response(200, json=course_json())
        response = super().handle(request)
        if method == "PUT" and path == "/api/course":
            self.has_course = True
        if method == "PUT" and path == f"{BASE}/question":
            body = json.loads(request.content)
            self.stored[body["slug"]] = {
                **stored_question(body),
                "files": body.get("files"),
            }
        elif method == "GET" and path == f"{BASE}/question":
            return httpx.Response(200, json=list(self.stored.values()))
        return response


def test_editing_only_a_linked_file_pushes_only_that_question_after_a_push(
    tmp_path, monkeypatch
):
    root = course(tmp_path)
    write(root, "questions/pick.md", CHOICE.format(id="pick", origin="data.csv"))
    csv = write(root, "questions/data.csv", b"x,y\n1,2\n")
    write(root, "questions/other.md", PLAIN_CHOICE.replace("pick", "other"))
    server = StatefulServer()
    assert push(monkeypatch, server, root).exit_code == 0

    server.calls.clear()
    assert push(monkeypatch, server, root).exit_code == 0
    assert server.puts("question") == []

    csv.write_bytes(b"x,y\n1,3\n")
    server.calls.clear()
    result = push(monkeypatch, server, root)

    assert result.exit_code == 0, result.output
    (put,) = server.puts("question")
    assert put.body is not None
    assert put.body["slug"] == "pick"
    assert put.body["files"] == {"data.csv": sha256(b"x,y\n1,3\n")}
