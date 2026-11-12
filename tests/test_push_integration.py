"""
End-to-end test for `codehood push` against a real dev server. See
`dev/specs/to-do/push.md`'s "Proof" section: init a course, push it,
resources visible; delete a local file, push again, resource gone.
MD/CODE only -- FILE is planned but not executed this slice.

Skipped by default, same as `tests/test_api_integration.py`: run with
`--run-integration` and a server answering at `CODEHOOD_SERVER`.

**This test mutates the shared dev server's `cs101`/`ada_2026-1` course.**
That course ships pre-seeded demo resources (`sicp-ch1`, `toolchain`,
`syllabus`, `factorial` -- verified against the running dev server while
writing this test). Push's default pruning behavior means the first push
this test makes deletes every one of them, since a freshly-scaffolded
local repository's `resources/` starts empty of them. There is no admin
endpoint available to this suite to create a disposable discipline/edition
to push against instead (`ROADBLOCKS.md` candidate), and `ada`/`2026-1` is
the exact course the spec's own "Proof" section names. Gated behind
`CODEHOOD_RUN_DESTRUCTIVE_PUSH_TEST=1` on top of `--run-integration` so
opting into the destructive suite is a separate, deliberate choice from
opting into integration tests in general -- flagged to the orchestrator,
not decided unilaterally here.

The first push of each test passes `--ours '*'`: a fresh checkout has no base,
so the seeded course differs from it and would otherwise be a conflict.
"""

from __future__ import annotations

import os
import re
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.api import generated
from codehood.cli.base import app
from codehood.models.repo import CourseIdentity, RepoConfig, ServerConfig
from codehood.repo import MACHINE_DIR, write_repo

pytestmark = pytest.mark.integration

SERVER_URL = os.environ.get("CODEHOOD_SERVER", "http://localhost:4321")
DISCIPLINE = "cs101"
INSTRUCTOR = "ada"
EDITION = "2026-1"
COURSE = f"{INSTRUCTOR}_{EDITION}"

runner = CliRunner()


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    live_client = httpx.Client(base_url=SERVER_URL, timeout=5.0)
    try:
        live_client.get("/openapi.json")
    except httpx.TransportError as exc:
        pytest.skip(f"no Codehood server reachable at {SERVER_URL} ({exc})")
    return live_client


@pytest.fixture(autouse=True)
def _require_destructive_opt_in():
    if os.environ.get("CODEHOOD_RUN_DESTRUCTIVE_PUSH_TEST") != "1":
        pytest.skip(
            "deletes cs101/ada_2026-1's pre-seeded demo resources -- set "
            "CODEHOOD_RUN_DESTRUCTIVE_PUSH_TEST=1 to opt in"
        )


@pytest.fixture(autouse=True)
def _real_credentials_store(tmp_path_factory, monkeypatch):
    """
    A scratch credentials store so this test never touches -- or depends
    on -- whatever is in the real `~/.codehood/credentials.toml`.
    """
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)


@pytest.fixture
def logged_in(client: httpx.Client) -> None:
    result = generated.login(
        body=generated.LoginRequest(login="ada", password="ada"), client=client
    )
    # The login sets a session cookie; the server rejects it next to the Bearer.
    client.cookies.clear()
    base_module.save_token(SERVER_URL, result.token)


@pytest.fixture
def course_repo(tmp_path: Path, logged_in: None) -> Path:
    write_repo(
        tmp_path,
        CourseIdentity(discipline=DISCIPLINE, instructor=INSTRUCTOR, edition=EDITION),
        ServerConfig(url=SERVER_URL),
        git=False,
        examples=False,
    )
    resources = tmp_path / "resources"
    (resources / "hello.md").write_text(
        "# Hello\n\nPushed by the push integration test.\n", encoding="utf-8"
    )
    (resources / "greet.py").write_text(
        "def greet(name):\n    return f'hello, {name}'\n", encoding="utf-8"
    )
    return tmp_path


EXAMPLE_QUESTIONS_DIR = Path(__file__).parent / "examples" / "ada-basic" / "questions"


