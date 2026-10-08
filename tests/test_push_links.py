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


#
# Markdown code is not parsed for links
#
CODE_SPANS = [
    pytest.param("```\n[x](resources/a.pdf)\n```", id="backtick-fence"),
    pytest.param("~~~\n[x](resources/a.pdf)\n~~~", id="tilde-fence"),
    pytest.param("```md\n[x](resources/a.pdf)\n```", id="fence-with-info-string"),
    pytest.param("````\n```\n[x](resources/a.pdf)\n```\n````", id="nested-fence"),
    pytest.param("Use `[x](resources/a.pdf)` here.", id="inline-span"),
    pytest.param("Use ``[x](resources/a.pdf)`` here.", id="double-backtick-span"),
]


@pytest.mark.parametrize("markdown", CODE_SPANS)
def test_links_inside_code_are_not_extracted(markdown):
    assert extract_resource_links(markdown) == ()


@pytest.mark.parametrize("markdown", CODE_SPANS)
def test_links_inside_code_are_neither_attached_nor_an_error(markdown):
    resource = _resource("resources/a.pdf")
    other = _resource("resources/b.pdf")
    [event] = [_event(1, "mon", markdown)]
    # `resources/a.pdf` is not even among the resources: no error either.
    assert attach_resources([event], [other], ROOT) == (other,)
    assert attach_resources([event], [resource], ROOT) == (resource,)


@pytest.mark.parametrize("markdown", CODE_SPANS)
def test_links_inside_code_are_not_rewritten(markdown):
    targets = {PurePosixPath("resources/a.pdf"): "/d/c/resources/a"}
    assert rewrite_resource_links(markdown, targets) == markdown


def test_a_real_link_next_to_code_is_still_extracted_and_rewritten():
    markdown = (
        "```\n[x](resources/code.pdf)\n```\n"
        "Real [A](resources/a.pdf), code `[x](resources/code.pdf)`.\n"
        "~~~\n[x](resources/code.pdf)\n~~~\n"
        "After [B](resources/b.pdf)."
    )
    assert extract_resource_links(markdown) == (
        PurePosixPath("resources/a.pdf"),
        PurePosixPath("resources/b.pdf"),
    )
    targets = {
        PurePosixPath("resources/a.pdf"): "/d/c/resources/a",
        PurePosixPath("resources/b.pdf"): "/d/c/resources/b",
        PurePosixPath("resources/code.pdf"): "/d/c/resources/code",
    }
    assert rewrite_resource_links(markdown, targets) == (
        "```\n[x](resources/code.pdf)\n```\n"
        "Real [A](/d/c/resources/a), code `[x](resources/code.pdf)`.\n"
        "~~~\n[x](resources/code.pdf)\n~~~\n"
        "After [B](/d/c/resources/b)."
    )


def test_target_with_balanced_parentheses_is_one_link():
    assert extract_resource_links("[x](resources/a(1).pdf)") == (
        PurePosixPath("resources/a(1).pdf"),
    )


def test_balanced_parentheses_target_attaches_to_that_resource():
    events = [_event(1, "mon", "See [x](resources/a(1).pdf).")]
    [result] = attach_resources(events, [_resource("resources/a(1).pdf")], ROOT)
    assert result.event == EventKey(week=1, time_slot="mon")


def test_balanced_parentheses_target_is_rewritten_whole():
    targets = {PurePosixPath("resources/a(1).pdf"): "/d/c/resources/a-1"}
    assert (
        rewrite_resource_links("See [x](resources/a(1).pdf) now.", targets)
        == "See [x](/d/c/resources/a-1) now."
    )


ESCAPED = r"\[x\](resources/a.pdf)"


def test_escaped_brackets_are_not_a_link():
    assert extract_resource_links(ESCAPED) == ()


def test_escaped_brackets_are_not_attached_or_rewritten():
    resource = _resource("resources/a.pdf")
    assert attach_resources([_event(1, "mon", ESCAPED)], [resource], ROOT) == (
        resource,
    )
    targets = {PurePosixPath("resources/a.pdf"): "/d/c/resources/a"}
    assert rewrite_resource_links(ESCAPED, targets) == ESCAPED


#
# Reference-style links
#
REFERENCE_FORMS = [
    pytest.param("[Slides][s]", id="full"),
    pytest.param("[s][]", id="collapsed"),
    pytest.param("[s]", id="shortcut"),
]


def _with_definition(use: str, definition: str = "[s]: resources/w03/slides.pdf"):
    return f"Read {use} today.\n\n{definition}\n"


@pytest.mark.parametrize("use", REFERENCE_FORMS)
def test_reference_link_is_extracted_through_its_definition(use):
    assert extract_resource_links(_with_definition(use)) == (
        PurePosixPath("resources/w03/slides.pdf"),
    )


