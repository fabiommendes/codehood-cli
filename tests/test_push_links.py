"""
Tests for `codehood.push.links` and the event attachment it feeds: a markdown
link inside a `calendar.md` lesson to a file under `resources/` attaches that
resource to the lesson's event. See `dev/specs/to-do/resources-on-calendar-events.md`,
R7.
"""

from __future__ import annotations

import importlib
import json
from datetime import date
from pathlib import Path, PurePosixPath

import httpx
import pytest
from typer.testing import CliRunner

from codehood.api import base as base_module
from codehood.cli.base import app
from codehood.push.calendar import Event, EventKey
from codehood.push.errors import ResourceLinkError
from codehood.push.links import (
    attach_resources,
    extract_resource_links,
    rewrite_event_links,
    rewrite_resource_links,
)
from codehood.push.plan import (
    DeleteCalendarEvent,
    DeleteResource,
    LocalState,
    PushOp,
    ServerEvent,
    ServerState,
    UpsertCalendarEvent,
    UpsertResource,
    plan_push,
)
from codehood.push.resource import (
    MdData,
    ResourceFile,
    content_ref,
    scan_resources,
)

ROOT = Path("/course")


def _resource(rel: str, slug: str | None = None) -> ResourceFile:
    data = MdData(content="body")
    return ResourceFile(
        slug=slug or rel.removeprefix("resources/").replace("/", "-").split(".")[0],
        title=rel,
        description=None,
        data=data,
        ref=content_ref(rel, None, data),
        path=ROOT / rel,
    )


def _event(week: int, slot: str, description: str, title: str = "Lesson") -> Event:
    return Event(week=week, time_slot=slot, title=title, description=description)


#
# extract_resource_links
#
@pytest.mark.parametrize(
    "markdown, expected",
    [
        ("[Slides](resources/w03/recursion.pdf)", ["resources/w03/recursion.pdf"]),
        ("[Slides](./resources/w03/recursion.pdf)", ["resources/w03/recursion.pdf"]),
        (
            "[A](resources/a.pdf) and [B](resources/b.pdf)",
            ["resources/a.pdf", "resources/b.pdf"],
        ),
        ("[Site](https://example.com/resources/a.pdf)", []),
        ("[Other](notes/a.pdf)", []),
        ("[Up](../resources/a.pdf)", []),
        ("[Anchor](#resources)", []),
        ("no links, just resources/a.pdf in prose", []),
        ("[Page](resources/a.pdf#page=2)", ["resources/a.pdf"]),
        ("[Q](resources/a.pdf?download=1)", ["resources/a.pdf"]),
        ("[Space](resources/my%20slides.pdf)", ["resources/my slides.pdf"]),
    ],
)
def test_extract_resource_links(markdown, expected):
    assert extract_resource_links(markdown) == tuple(
        PurePosixPath(item) for item in expected
    )


#
# attach_resources
#
def test_linked_resource_gets_the_lesson_s_event_key():
    events = [_event(3, "tue", "Read [Slides](resources/w03/recursion.pdf).")]
    [result] = attach_resources(
        events, [_resource("resources/w03/recursion.pdf")], ROOT
    )
    assert result.event == EventKey(week=3, time_slot="tue")


def test_dot_slash_link_attaches_the_same_way():
    events = [_event(1, "mon", "[Slides](./resources/a.md)")]
    [result] = attach_resources(events, [_resource("resources/a.md")], ROOT)
    assert result.event == EventKey(week=1, time_slot="mon")


def test_unlinked_resource_keeps_no_event_and_its_ref():
    resource = _resource("resources/a.md")
    events = [_event(1, "mon", "No links here.")]
    [result] = attach_resources(events, [resource], ROOT)
    assert result == resource
    assert result.event is None


