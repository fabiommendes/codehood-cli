"""
Tests for repositories in the plan, the shell and the plan line (batch 2):
`plan_repositories`/`plan_push`, `run_upsert_repository` and friends,
`run_plan` with a `RepositoryApi`, and `describe_repository`.

The server is a fake `RepositoryApi`: one method per endpoint, each
recording the call it got.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx
import mdq
import pytest

from codehood.cli.push import describe, describe_repository
from codehood.push.calendar import Duration, Event, TimeOfDay, TimeSlot
from codehood.push.plan import (
    DeleteRepository,
    LocalState,
    ServerState,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertQuestion,
    UpsertRepository,
    UpsertResource,
    UpsertTimeSlot,
    WarnRepositoryKept,
    plan_push,
    plan_repositories,
)
from codehood.push.question import QuestionFile, question_version
from codehood.push.repository import (
    MAX_FILE_BYTES,
    RepositoryEntry,
    RepositoryTree,
)
from codehood.push.resource import MdData, ResourceFile, content_ref
from codehood.push.run import (
    OpResult,
    run_delete_repository,
    run_plan,
    run_upsert_repository,
    run_warn_repository_kept,
)

MB = 1024 * 1024
DISCIPLINE = "cs101"
COURSE = "ada_2026-1"
QUESTION = "---\ntitle: Q\n---\n\nWhat is 2 + 2?\n\n- [ ] 3\n- [*] 4\n- [ ] 5\n"


def _entry(path: str, size: int = 10, *, sha256: str | None = None) -> RepositoryEntry:
    return RepositoryEntry(
        path=path,
        mode="100644",
        sha256=sha256 or path.encode().hex().ljust(64, "0")[:64],
        git_sha="1" * 40,
        size=size,
        source=Path("/nowhere") / path,
    )


def _tree(
    slug: str = "lab1", *entries: RepositoryEntry, tree_sha: str | None = None
) -> RepositoryTree:
    return RepositoryTree(
        slug=slug,
        entries=entries or (_entry("a.py"),),
        tree_sha=tree_sha or (slug.encode().hex() * 40)[:40],
    )


def _local(*trees: RepositoryTree, **kwargs) -> LocalState:
    return LocalState(
        discipline=DISCIPLINE,
        course=COURSE,
        description="d",
        start=date(2026, 1, 1),
        end=date(2026, 6, 1),
        repositories=trees,
        **kwargs,
    )


def _server(**repositories: str | None) -> ServerState:
    return ServerState(course_exists=True, repositories=repositories)


@dataclass
class FakeApi:
    """A `RepositoryApi` that records calls and can be told to fail a step."""

    absent: set[str] | None = None
    fail_on: str | None = None
    head: str | None = "abc1234"
    calls: list[tuple[str, object]] = field(default_factory=list)

    def list_trees(self) -> Mapping[str, str | None]:
        self.calls.append(("list_trees", None))
        return {}

    def upsert(self, slug: str) -> None:
        self._step("upsert", slug)

    def missing(self, hashes: Sequence[str]) -> list[str]:
        self._step("missing", list(hashes))
        if self.absent is None:
            return list(hashes)
        return [h for h in hashes if h in self.absent]

    def upload(self, slug: str, entries: Sequence[RepositoryEntry]) -> None:
        self._step("upload", (slug, [e.path for e in entries]))

    def commit(
        self, slug: str, entries: Sequence[RepositoryEntry], message: str | None
    ) -> str | None:
        self._step("commit", (slug, [e.path for e in entries], message))
        return self.head

    def delete(self, slug: str) -> None:
        self._step("delete", slug)

    def _step(self, name: str, arg: object) -> None:
        self.calls.append((name, arg))
        if name == self.fail_on:
            request = httpx.Request("POST", "http://test/x")
            raise httpx.HTTPStatusError(
                "boom", request=request, response=httpx.Response(500, request=request)
            )

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


#
# plan_repositories
#
def test_a_repository_the_server_lacks_is_upserted():
    tree = _tree("lab1")
    ops = list(plan_repositories(_local(tree), _server()))
    assert ops == [UpsertRepository(tree=tree, message=None)]


def test_a_repository_with_another_tree_is_upserted():
    tree = _tree("lab1")
    ops = list(plan_repositories(_local(tree), _server(lab1="f" * 40)))
    assert ops == [UpsertRepository(tree=tree, message=None)]


def test_a_repository_before_its_first_commit_is_upserted():
    tree = _tree("lab1")
    ops = list(plan_repositories(_local(tree), _server(lab1=None)))
    assert ops == [UpsertRepository(tree=tree, message=None)]


def test_a_repository_with_the_same_tree_plans_nothing():
    tree = _tree("lab1")
    assert list(plan_repositories(_local(tree), _server(lab1=tree.tree_sha))) == []


def test_the_message_travels_with_every_upsert():
    trees = (_tree("lab1"), _tree("lab2"))
    ops = list(plan_repositories(_local(*trees), _server(), message="week 3"))
    assert [op.message for op in ops if isinstance(op, UpsertRepository)] == [
        "week 3",
        "week 3",
    ]


def test_repositories_are_planned_in_slug_order():
    ops = list(plan_repositories(_local(_tree("a"), _tree("b"), _tree("c")), _server()))
    assert [op.tree.slug for op in ops if isinstance(op, UpsertRepository)] == [
        "a",
        "b",
        "c",
    ]


def test_a_repository_whose_folder_is_gone_is_kept_with_a_warning():
    ops = list(plan_repositories(_local(), _server(old="e" * 40)))
    assert ops == [WarnRepositoryKept(slug="old")]


def test_a_repository_never_committed_whose_folder_is_gone_is_also_kept():
    assert list(plan_repositories(_local(), _server(old=None))) == [
        WarnRepositoryKept(slug="old")
    ]


def test_drop_repositories_deletes_a_repository_whose_folder_is_gone():
    ops = list(
        plan_repositories(_local(), _server(old="e" * 40), drop_repositories=True)
    )
    assert ops == [DeleteRepository(slug="old")]


def test_drop_repositories_leaves_a_present_repository_alone():
    tree = _tree("lab1")
    ops = list(
        plan_repositories(
            _local(tree), _server(lab1=tree.tree_sha), drop_repositories=True
        )
    )
    assert ops == []


def test_a_second_plan_against_the_state_the_first_wrote_plans_no_repository_op():
    trees = (_tree("lab1"), _tree("lab2"))
    server = _server(**{tree.slug: tree.tree_sha for tree in trees})
    assert list(plan_repositories(_local(*trees), server)) == []


#
# plan_push
#
def test_plan_push_carries_the_repository_ops():
    tree = _tree("lab1")
    ops = list(plan_push(_local(tree), _server(), message="m"))
    assert UpsertRepository(tree=tree, message="m") in ops


def test_plan_push_drops_repositories_only_on_request():
    local, server = _local(), _server(old="e" * 40)
    assert WarnRepositoryKept(slug="old") in plan_push(local, server)
    assert DeleteRepository(slug="old") in plan_push(
        local, server, drop_repositories=True
    )


def test_plan_push_orders_course_repositories_calendar_resources_questions():
    slot = TimeSlot(
        slug="mon",
        day="MONDAY",
        start=TimeOfDay(hour=14, minute=0),
        duration=Duration(hours=2, minutes=0),
    )
    data = MdData(content="body")
    resource = ResourceFile(
        slug="r",
        title="r",
        description=None,
        data=data,
        ref=content_ref("resources/r.md", None, data),
        path=Path("resources/r.md"),
    )
    question = QuestionFile(
        slug="q",
        version=question_version(QUESTION.encode()),
        question=mdq.parse(QUESTION, kind="question", ids="fill"),
        path=Path("questions/q.md"),
    )
    local = _local(
        _tree("lab1"),
        slots=(slot,),
        events=(Event(week=0, time_slot="mon", title="Intro"),),
        resources=(resource,),
        questions=(question,),
    )
    kinds = [
        type(op)
        for op in plan_push(local, _server())
        if isinstance(
            op,
            UpsertCourse
            | UpsertRepository
            | UpsertTimeSlot
            | UpsertCalendarEvent
            | UpsertResource
            | UpsertQuestion,
        )
    ]
    assert kinds == [
        UpsertCourse,
        UpsertRepository,
        UpsertTimeSlot,
        UpsertCalendarEvent,
        UpsertResource,
        UpsertQuestion,
    ]


def test_plan_push_with_matching_trees_yields_only_the_course():
    tree = _tree("lab1")
    ops = list(plan_push(_local(tree), _server(lab1=tree.tree_sha)))
    assert [type(op) for op in ops] == [UpsertCourse]


#
# run_upsert_repository
#
def test_upsert_runs_put_then_missing_then_files_then_commit():
    api = FakeApi()
    tree = _tree("lab1", _entry("a.py"), _entry("b.py"))
    result = run_upsert_repository(UpsertRepository(tree=tree, message="m"), api)
    assert result.ok is True
    assert api.names == ["upsert", "missing", "upload", "commit"]
    assert api.calls[0] == ("upsert", "lab1")


def test_upsert_asks_about_the_sha256_of_every_file():
    api = FakeApi()
    entries = (_entry("a.py", sha256="a" * 64), _entry("b.py", sha256="b" * 64))
    run_upsert_repository(UpsertRepository(tree=_tree("lab1", *entries)), api)
    [(_, asked)] = [call for call in api.calls if call[0] == "missing"]
    assert sorted(asked) == ["a" * 64, "b" * 64]


def test_upsert_uploads_only_the_missing_files():
    api = FakeApi(absent={"b" * 64})
    entries = (_entry("a.py", sha256="a" * 64), _entry("b.py", sha256="b" * 64))
    run_upsert_repository(UpsertRepository(tree=_tree("lab1", *entries)), api)
    assert [call for call in api.calls if call[0] == "upload"] == [
        ("upload", ("lab1", ["b.py"]))
    ]


def test_upsert_commits_every_file_even_when_none_was_uploaded():
    api = FakeApi(absent=set())
    entries = (_entry("a.py"), _entry("b.py"))
    result = run_upsert_repository(
        UpsertRepository(tree=_tree("lab1", *entries), message="week 3"), api
    )
    assert result.ok is True
    assert "upload" not in api.names
    assert api.calls[-1] == ("commit", ("lab1", ["a.py", "b.py"], "week 3"))


def test_upsert_commits_with_the_message_of_the_push():
    api = FakeApi()
    run_upsert_repository(UpsertRepository(tree=_tree("lab1"), message="fix lab"), api)
    assert api.calls[-1][1][2] == "fix lab"  # type: ignore[index]


def test_upsert_without_a_message_commits_with_none():
    api = FakeApi()
    run_upsert_repository(UpsertRepository(tree=_tree("lab1")), api)
    assert api.calls[-1][1][2] is None  # type: ignore[index]


def test_upsert_uploads_in_batches_of_at_most_sixteen_megabytes():
    api = FakeApi()
    entries = tuple(_entry(f"f{i}.bin", 6 * MB, sha256=f"{i}" * 64) for i in range(3))
    run_upsert_repository(UpsertRepository(tree=_tree("lab1", *entries)), api)
    uploads = [call[1][1] for call in api.calls if call[0] == "upload"]  # type: ignore[index]
    assert uploads == [["f0.bin", "f1.bin"], ["f2.bin"]]


def test_upsert_sends_a_file_of_exactly_the_limit_in_its_own_batch():
    api = FakeApi()
    entries = (
        _entry("a", 1, sha256="a" * 64),
        _entry("big", MAX_FILE_BYTES, sha256="b" * 64),
    )
    run_upsert_repository(UpsertRepository(tree=_tree("lab1", *entries)), api)
    uploads = [call[1][1] for call in api.calls if call[0] == "upload"]  # type: ignore[index]
    assert uploads == [["a"], ["big"]]


@pytest.mark.parametrize("step", ["upsert", "missing", "upload", "commit"])
def test_upsert_stops_at_the_first_failed_step(step):
    api = FakeApi(fail_on=step)
    result = run_upsert_repository(UpsertRepository(tree=_tree("lab1")), api)
    order = ["upsert", "missing", "upload", "commit"]
    assert result.ok is False
    assert api.names == order[: order.index(step) + 1]


def test_upsert_failure_does_not_raise_and_says_why():
    api = FakeApi(fail_on="commit")
    result = run_upsert_repository(UpsertRepository(tree=_tree("lab1")), api)
    assert isinstance(result, OpResult)
    assert "500" in result.message


def test_upsert_reports_the_new_head():
    api = FakeApi(head="abc1234")
    result = run_upsert_repository(UpsertRepository(tree=_tree("lab1")), api)
    assert "abc1234" in result.message


#
# warn / delete / run_plan
#
def test_a_kept_warning_is_not_a_failure_and_names_the_slug():
    result = run_warn_repository_kept(WarnRepositoryKept(slug="old"))
    assert result.ok is True
    assert "old" in result.message


def test_delete_calls_the_api():
    api = FakeApi()
    result = run_delete_repository(DeleteRepository(slug="old"), api)
    assert result.ok is True
    assert api.calls == [("delete", "old")]


def test_a_refused_delete_is_a_failed_result():
    api = FakeApi(fail_on="delete")
    result = run_delete_repository(DeleteRepository(slug="old"), api)
    assert result.ok is False
    assert "500" in result.message


def _no_http_client() -> httpx.Client:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return httpx.Client(base_url="http://test", transport=httpx.MockTransport(refuse))


def test_run_plan_sends_repository_ops_through_the_given_api():
    api = FakeApi()
    ops = [
        UpsertRepository(tree=_tree("lab1"), message="m"),
        WarnRepositoryKept(slug="kept"),
        DeleteRepository(slug="old"),
    ]
    results = list(
        run_plan(
            ops,
            discipline=DISCIPLINE,
            course=COURSE,
            client=_no_http_client(),
            repositories=api,
        )
    )
    assert [r.ok for r in results] == [True, True, True]
    assert [r.op for r in results] == ops
    assert api.names == ["upsert", "missing", "upload", "commit", "delete"]


def test_run_plan_keeps_going_after_a_failed_repository():
    api = FakeApi(fail_on="upsert")
    ops = [
        UpsertRepository(tree=_tree("lab1")),
        WarnRepositoryKept(slug="kept"),
    ]
    results = list(
        run_plan(
            ops,
            discipline=DISCIPLINE,
            course=COURSE,
            client=_no_http_client(),
            repositories=api,
        )
    )
    assert [r.ok for r in results] == [False, True]


#
# describe_repository
#
def test_the_plan_line_for_an_upsert():
    tree = RepositoryTree(
        slug="lab1",
        entries=(
            _entry("a", 400_000),
            _entry("b", 400_000),
            _entry("c", 400_000),
        ),
        tree_sha="4f2a9c1" + "0" * 33,
    )
    line = describe_repository(UpsertRepository(tree=tree))
    assert line == "repository lab1: 3 files (1.2 MB), commit 4f2a9c1"


def test_the_plan_line_uses_the_singular_for_one_file():
    tree = RepositoryTree(
        slug="lab1", entries=(_entry("a", 400_000),), tree_sha="4f2a9c1" + "0" * 33
    )
    assert describe_repository(UpsertRepository(tree=tree)).startswith(
        "repository lab1: 1 file ("
    )


def test_the_kept_line_names_the_flag():
    line = describe_repository(WarnRepositoryKept(slug="old"))
    assert "old" in line
    assert "--drop-repositories" in line


def test_the_delete_line_names_the_slug():
    assert "old" in describe_repository(DeleteRepository(slug="old"))


def test_describe_dispatches_repository_ops():
    tree = _tree("lab1", tree_sha="4f2a9c1" + "0" * 33)
    assert describe(UpsertRepository(tree=tree)) == describe_repository(
        UpsertRepository(tree=tree)
    )
