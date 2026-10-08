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
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.api import generated
from codehood.cli.base import app
from codehood.models.repo import CourseIdentity, ServerConfig
from codehood.repo import write_repo

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
    first = runner.invoke(app, ["push", str(course_repo)])
    assert first.exit_code == 0, first.output
    assert "mon" in _time_slot_slugs(client)
    assert (0, "mon") in _calendar_event_keys(client)

    second = runner.invoke(app, ["push", str(course_repo), "--dry-run"])
    assert second.exit_code == 0, second.output
    # A seeded CANCELLED event pins its time slot, so the plan may still
    # carry a "kept" notice for it. That notice is not a write.
    planned = [
        line for line in second.output.splitlines() if line.startswith("planned")
    ]
    writes = [line for line in planned if " kept " not in line]
    assert [line for line in writes if "time slot" in line or " event " in line] == []


def test_push_then_delete_then_push_converges_on_the_real_server(
    course_repo: Path, client: httpx.Client
):
    first = runner.invoke(app, ["push", str(course_repo)])
    assert first.exit_code == 0, first.output
    assert {"hello", "greet"} <= _slugs(client)

    (course_repo / "resources" / "hello.md").unlink()

    second = runner.invoke(app, ["push", str(course_repo)])
    assert second.exit_code == 0, second.output

    slugs = _slugs(client)
    assert "hello" not in slugs
    assert "greet" in slugs


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
    first = runner.invoke(app, ["push", str(course_repo_with_questions)])
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
    return [line for line in planned if " kept " not in line]


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
        for resource in read_local_state(course_repo).resources
    }["hello"]
    assert expected is not None, "the link in calendar.md did not attach hello.md"

    first = runner.invoke(app, ["push", str(course_repo)])
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
    assert server_resources["greet"].event is None

    second = runner.invoke(app, ["push", str(course_repo), "--dry-run"])
    assert second.exit_code == 0, second.output
    writes = _planned_writes(second.output)
    assert [line for line in writes if " event " in line or "resource" in line] == []