@pytest.mark.parametrize(
    "link",
    [
        "resources/my%20slides.md",
        "resources/my slides.md".replace(" ", "%20") + "#intro",
        "./resources/my%20slides.md?raw=1",
    ],
)
def test_fragment_query_and_percent_encoding_still_match_the_resource(link):
    events = [_event(1, "mon", f"[S]({link})")]
    [result] = attach_resources(events, [_resource("resources/my slides.md")], ROOT)
    assert result.event == EventKey(week=1, time_slot="mon")


def test_links_that_are_not_under_resources_are_ignored():
    events = [
        _event(
            1,
            "mon",
            "[Web](https://example.com/x.pdf) [Doc](docs/x.pdf) [Top](#top)",
        )
    ]
    resource = _resource("resources/a.md")
    assert attach_resources(events, [resource], ROOT) == (resource,)


def test_same_resource_linked_twice_in_one_lesson_is_fine():
    events = [_event(2, "wed", "[A](resources/a.md) again [A](./resources/a.md)")]
    [result] = attach_resources(events, [_resource("resources/a.md")], ROOT)
    assert result.event == EventKey(week=2, time_slot="wed")


def test_each_resource_gets_its_own_lessons_event_and_order_is_kept():
    events = [
        _event(1, "mon", "[A](resources/a.md)"),
        _event(2, "mon", "[B](resources/b.md)"),
    ]
    resources = [
        _resource("resources/b.md"),
        _resource("resources/free.md"),
        _resource("resources/a.md"),
    ]
    result = attach_resources(events, resources, ROOT)
    assert [r.slug for r in result] == ["b", "free", "a"]
    assert [r.event for r in result] == [
        EventKey(week=2, time_slot="mon"),
        None,
        EventKey(week=1, time_slot="mon"),
    ]


def test_attaching_changes_the_ref_to_include_the_event():
    resource = _resource("resources/a.md")
    [result] = attach_resources(
        [_event(1, "mon", "[A](resources/a.md)")], [resource], ROOT
    )
    assert result.ref != resource.ref
    assert result.ref == content_ref(
        resource.title,
        resource.description,
        resource.data,
        EventKey(week=1, time_slot="mon"),
    )


def test_moving_a_link_to_another_lesson_changes_the_ref():
    resource = _resource("resources/a.md")
    [first] = attach_resources(
        [_event(1, "mon", "[A](resources/a.md)"), _event(2, "mon", "")],
        [resource],
        ROOT,
    )
    [second] = attach_resources(
        [_event(1, "mon", ""), _event(2, "mon", "[A](resources/a.md)")],
        [resource],
        ROOT,
    )
    assert first.ref != second.ref


def test_content_ref_depends_on_the_event_key():
    data = MdData(content="x")
    base = content_ref("t", None, data)
    on_mon = content_ref("t", None, data, EventKey(1, "mon"))
    on_tue = content_ref("t", None, data, EventKey(1, "tue"))
    other_week = content_ref("t", None, data, EventKey(2, "mon"))
    assert len({base, on_mon, on_tue, other_week}) == 4


def test_resource_linked_from_two_lessons_is_an_error_naming_all_three():
    events = [
        _event(1, "mon", "[A](resources/w01/a.md)", title="Intro"),
        _event(2, "tue", "[A](resources/w01/a.md)", title="Recursion"),
    ]
    with pytest.raises(ResourceLinkError) as info:
        attach_resources(events, [_resource("resources/w01/a.md")], ROOT)
    message = str(info.value)
    assert "resources/w01/a.md" in message
    assert "Intro" in message or ("1" in message and "mon" in message)
    assert "Recursion" in message or ("2" in message and "tue" in message)


def test_link_to_a_file_that_is_not_a_resource_is_an_error_naming_the_target():
    events = [_event(1, "mon", "[Gone](resources/w01/missing.pdf)")]
    with pytest.raises(ResourceLinkError, match=r"resources/w01/missing\.pdf"):
        attach_resources(events, [_resource("resources/w01/a.md")], ROOT)