@pytest.fixture
def course_repo_with_questions(course_repo: Path) -> Path:
    """
    `course_repo`, plus `tests/examples/ada-basic/questions/` copied in whole --
    the spec's own "Acceptance" fixture: "exactly two questions
    (example.md, fat.md)".
    """
    import shutil

    # `write_repo` already created an empty `questions/` directory as part
    # of the standard layout, so files are copied in rather than the
    # whole tree replaced.
    questions = course_repo / "questions"
    for source in EXAMPLE_QUESTIONS_DIR.iterdir():
        shutil.copy(source, questions / source.name)
    return course_repo


def _slugs(client: httpx.Client) -> set[str]:
    resources = generated.list_resource(
        discipline=DISCIPLINE, course=COURSE, client=client
    )
    return {resource.slug for resource in resources}


def _question_slugs(client: httpx.Client, *, archived: bool = False) -> set[str]:
    """
    The server's question slugs, by default only the live ones.

    `DELETE .../question/{slug}` archives rather than removes, and an
    unfiltered listing still returns the row -- see `ROADBLOCKS.md`. The
    live set is what `push.run.fetch_server_state` reads and therefore
    what "the server holds these questions" means to the CLI; pass
    `archived=True` to see the tombstones too.
    """
    questions = generated.list_question(
        discipline=DISCIPLINE,
        course=COURSE,
        statuses=None if archived else ["DRAFT", "PUBLISHED"],
        client=client,
    )
    return {question.slug for question in questions}


def _time_slot_slugs(client: httpx.Client) -> set[str]:
    slots = generated.list_timeslot(discipline=DISCIPLINE, course=COURSE, client=client)
    return {slot.slug for slot in slots}


def _calendar_event_keys(client: httpx.Client) -> set[tuple[int, str]]:
    events = generated.list_calendar_event(
        discipline=DISCIPLINE, course=COURSE, client=client
    )
    return {(event.week, event.time_slot.slug) for event in events}


def test_push_writes_the_calendar_and_reconverges_on_a_second_run(
    course_repo: Path, client: httpx.Client
):
    """
    `push-calendar.handoff.md`'s acceptance criteria: "`codehood push`
    against the live dev server writes the calendar, and a second run
    reports nothing but the course row." `course_repo` is scaffolded by
    `write_repo`, which writes the stock `calendar.md` -- one Monday
    lecture slot and one undated "Course overview" section, so a push
    always has exactly one `TimeSlot` and one `Event` to converge on.
    """
    first = runner.invoke(app, ["push", str(course_repo), "--ours", "*"])
    assert first.exit_code == 0, first.output
    assert "mon" in _time_slot_slugs(client)
    # Start is Thu 2026-01-01, so the first Monday falls in the next ISO week.
    assert (1, "mon") in _calendar_event_keys(client)

    second = runner.invoke(app, ["push", str(course_repo), "--dry-run"])
    assert second.exit_code == 0, second.output
    # A seeded CANCELLED event pins its time slot and a seeded roll call
    # pins its meeting, so the plan may still carry "kept" notices for them.
    # Those notices are not writes.
    writes = _planned_writes(second.output)
    assert [line for line in writes if "time slot" in line or " event " in line] == []


def test_push_then_delete_then_push_converges_on_the_real_server(
    course_repo: Path, client: httpx.Client
):
    first = runner.invoke(app, ["push", str(course_repo), "--ours", "*"])
    assert first.exit_code == 0, first.output
    assert {"hello", "greet.py"} <= _slugs(client)

    (course_repo / "resources" / "hello.md").unlink()

    second = runner.invoke(app, ["push", str(course_repo)])
    assert second.exit_code == 0, second.output

    slugs = _slugs(client)
    assert "hello" not in slugs
    assert "greet.py" in slugs


def test_push_questions_matches_the_repository_exactly_and_reconverges(
    course_repo_with_questions: Path, client: httpx.Client
):
    """
    `dev/specs/to-do/push-questions.md`'s "Acceptance": pushing
    `tests/examples/ada-basic` (`example.md`, `fat.md`) leaves the server's
    question bank holding exactly those two, whatever it held before --
    and a second `ch push` immediately after plans zero question
    operations.
    """
    first = runner.invoke(app, ["push", str(course_repo_with_questions), "--ours", "*"])
    assert first.exit_code == 0, first.output
    assert _question_slugs(client) == {"example", "fat"}
    # The pre-seeded questions are gone from the live set but survive as
    # archived rows -- the server gap this test is pinned against.
    assert _question_slugs(client, archived=True) > {"example", "fat"}

    second = runner.invoke(app, ["push", str(course_repo_with_questions), "--dry-run"])
    assert second.exit_code == 0, second.output
    assert "question" not in second.output
    assert "delete question" not in second.output