@pytest.mark.parametrize(
    "definition",
    [
        "[s]: <resources/w03/slides.pdf>",
        '[s]: resources/w03/slides.pdf "Slides"',
        "[s]: <resources/w03/slides.pdf> 'Slides'",
        "[s]: ./resources/w03/slides.pdf (Slides)",
        "[s]: resources/w03/slides.pdf#page=2",
    ],
)
def test_reference_definition_may_use_angle_brackets_title_and_dot_slash(definition):
    markdown = _with_definition("[Slides][s]", definition)
    assert extract_resource_links(markdown) == (
        PurePosixPath("resources/w03/slides.pdf"),
    )


@pytest.mark.parametrize("use", REFERENCE_FORMS)
def test_reference_link_attaches_the_resource(use):
    events = [_event(4, "wed", _with_definition(use))]
    [result] = attach_resources(events, [_resource("resources/w03/slides.pdf")], ROOT)
    assert result.event == EventKey(week=4, time_slot="wed")


def test_reference_link_to_a_missing_resource_is_an_error():
    events = [_event(1, "mon", _with_definition("[Slides][s]"))]
    with pytest.raises(ResourceLinkError, match=r"resources/w03/slides\.pdf"):
        attach_resources(events, [_resource("resources/other.pdf")], ROOT)


def test_reference_link_from_two_lessons_is_an_error():
    events = [
        _event(1, "mon", _with_definition("[Slides][s]"), title="Intro"),
        _event(2, "tue", "Again [s].\n\n[s]: resources/w03/slides.pdf\n", "Later"),
    ]
    with pytest.raises(ResourceLinkError, match=r"resources/w03/slides\.pdf"):
        attach_resources(events, [_resource("resources/w03/slides.pdf")], ROOT)


def test_reference_and_inline_links_to_one_resource_in_one_lesson_are_fine():
    description = "[A](resources/a.pdf) and [B][b]\n\n[b]: resources/a.pdf\n"
    [result] = attach_resources(
        [_event(1, "mon", description)], [_resource("resources/a.pdf")], ROOT
    )
    assert result.event == EventKey(week=1, time_slot="mon")


def test_bracketed_text_without_a_definition_is_not_a_link():
    markdown = "A [Slides][s] and [t] and [u][] with no definitions."
    assert extract_resource_links(markdown) == ()
    resource = _resource("resources/a.pdf")
    assert attach_resources([_event(1, "mon", markdown)], [resource], ROOT) == (
        resource,
    )


def test_reference_definition_to_something_else_is_ignored():
    markdown = (
        "[A][a] [B][b]\n\n[a]: https://example.com/resources/x.pdf\n[b]: docs/x.pdf\n"
    )
    assert extract_resource_links(markdown) == ()
    assert rewrite_resource_links(markdown, URLS) == markdown


@pytest.mark.parametrize(
    "definition, expected",
    [
        (
            "[s]: resources/w03/recursion.md",
            "[s]: /cs101/ada_2026-1/resources/w03-recursion",
        ),
        (
            "[s]: ./resources/w03/recursion.md",
            "[s]: /cs101/ada_2026-1/resources/w03-recursion",
        ),
        (
            "[s]: <resources/w03/recursion.md>",
            "[s]: </cs101/ada_2026-1/resources/w03-recursion>",
        ),
        (
            '[s]: resources/w03/recursion.md "Slides"',
            '[s]: /cs101/ada_2026-1/resources/w03-recursion "Slides"',
        ),
        (
            "[s]: resources/w03/recursion.md#page=2",
            "[s]: /cs101/ada_2026-1/resources/w03-recursion#page=2",
        ),
    ],
)
def test_rewrite_changes_the_definition_target_and_keeps_the_rest(definition, expected):
    markdown = f"See [Slides][s].\n\n{definition}\n"
    assert rewrite_resource_links(markdown, URLS) == f"See [Slides][s].\n\n{expected}\n"


@pytest.mark.parametrize("use", REFERENCE_FORMS)
def test_rewrite_leaves_the_reference_in_the_text_alone(use):
    markdown = _with_definition(use, "[s]: resources/w03/recursion.md")
    assert rewrite_resource_links(markdown, URLS) == (
        f"Read {use} today.\n\n[s]: /cs101/ada_2026-1/resources/w03-recursion\n"
    )


def test_rewrite_event_links_rewrites_reference_definitions():
    events = [_event(1, "mon", "Read [Slides][s].\n\n[s]: resources/a.md\n")]
    [event] = rewrite_event_links(events, [_resource("resources/a.md")], ROOT, "d", "c")
    assert event.description == "Read [Slides][s].\n\n[s]: /d/c/resources/a\n"


def test_reference_definition_inside_a_fence_is_not_a_definition():
    markdown = "See [Slides][s].\n\n```\n[s]: resources/a.pdf\n```\n"
    assert extract_resource_links(markdown) == ()
    targets = {PurePosixPath("resources/a.pdf"): "/d/c/resources/a"}
    assert rewrite_resource_links(markdown, targets) == markdown