def test_dot_slash_link_to_a_missing_resource_is_also_an_error():
    events = [_event(1, "mon", "[Gone](./resources/missing.pdf)")]
    with pytest.raises(ResourceLinkError, match=r"resources/missing\.pdf"):
        attach_resources(events, [], ROOT)


#
# rewrite_resource_links / rewrite_event_links
#
URLS = {
    PurePosixPath(
        "resources/w03/recursion.md"
    ): "/cs101/ada_2026-1/resources/w03-recursion"
}


@pytest.mark.parametrize(
    "markdown, expected",
    [
        (
            "See [Slides](resources/w03/recursion.md).",
            "See [Slides](/cs101/ada_2026-1/resources/w03-recursion).",
        ),
        (
            "See [Slides](./resources/w03/recursion.md).",
            "See [Slides](/cs101/ada_2026-1/resources/w03-recursion).",
        ),
        (
            "[Slides](resources/w03/recursion.md#page=2)",
            "[Slides](/cs101/ada_2026-1/resources/w03-recursion#page=2)",
        ),
        (
            "[A](resources/w03/recursion.md) and [B](resources/w03/recursion.md)",
            "[A](/cs101/ada_2026-1/resources/w03-recursion) and "
            "[B](/cs101/ada_2026-1/resources/w03-recursion)",
        ),
    ],
)
def test_rewrite_resource_links_replaces_the_target_and_keeps_text_and_fragment(
    markdown, expected
):
    assert rewrite_resource_links(markdown, URLS) == expected


@pytest.mark.parametrize(
    "markdown",
    [
        "[Web](https://example.com/resources/w03/recursion.md)",
        "[Other](docs/recursion.md) and [Top](#top)",
        "[Unknown](resources/w03/other.md)",
        "Plain text mentioning resources/w03/recursion.md.",
        "",
    ],
)
def test_rewrite_resource_links_leaves_everything_else_untouched(markdown):
    assert rewrite_resource_links(markdown, URLS) == markdown


def test_rewrite_event_links_points_links_at_the_resource_page():
    events = [
        _event(1, "mon", "Read [Slides](resources/w01/intro.md#top) now.", "Intro"),
        _event(2, "tue", "Nothing here. [Web](https://example.com)", "Other"),
    ]
    resources = [_resource("resources/w01/intro.md")]
    [first, second] = rewrite_event_links(
        events, resources, ROOT, "cs101", "ada_2026-1"
    )
    assert first.description == (
        "Read [Slides](/cs101/ada_2026-1/resources/w01-intro#top) now."
    )
    assert (first.week, first.time_slot, first.title) == (1, "mon", "Intro")
    assert second == events[1]


def test_rewrite_event_links_uses_each_resource_s_own_slug():
    events = [_event(1, "mon", "[A](resources/a.md) [B](resources/sub/b.md)")]
    resources = [_resource("resources/a.md"), _resource("resources/sub/b.md")]
    [event] = rewrite_event_links(events, resources, ROOT, "d", "c")
    assert event.description == "[A](/d/c/resources/a) [B](/d/c/resources/sub-b)"


#
# plan and run carry the event
#
def test_plan_carries_the_event_on_the_upsert():
    base = _resource("resources/a.md")
    resource = ResourceFile(
        slug=base.slug,
        title=base.title,
        description=base.description,
        data=base.data,
        ref="ref-with-event",
        path=base.path,
        event=EventKey(week=3, time_slot="tue"),
    )
    local = LocalState(
        discipline="cs101",
        course="ada_2026-1",
        description="d",
        start=date(2026, 1, 1),
        end=date(2026, 6, 1),
        resources=(resource,),
    )
    [op] = [o for o in plan_push(local, ServerState()) if isinstance(o, UpsertResource)]
    assert op.event == EventKey(week=3, time_slot="tue")