def _planned_writes(output: str) -> list[str]:
    """The `planned` lines of a dry run that are real writes, not notices."""
    planned = [line for line in output.splitlines() if line.startswith("planned")]
    return [line for line in planned if not re.search(r" kept\b", line)]


def test_push_attaches_a_linked_resource_to_its_lesson_and_reconverges(
    course_repo: Path, client: httpx.Client
):
    """
    A resource linked from a `calendar.md` lesson comes back from the server
    carrying that lesson's event key, and a second push plans no event and
    no resource write.
    """
    from codehood.cli.push import read_local_state

    calendar = course_repo / "calendar.md"
    calendar.write_text(
        calendar.read_text(encoding="utf-8")
        + "\nRead the [greeting](resources/hello.md).\n",
        encoding="utf-8",
    )
    expected = {
        resource.slug: resource.event
        for resource in read_local_state(
            course_repo, RepoConfig.open(course_repo)
        ).resources
    }["hello"]
    assert expected is not None, "the link in calendar.md did not attach hello.md"

    first = runner.invoke(app, ["push", str(course_repo), "--ours", "*"])
    assert first.exit_code == 0, first.output

    server_resources = {
        resource.slug: resource
        for resource in generated.list_resource(
            discipline=DISCIPLINE, course=COURSE, client=client
        )
    }
    event = server_resources["hello"].event
    assert event is not None
    assert (event.week, event.time_slot) == (expected.week, expected.time_slot)
    assert server_resources["greet.py"].event is None

    second = runner.invoke(app, ["push", str(course_repo), "--dry-run"])
    assert second.exit_code == 0, second.output
    writes = _planned_writes(second.output)
    assert [line for line in writes if " event " in line or "resource" in line] == []


#
# Sync with a server that changes behind the CLI's back
#
# These run on `cs101/ada_2026-2`, which each test clears of resources and
# takes over with `--ours '*'`, so they never touch the course the tests above
# use. `DELETE` of a course answers 500, so it cannot be rebuilt from scratch.
#
SCRATCH_EDITION = "2026-2"
SCRATCH = f"{INSTRUCTOR}_{SCRATCH_EDITION}"
WEB = "Edited on the web"