#
# The skip decision compares the server's event key
#
def _plan_resources(resource: ResourceFile, server: ServerState) -> list[PushOp]:
    local = LocalState(
        discipline="cs101",
        course="ada_2026-1",
        description="d",
        start=date(2026, 1, 1),
        end=date(2026, 6, 1),
        resources=(resource,),
    )
    return [op for op in plan_push(local, server) if isinstance(op, UpsertResource)]


def _attached(rel: str = "resources/a.md") -> ResourceFile:
    [resource] = attach_resources(
        [_event(1, "mon", f"[A]({rel})")], [_resource(rel)], ROOT
    )
    return resource


KEY = EventKey(week=1, time_slot="mon")


def test_resource_with_matching_ref_and_event_is_skipped():
    resource = _attached()
    server = ServerState(
        resources={resource.slug: resource.ref},
        resource_events={resource.slug: KEY},
    )
    assert _plan_resources(resource, server) == []


@pytest.mark.parametrize(
    "server_event",
    [
        pytest.param(None, id="fell-back-to-general"),
        pytest.param(EventKey(week=2, time_slot="mon"), id="other-week"),
        pytest.param(EventKey(week=1, time_slot="tue"), id="other-slot"),
    ],
)
def test_resource_is_upserted_when_the_server_event_differs_despite_equal_ref(
    server_event,
):
    resource = _attached()
    server = ServerState(
        resources={resource.slug: resource.ref},
        resource_events={resource.slug: server_event},
    )
    [op] = _plan_resources(resource, server)
    assert (op.slug, op.event) == (resource.slug, KEY)


def test_resource_missing_from_server_events_counts_as_having_no_event():
    resource = _attached()
    server = ServerState(resources={resource.slug: resource.ref})
    [op] = _plan_resources(resource, server)
    assert op.event == KEY


def test_unattached_resource_is_skipped_when_the_server_has_no_event_either():
    resource = _resource("resources/a.md")
    for events in ({}, {resource.slug: None}):
        server = ServerState(
            resources={resource.slug: resource.ref}, resource_events=events
        )
        assert _plan_resources(resource, server) == []


def test_unattached_resource_is_upserted_when_the_server_still_has_an_event():
    resource = _resource("resources/a.md")
    server = ServerState(
        resources={resource.slug: resource.ref},
        resource_events={resource.slug: KEY},
    )
    [op] = _plan_resources(resource, server)
    assert op.event is None


def _server_resource_json(slug: str, rev: str, event: dict | None) -> dict:
    return {
        "slug": slug,
        "title": slug,
        "description": None,
        "data": {"type": "MD", "content": "body"},
        "event": event,
        "rev": rev,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


def test_fetch_server_state_reads_each_resource_s_event_key():
    from test_cli_push import _course_json

    from codehood.push.run import fetch_server_state

    listing = [
        _server_resource_json("a", "ra", {"week": 3, "timeSlot": "tue"}),
        _server_resource_json("b", "rb", None),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/resource"):
            return httpx.Response(200, json=listing)
        if request.url.path.endswith(("/question", "/time-slot")):
            return httpx.Response(200, json=[])
        if request.url.path.endswith(("/calendar-event", "/grade-column")):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_course_json())

    client = httpx.Client(
        base_url="http://localhost:4321", transport=httpx.MockTransport(handler)
    )
    state = fetch_server_state("cs101", "ada_2026-1", client)
    assert state.resources == {"a": "ra", "b": "rb"}
    assert state.resource_events.get("a") == EventKey(week=3, time_slot="tue")
    assert state.resource_events.get("b") is None


def test_dry_run_plans_the_resource_whose_server_event_was_lost(tmp_path, monkeypatch):
    from test_cli_push import _calendar_defaults, _course_json

    repo = _repo(tmp_path, _calendar("[Slides](resources/w03/recursion.md)"))
    [local] = push_module.read_local_state(repo).resources

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            raise AssertionError(f"--dry-run made a write: {request.url}")
        path = request.url.path
        if path.endswith("/resource"):
            return httpx.Response(
                200, json=[_server_resource_json(local.slug, local.ref, None)]
            )
        if path.endswith(("/question", "/grade-column")):
            return httpx.Response(200, json=[])
        if (response := _calendar_defaults(request)) is not None:
            return response
        return httpx.Response(200, json=_course_json())

    monkeypatch.setattr(
        push_module,
        "get_client",
        lambda base_url=None: httpx.Client(
            base_url=base_url or "http://localhost:4321",
            transport=httpx.MockTransport(handler),
        ),
    )
    result = CliRunner().invoke(app, ["push", str(repo), "--dry-run"])

    assert result.exit_code == 0, result.output
    planned = [
        line for line in result.output.splitlines() if line.startswith("planned")
    ]
    assert any(local.slug in line and "resource" in line for line in planned), planned