def test_run_sends_the_event_key_in_the_resource_payload():
    from codehood.push.run import run_plan

    sent: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "slug": "a",
                "title": "a",
                "description": None,
                "data": {"type": "MD", "content": "body"},
                "event": None,
                "rev": "r",
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-01T00:00:00Z",
            },
        )

    op = UpsertResource(
        slug="a",
        title="a",
        description=None,
        data=MdData(content="body"),
        ref="r",
        path=Path("resources/a.md"),
        event=EventKey(week=3, time_slot="tue"),
    )
    client = httpx.Client(
        base_url="http://localhost:4321",
        transport=httpx.MockTransport(handler),
    )
    [result] = list(
        run_plan([op], discipline="cs101", course="ada_2026-1", client=client)
    )
    assert result.ok is True
    assert sent["event"] == {"week": 3, "timeSlot": "tue"}


#
# read_local_state wires it together
#
push_module = importlib.import_module("codehood.cli.push")

TOML = (
    '[course]\ndiscipline = "cs101"\ninstructor = "ada"\nedition = "2026-1"\n'
    '\n[server]\nurl = "http://localhost:4321"\n'
)


def _calendar(first: str, second: str = "") -> str:
    return f"""---
start: 2026-01-05
end:   2026-06-01
days:
  - Mon 14:00 2h, Lecture
holidays: []
---

## First lesson

{first}

## Second lesson

{second}
"""


def _repo(tmp_path: Path, calendar: str, files=("resources/w03/recursion.md",)) -> Path:
    (tmp_path / "codehood.toml").write_text(TOML, encoding="utf-8")
    (tmp_path / "README.md").write_text("# CS101\n\nA description.\n", encoding="utf-8")
    (tmp_path / "calendar.md").write_text(calendar, encoding="utf-8")
    for rel in files:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Recursion\n\nBody.\n", encoding="utf-8")
    return tmp_path


def test_read_local_state_attaches_the_linked_resource(tmp_path):
    repo = _repo(tmp_path, _calendar("[Slides](resources/w03/recursion.md)"))
    local = push_module.read_local_state(repo)
    [resource] = local.resources
    assert resource.event == EventKey(week=0, time_slot="mon")


def test_read_local_state_leaves_an_unlinked_resource_without_event(tmp_path):
    repo = _repo(tmp_path, _calendar("Nothing linked."))
    [resource] = push_module.read_local_state(repo).resources
    assert resource.event is None
    assert resource == next(scan_resources(repo))


def test_read_local_state_rejects_a_resource_linked_from_two_lessons(tmp_path):
    link = "[Slides](resources/w03/recursion.md)"
    repo = _repo(tmp_path, _calendar(link, link))
    with pytest.raises(ResourceLinkError, match=r"resources/w03/recursion\.md"):
        push_module.read_local_state(repo)


def test_read_local_state_rejects_a_link_to_a_missing_resource(tmp_path):
    repo = _repo(tmp_path, _calendar("[Slides](resources/w03/nope.md)"))
    with pytest.raises(ResourceLinkError, match=r"resources/w03/nope\.md"):
        push_module.read_local_state(repo)


@pytest.fixture(autouse=True)
def credentials(tmp_path_factory, monkeypatch):
    store = tmp_path_factory.mktemp("credentials") / "credentials.toml"
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", store)
    base_module.save_token("http://localhost:4321", "test-token")


def test_push_with_a_bad_link_sends_no_request_and_exits_nonzero(tmp_path, monkeypatch):
    repo = _repo(tmp_path, _calendar("[Slides](resources/w03/nope.md)"))
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        return httpx.Response(500)

    monkeypatch.setattr(
        push_module,
        "get_client",
        lambda base_url=None: httpx.Client(
            base_url=base_url or "http://localhost:4321",
            transport=httpx.MockTransport(handler),
        ),
    )
    result = CliRunner().invoke(app, ["push", str(repo)])
    assert result.exit_code != 0
    assert "nope.md" in result.output
    assert calls == []


def _read_calendar_events_body(repo: Path):
    """The `description` the course's first lesson would be pushed with."""
    local = push_module.read_local_state(repo)
    return {event.title: event.description for event in local.events}