@pytest.fixture
def write_requests(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    The `<METHOD> <path>` of every write the CLI sends from now on.
    """
    sent: list[str] = []
    send = httpx.Client.send

    def recording(
        self: httpx.Client, request: httpx.Request, **kwargs
    ) -> httpx.Response:
        if request.method not in ("GET", "HEAD"):
            sent.append(f"{request.method} {request.url.path}")
        return send(self, request, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", recording)
    return sent


@pytest.fixture
def synced(
    tmp_path: Path, client: httpx.Client, logged_in: None, write_requests: list[str]
) -> Iterator[Path]:
    """
    A scratch course repository, pushed once: the server holds exactly what
    the repository holds, and the base records it.
    """
    for slug in _resource_slugs(client):
        generated.delete_resource(
            discipline=DISCIPLINE, course=SCRATCH, slug=slug, client=client
        )
    write_repo(
        tmp_path,
        CourseIdentity(
            discipline=DISCIPLINE, instructor=INSTRUCTOR, edition=SCRATCH_EDITION
        ),
        ServerConfig(url=SERVER_URL),
        git=False,
        examples=False,
    )
    (tmp_path / "resources" / "hello.md").write_text("# Hello\n\nLocal.\n")
    # Whatever the seed left on the course has no source here: take it over.
    first = _push(tmp_path, "--ours", "*")
    assert first.exit_code == 0, first.output
    write_requests.clear()
    yield tmp_path


def _push(repo: Path, *args: str):
    return runner.invoke(app, ["push", str(repo), *args])


def _resource(client: httpx.Client, slug: str) -> generated.Resource:
    return generated.read_resource(
        discipline=DISCIPLINE, course=SCRATCH, slug=slug, client=client
    )


def _resource_slugs(client: httpx.Client) -> set[str]:
    return {
        r.slug
        for r in generated.list_resource(
            discipline=DISCIPLINE, course=SCRATCH, client=client
        )
    }


def _patch(client: httpx.Client, path: str, body: dict) -> None:
    """
    `PATCH` only the given fields, as the web does. The generated request
    models send every unset field as `null`, which the server rejects.
    """
    response = client.patch(
        f"/api/course/{DISCIPLINE}/{SCRATCH}/{path}",
        json=body,
        headers=base_module.auth_headers(client),
    )
    assert response.status_code < 400, response.text


def _md(resource: generated.Resource) -> str:
    assert isinstance(resource.data, generated.DataMd)
    return resource.data.content


def _event(client: httpx.Client) -> generated.CalendarEvent:
    return generated.read_calendar_event(
        discipline=DISCIPLINE, course=SCRATCH, week="1", time_slot="mon", client=client
    )


def test_a_resource_edited_on_the_web_stays_and_shows_as_a_pull(
    synced: Path, client: httpx.Client
):
    before = _resource(client, "hello")
    _patch(client, "resource/hello", {"data": {"type": "MD", "content": "# Web\n"}})
    assert _resource(client, "hello").rev == before.rev

    result = _push(synced)

    assert result.exit_code == 0, result.output
    assert _md(_resource(client, "hello")) == "# Web\n"
    assert re.search(r"pull .*resource hello", result.output), result.output


def test_an_event_edited_on_the_web_stays_and_shows_as_a_pull(
    synced: Path, client: httpx.Client
):
    before = _event(client)
    _patch(client, "calendar-event/1/mon", {"title": WEB})
    assert _event(client).rev == before.rev

    try:
        result = _push(synced)

        assert result.exit_code == 0, result.output
        assert _event(client).title == WEB
        assert re.search(r"pull .*calendar event 1/mon", result.output), result.output
    finally:
        # The scratch course outlives the test: a title left edited would
        # show up as a pull in every push that follows.
        _patch(client, "calendar-event/1/mon", {"title": before.title})


def test_a_resource_created_on_the_web_is_kept_and_shows_as_a_pull(
    synced: Path, client: httpx.Client
):
    generated.create_resource(
        discipline=DISCIPLINE,
        course=SCRATCH,
        body=generated.ResourceCreate(
            slug="web-made", title="Web", data=generated.DataMd(type="MD", content="x")
        ),
        client=client,
    )

    result = _push(synced)

    assert result.exit_code == 0, result.output
    assert "web-made" in _resource_slugs(client)
    assert re.search(r"pull .*resource web-made", result.output), result.output


def test_edits_on_both_sides_conflict_and_ours_sends_the_local_version(
    synced: Path, client: httpx.Client, write_requests: list[str]
):
    _patch(client, "resource/hello", {"data": {"type": "MD", "content": "# Web\n"}})
    (synced / "resources" / "hello.md").write_text("# Hello\n\nLocal edit.\n")
    write_requests.clear()

    conflicted = _push(synced)

    assert conflicted.exit_code != 0, conflicted.output
    assert re.search(r"^conflict .*resource hello", conflicted.output, re.MULTILINE)
    assert _md(_resource(client, "hello")) == "# Web\n"
    assert write_requests == []

    ours = _push(synced, "--ours", "resource/hello")

    assert ours.exit_code == 0, ours.output
    assert "Local edit." in _md(_resource(client, "hello"))
    clean = _push(synced, "--dry-run")
    assert clean.exit_code == 0, clean.output
    assert not re.search(r"^conflict ", clean.output, re.MULTILINE), clean.output
    assert _planned_writes(clean.output) == []


def test_a_course_in_sync_without_a_base_rebuilds_it_and_writes_nothing(
    synced: Path, client: httpx.Client, write_requests: list[str]
):
    base = synced / MACHINE_DIR / "base"
    assert (base / "resources.json").exists()
    shutil.rmtree(synced / MACHINE_DIR)

    result = _push(synced)

    assert result.exit_code == 0, result.output
    assert not re.search(r"^conflict ", result.output, re.MULTILINE), result.output
    assert write_requests == []
    assert (base / "resources.json").exists()


def test_an_entity_only_the_server_has_with_a_rev_is_other_cli_until_ours(
    synced: Path, client: httpx.Client
):
    generated.create_resource(
        discipline=DISCIPLINE,
        course=SCRATCH,
        body=generated.ResourceCreate(
            slug="theirs",
            title="Theirs",
            rev="somebody-else",
            data=generated.DataMd(type="MD", content="x"),
        ),
        client=client,
    )

    result = _push(synced)

    assert result.exit_code == 0, result.output
    assert re.search(r"other cli .*resource theirs", result.output), result.output
    assert "--ours resource/theirs" in result.output
    assert "theirs" in _resource_slugs(client)

    ours = _push(synced, "--ours", "resource/theirs")

    assert ours.exit_code == 0, ours.output
    assert "theirs" not in _resource_slugs(client)


def test_a_second_push_without_changes_writes_nothing(
    synced: Path, client: httpx.Client, write_requests: list[str]
):
    (synced / "resources" / "hello.md").write_text("# Hello\n\nChanged.\n")
    first = _push(synced)
    assert first.exit_code == 0, first.output
    assert write_requests, "the edit should have been written"
    stamp = _resource(client, "hello").updated_at
    write_requests.clear()

    second = _push(synced)

    assert second.exit_code == 0, second.output
    assert write_requests == []
    assert _resource(client, "hello").updated_at == stamp


QUESTION = "---\ntitle: Sum\n---\n\nWhat is 2 + 2?\n\n- [ ] 3\n- [*] 4\n- [ ] 5\n"


def _question_json(client: httpx.Client, slug: str) -> dict:
    response = client.get(
        f"/api/course/{DISCIPLINE}/{SCRATCH}/question/{slug}",
        headers=base_module.auth_headers(client),
    )
    response.raise_for_status()
    return response.json()


def _edit_question_on_the_server(
    client: httpx.Client, slug: str, **fields: object
) -> None:
    """
    Change the stem and version of a question through the REST API, plus `fields`.
    """
    question = _question_json(client, slug)["question"]
    question["stem"] = WEB
    body = {"question": question, "version": "web-edit", **fields}
    _patch(client, f"question/{slug}", body)


def test_a_pushed_question_carries_a_rev_and_an_edit_with_a_new_rev_is_other_cli(
    synced: Path, client: httpx.Client
):
    (synced / "questions" / "sum.md").write_text(QUESTION, encoding="utf-8")
    first = _push(synced)
    assert first.exit_code == 0, first.output
    stored = _question_json(client, "sum")
    assert stored["rev"] == stored["version"]

    _edit_question_on_the_server(client, "sum", rev="pushed-by-somebody-else")
    result = _push(synced)

    assert result.exit_code == 0, result.output
    assert re.search(r"other cli .*question sum", result.output), result.output
    assert not re.search(r"^pull +question", result.output, re.MULTILINE), result.output
    assert _question_json(client, "sum")["question"]["stem"] == WEB


def test_a_question_edited_keeping_its_rev_shows_as_a_pull(
    synced: Path, client: httpx.Client
):
    (synced / "questions" / "sum.md").write_text(QUESTION, encoding="utf-8")
    first = _push(synced)
    assert first.exit_code == 0, first.output

    _edit_question_on_the_server(client, "sum")
    result = _push(synced)

    assert result.exit_code == 0, result.output
    assert re.search(r"pull .*question sum", result.output), result.output
    assert "other cli" not in result.output
    assert _question_json(client, "sum")["question"]["stem"] == WEB


def test_a_question_created_over_rest_without_a_rev_is_a_pull_and_ours_keeps_it(
    synced: Path, client: httpx.Client
):
    (synced / "questions" / "sum.md").write_text(QUESTION, encoding="utf-8")
    assert _push(synced).exit_code == 0
    slug = f"web-{uuid.uuid4().hex[:8]}"
    body = {
        "slug": slug,
        "status": "PUBLISHED",
        "version": "web-v1",
        "question": _question_json(client, "sum")["question"],
    }
    response = client.post(
        f"/api/course/{DISCIPLINE}/{SCRATCH}/question",
        json=body,
        headers=base_module.auth_headers(client),
    )
    assert response.status_code < 400, response.text
    try:
        assert _question_json(client, slug)["rev"] is None

        result = _push(synced, "--ours", "*")

        assert re.search(rf"pull .*question {slug}", result.output), result.output
        assert f"delete question {slug}" not in result.output, result.output
        assert slug in {
            q["slug"]
            for q in client.get(
                f"/api/course/{DISCIPLINE}/{SCRATCH}/question",
                params={"statuses": ["DRAFT", "PUBLISHED", "HIDDEN"]},
                headers=base_module.auth_headers(client),
            ).json()
        }
    finally:
        client.delete(
            f"/api/course/{DISCIPLINE}/{SCRATCH}/question/{slug}",
            headers=base_module.auth_headers(client),
        )


def test_a_server_edit_of_an_event_with_a_roll_call_survives_a_push_and_blocks_the_drop(
    synced: Path, client: httpx.Client
):
    """
    The seed gives the scratch course a roll call on `0/wed`, which the
    repository has no lesson for. A plain push keeps it; once the server edits
    the event, neither a plain push nor `--drop-roll-calls` may forget the edit.
    """

    def wed() -> generated.CalendarEvent:
        return generated.read_calendar_event(
            discipline=DISCIPLINE,
            course=SCRATCH,
            week="0",
            time_slot="wed",
            client=client,
        )

    def roll_calls() -> set[tuple[int, str]]:
        return {
            (r.week, r.time_slot)
            for r in generated.list_roll_call(
                discipline=DISCIPLINE, course=SCRATCH, client=client
            )
        }

    assert (0, "wed") in roll_calls()
    before = wed()
    assert _push(synced).exit_code == 0
    _patch(client, "calendar-event/0/wed", {"title": WEB})
    try:
        plain = _push(synced)
        assert "calendar event 0/wed" in plain.output, plain.output

        dropped = _push(synced, "--drop-roll-calls")

        assert dropped.exit_code == 1, dropped.output
        assert re.search(r"conflict +calendar event 0/wed", dropped.output)
        assert (0, "wed") in roll_calls()
        assert wed().title == WEB
    finally:
        _patch(client, "calendar-event/0/wed", {"title": before.title})


def test_a_rebuilt_base_of_a_full_course_syncs_without_a_decision_or_a_write(
    synced: Path, client: httpx.Client, write_requests: list[str]
):
    """
    A resource of each kind, a question, a lesson link and a grade column go
    up, then the base is deleted: nothing is a decision, nothing is sent.
    """
    calendar = synced / "calendar.md"
    calendar.write_text(
        calendar.read_text(encoding="utf-8")
        + "\nRead the [notes](resources/notes.md).\n",
        encoding="utf-8",
    )
    (synced / "resources" / "notes.md").write_text("# Notes\n\nLinked.\n")
    (synced / "resources" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\nnot really")
    (synced / "questions" / "sum.md").write_text(QUESTION, encoding="utf-8")
    config = synced / "codehood.toml"
    config.write_text(
        config.read_text(encoding="utf-8")
        + '\n[[grades.column]]\nslug = "total"\ntitle = "Total"\n',
        encoding="utf-8",
    )
    (synced / "grades.csv").write_text("username,total\nbob,7\n", encoding="utf-8")
    first = _push(synced)
    assert first.exit_code == 0, first.output
    assert _resource(client, "notes").event is not None
    shutil.rmtree(synced / MACHINE_DIR)
    write_requests.clear()

    result = _push(synced)

    assert result.exit_code == 0, result.output
    # The scratch course also holds time slots the seed created (`tue`, `thu`),
    # which always show as pulls and are none of this course's content.
    decisions = re.findall(
        r"^(?:pull|conflict|other cli) +(?:course|resource|question|calendar event"
        r"|grade column)\b.*$",
        result.output,
        re.MULTILINE,
    )
    assert decisions == []
    assert write_requests == []
    assert (synced / MACHINE_DIR / "base" / "questions.json").exists()