def test_read_local_state_rewrites_resource_links_in_event_descriptions(tmp_path):
    repo = _repo(
        tmp_path, _calendar("Read [Slides](./resources/w03/recursion.md#page=2).")
    )
    descriptions = _read_calendar_events_body(repo)
    assert descriptions["First lesson"] == (
        "Read [Slides](/cs101/ada_2026-1/resources/w03-recursion#page=2)."
    )


def test_read_local_state_does_not_touch_calendar_md(tmp_path):
    text = _calendar("[Slides](resources/w03/recursion.md)")
    repo = _repo(tmp_path, text)
    push_module.read_local_state(repo)
    assert (repo / "calendar.md").read_text(encoding="utf-8") == text


def _install_recording_server(monkeypatch):
    """A fresh server that records every request in order, bodies included."""
    from test_cli_push import _fresh_server_handler

    calls: list[tuple[str, str, dict | None]] = []
    inner = _fresh_server_handler([])

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        return inner(request)

    monkeypatch.setattr(
        push_module,
        "get_client",
        lambda base_url=None: httpx.Client(
            base_url=base_url or "http://localhost:4321",
            transport=httpx.MockTransport(handler),
        ),
    )
    return calls


def test_push_sends_the_rewritten_description_and_leaves_calendar_md_alone(
    tmp_path, monkeypatch
):
    text = _calendar("Read [Slides](resources/w03/recursion.md).")
    repo = _repo(tmp_path, text)
    calls = _install_recording_server(monkeypatch)

    result = CliRunner().invoke(app, ["push", str(repo)])

    assert result.exit_code == 0, result.output
    [body] = [
        body
        for method, path, body in calls
        if method == "PUT"
        and path.endswith("/calendar-event")
        and body["title"] == "First lesson"
    ]
    assert body["description"] == (
        "Read [Slides](/cs101/ada_2026-1/resources/w03-recursion)."
    )
    assert (repo / "calendar.md").read_text(encoding="utf-8") == text


#
# R8: calendar ops come before resource ops
#
def _kinds(ops: list[PushOp]) -> list[str]:
    return [type(op).__name__ for op in ops]


def test_plan_orders_every_calendar_op_before_any_resource_op():
    resource = _resource("resources/a.md")
    local = LocalState(
        discipline="cs101",
        course="ada_2026-1",
        description="d",
        start=date(2026, 1, 1),
        end=date(2026, 6, 1),
        events=(_event(1, "mon", "x"),),
        resources=(resource,),
    )
    server = ServerState(
        resources={"stale": "ref"},
        calendar_events={(9, "mon"): ServerEvent(ref="r", kind="REGULAR")},
    )
    ops = list(plan_push(local, server))
    kinds = _kinds(ops)
    for calendar_op in (UpsertCalendarEvent, DeleteCalendarEvent):
        assert calendar_op.__name__ in kinds
    for resource_op in (UpsertResource, DeleteResource):
        assert resource_op.__name__ in kinds
    calendar_idx = [
        i
        for i, op in enumerate(ops)
        if isinstance(op, UpsertCalendarEvent | DeleteCalendarEvent)
    ]
    resource_idx = [
        i for i, op in enumerate(ops) if isinstance(op, UpsertResource | DeleteResource)
    ]
    assert max(calendar_idx) < min(resource_idx)


def test_push_sends_calendar_requests_before_resource_requests(tmp_path, monkeypatch):
    repo = _repo(tmp_path, _calendar("[Slides](resources/w03/recursion.md)"))
    calls = _install_recording_server(monkeypatch)

    result = CliRunner().invoke(app, ["push", str(repo)])

    assert result.exit_code == 0, result.output
    writes = [path for method, path, _ in calls if method == "PUT"]
    last_calendar = max(
        i
        for i, path in enumerate(writes)
        if path.endswith(("/calendar-event", "/time-slot"))
    )
    first_resource = min(
        i for i, path in enumerate(writes) if path.endswith("/resource")
    )
    assert last_calendar < first_resource
