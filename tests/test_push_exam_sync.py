"""
Tests for exams in the three-way sync: the projection (sync R3), the plan for
an exam (status guard, server-set `duration`/`scheduledAt`, `InvalidExam`),
and the order of the writes.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import mdq
from hypothesis import given
from hypothesis import strategies as st
from pydantic import JsonValue

from codehood.api import generated
from codehood.models.repo import CourseKey
from codehood.push.base import COLLECTIONS, BaseEntry, BaseState, load_base, save_base
from codehood.push.exam import ExamFile, InvalidExam, exam_rev
from codehood.push.plan import (
    DeleteExam,
    DeleteQuestion,
    IgnoredExamPolicy,
    KeptExamLive,
    LocalState,
    Plan,
    Rejected,
    ServerExam,
    ServerState,
    UpsertExam,
    UpsertQuestion,
    UpsertResource,
    course_ref,
    order_writes,
    plan_sync,
    write_rank,
)
from codehood.push.project import RemoteEntry, project_exam
from codehood.push.question import QuestionFile, question_version
from codehood.push.wire import Payload, course_payload, exam_payload, instant

KEY = CourseKey("cs101", "ada", "2026-1")
START, END = date(2026, 1, 1), date(2026, 6, 1)
STAMP = "2026-03-01T12:00:00.000Z"


#
# Helpers
#
def exam_file(slug: str = "mid", **changes) -> ExamFile:
    base = ExamFile(
        slug=slug,
        path=Path(f"exams/{slug}.md"),
        type="EXAM",
        status="SCHEDULED",
        title="Midterm",
        description=None,
        preamble="Read.",
        tags=("loops",),
        allow_code_run=None,
        questions=("q1",),
        duration={"hours": 2, "minutes": 0},
        scheduled_at="2026-03-15T14:00:00.000Z",
    )
    return replace(base, **changes)


def local_state(*exams: ExamFile | InvalidExam) -> LocalState:
    return LocalState(
        key=KEY, description="d", start=START, end=END, exams=tuple(exams)
    )


def course_entry() -> RemoteEntry:
    ref = course_ref("d", instant(START), instant(END))
    payload = course_payload(KEY, "d", START, END)
    return RemoteEntry(payload, rev=ref, updated_at=STAMP)


def server_exam(
    file: ExamFile, status: str = "SCHEDULED", **payload_changes: JsonValue
) -> ServerExam:
    payload = {**exam_payload(file), **payload_changes}
    entry = RemoteEntry(payload, rev=file.rev, updated_at=STAMP)
    return ServerExam(entry, status)  # type: ignore[arg-type]


def server_state(**exams: ServerExam) -> ServerState:
    return ServerState(
        course_exists=True,
        course=course_entry(),
        exams=exams,
    )


def base_of(server: ServerState) -> BaseState:
    from codehood.push.plan import COURSE_KEY

    course = server.course
    assert course is not None
    return BaseState(
        course={COURSE_KEY: BaseEntry(course.payload, course.rev, course.updated_at)},
        exams={
            slug: BaseEntry(exam.entry.payload, exam.entry.rev, exam.entry.updated_at)
            for slug, exam in server.exams.items()
        },
    )


def plan(local: LocalState, server: ServerState, base: BaseState | None = None) -> Plan:
    return plan_sync(local, base or base_of(server), server)


def exam_writes(result: Plan) -> list[UpsertExam | DeleteExam]:
    return [w for w in result.writes if isinstance(w, UpsertExam | DeleteExam)]


def quiet(result: Plan) -> bool:
    return not (
        result.writes
        or result.pulls
        or result.conflicts
        or result.other_cli
        or result.rejected
    )


def question_file(slug: str = "q1") -> QuestionFile:
    body = "---\ntitle: Q\n---\n\nWhat?\n\n- [ ] 3\n- [*] 4\n"
    return QuestionFile(
        slug=slug,
        version=question_version(body.encode()),
        question=mdq.parse(body, kind="question", ids="fill"),
        path=Path(f"questions/{slug}.md"),
    )


#
# Projection (sync R3)
#
def read_exam(payload: Payload, status: str = "SCHEDULED") -> generated.Exam:
    """
    What the server returns for an exam it stored from `payload`: the columns
    it fills itself, `null` for what the payload leaves out.
    """
    duration = payload.get("duration")
    questions = payload["questions"]
    assert isinstance(questions, list)
    return generated.Exam.model_validate(
        {
            "slug": payload["slug"],
            "type": payload["type"],
            "status": status,
            "title": payload["title"],
            "description": payload["description"],
            "preamble": payload["preamble"],
            "format": payload["format"],
            "scheduledAt": payload.get("scheduledAt"),
            "duration": duration,
            "extraTime": None,
            "allowCodeRun": payload["allowCodeRun"],
            "answerHistory": None,
            "gradesReleasedAt": None,
            "author": "ada",
            "rev": "v1:abc",
            "tags": sorted(payload["tags"]),  # type: ignore[type-var]
            "questions": questions,
            "createdAt": STAMP,
            "updatedAt": STAMP,
        }
    )


slug = st.from_regex(r"[a-z][a-z0-9-]{0,8}", fullmatch=True)
text = st.text(st.characters(min_codepoint=32, max_codepoint=0x2FF), max_size=12)


@st.composite
def exam_files(draw) -> ExamFile:
    minutes = draw(st.none() | st.integers(min_value=1, max_value=5000))
    return ExamFile(
        slug=draw(slug),
        path=Path("exams/x.md"),
        type=draw(st.sampled_from(["EXAM", "QUIZ", "PRACTICE"])),
        status=draw(st.sampled_from(["DRAFT", "SCHEDULED"])),
        title=draw(text.filter(bool)),
        description=draw(st.none() | text),
        preamble=draw(st.none() | text),
        tags=tuple(draw(st.lists(slug, max_size=3, unique=True))),
        allow_code_run=draw(st.none() | st.booleans()),
        questions=tuple(draw(st.lists(slug, max_size=4, unique=True))),
        duration=(
            None
            if minutes is None
            else {"hours": minutes // 60, "minutes": minutes % 60}
        ),
        scheduled_at=draw(
            st.none()
            | st.just("2026-03-15T14:00:00.000Z")
            | st.just("2027-01-01T00:00:00.000Z")
        ),
    )


@given(file=exam_files())
def test_projecting_what_the_server_reads_back_gives_the_payload(file):
    payload = exam_payload(file)

    assert project_exam(read_exam(payload)) == payload


def test_the_projection_drops_the_schedule_the_server_does_not_hold():
    file = exam_file(duration=None, scheduled_at=None)

    projected = project_exam(read_exam(exam_payload(file)))

    assert "duration" not in projected
    assert "scheduledAt" not in projected


def test_the_projection_never_pins_a_question_version():
    payload = exam_payload(exam_file())
    questions = [{"slug": "q1", "version": "md5:abc"}]
    read = read_exam({**payload, "questions": questions})

    assert project_exam(read)["questions"] == [{"slug": "q1", "version": None}]


#
# Plan
#
def test_a_new_exam_is_written_with_its_status_and_rev():
    file = exam_file()

    result = plan(local_state(file), server_state(), BaseState())

    (write,) = exam_writes(result)
    assert isinstance(write, UpsertExam)
    assert write.status == "SCHEDULED"
    assert write.rev == exam_rev(exam_payload(file))
    assert write.payload == exam_payload(file)
    (confirmation,) = [c for c in result.confirmations if c.write == write]
    assert confirmation.update.kind == "exam"
    assert confirmation.update.entry == BaseEntry(exam_payload(file))


def test_a_second_plan_right_after_a_push_plans_nothing():
    file = exam_file()
    server = server_state(mid=server_exam(file))

    result = plan(local_state(file), server)

    assert quiet(result)
    assert result.notices == ()


def test_an_edited_exam_is_written_again():
    file = exam_file()
    server = server_state(mid=server_exam(file))

    result = plan(local_state(replace(file, title="Final")), server)

    (write,) = exam_writes(result)
    assert isinstance(write, UpsertExam) and write.payload["title"] == "Final"


def test_a_duration_the_server_set_is_not_a_change():
    file = exam_file(duration=None, scheduled_at=None)
    server = server_state(
        mid=server_exam(
            file,
            duration={"hours": 3, "minutes": 0},
            scheduledAt="2026-05-01T10:00:00.000Z",
        )
    )
    base = base_of(server_state(mid=server_exam(file)))

    assert quiet(plan(local_state(file), server, base))


def test_a_duration_the_server_set_is_not_sent_blank_with_another_edit():
    file = exam_file(duration=None, scheduled_at=None)
    server = server_state(mid=server_exam(file, duration={"hours": 3, "minutes": 0}))
    base = base_of(server_state(mid=server_exam(file)))

    result = plan(local_state(replace(file, title="Final")), server, base)

    (write,) = exam_writes(result)
    assert isinstance(write, UpsertExam)
    assert "duration" not in write.payload
    assert "scheduledAt" not in write.payload


def test_removing_the_duration_from_the_file_does_not_blank_the_server():
    declared = exam_file(duration={"hours": 2, "minutes": 0})
    server = server_state(mid=server_exam(declared))

    result = plan(local_state(replace(declared, duration=None)), server)

    assert quiet(result)


def test_a_duration_the_file_declares_still_compares():
    file = exam_file(duration={"hours": 2, "minutes": 0})
    server = server_state(mid=server_exam(file, duration={"hours": 3, "minutes": 0}))
    base = base_of(server_state(mid=server_exam(file)))

    result = plan(local_state(file), server, base)

    assert exam_writes(result) == []
    assert [pull.fields for pull in result.pulls] == [("duration",)]


def test_an_ongoing_exam_keeps_its_status_and_the_push_says_so():
    file = exam_file()
    server = server_state(mid=server_exam(file, status="ONGOING"))

    result = plan(local_state(file), server)

    assert quiet(result)
    assert result.notices == (
        KeptExamLive("mid", "ONGOING", "SCHEDULED", Path("exams/mid.md")),
    )


def test_a_completed_exam_with_an_edit_is_written_at_its_status():
    file = exam_file()
    server = server_state(mid=server_exam(file, status="COMPLETED"))

    result = plan(local_state(replace(file, title="Typo fixed")), server)

    (write,) = exam_writes(result)
    assert isinstance(write, UpsertExam) and write.status == "COMPLETED"
    assert [n.status for n in result.notices if isinstance(n, KeptExamLive)] == [
        "COMPLETED"
    ]


def test_the_file_wins_below_ongoing_in_both_directions():
    scheduled = exam_file(status="SCHEDULED")
    server = server_state(mid=server_exam(scheduled, status="SCHEDULED"))
    base = base_of(server)
    draft = replace(scheduled, status="DRAFT", scheduled_at=None)

    down = plan(local_state(draft), server, base)
    (write,) = exam_writes(down)
    assert isinstance(write, UpsertExam) and write.status == "DRAFT"

    promoted = plan(
        local_state(scheduled), server_state(mid=server_exam(scheduled, status="DRAFT"))
    )
    (write,) = exam_writes(promoted)
    assert isinstance(write, UpsertExam) and write.status == "SCHEDULED"


def test_an_unresolved_include_keeps_the_server_copy():
    file = exam_file()
    server = server_state(mid=server_exam(file))
    invalid = InvalidExam(
        "mid", Path("exams/mid.md"), "include 'x' matches no question"
    )

    result = plan(local_state(invalid), server)

    assert exam_writes(result) == []
    assert result.rejected == (
        Rejected("mid", Path("exams/mid.md"), "include 'x' matches no question"),
    )


def test_an_invalid_exam_is_never_pruned_even_with_nothing_on_the_server_side_to_match():
    file = exam_file()
    server = server_state(mid=server_exam(file))

    result = plan(
        local_state(InvalidExam("mid", Path("exams/mid.md"), "broken")), server
    )

    assert not any(isinstance(w, DeleteExam) for w in result.writes)


def test_a_deleted_file_archives_its_exam():
    file = exam_file()
    server = server_state(mid=server_exam(file))

    result = plan(local_state(), server)

    assert exam_writes(result) == [DeleteExam("mid")]
    (confirmation,) = [
        c for c in result.confirmations if isinstance(c.write, DeleteExam)
    ]
    assert confirmation.update.entry is None


def test_a_deleted_file_does_not_archive_a_live_exam():
    file = exam_file()
    server = server_state(mid=server_exam(file, status="ONGOING"))

    result = plan(local_state(), server)

    assert exam_writes(result) == []
    assert result.notices == (KeptExamLive("mid", "ONGOING", None),)


def test_an_exam_made_on_the_server_is_not_pruned():
    file = exam_file()
    server = server_state(mid=server_exam(file))

    result = plan(local_state(), server, BaseState(course=base_of(server).course))

    assert exam_writes(result) == []


def test_fields_the_server_has_no_column_for_are_reported():
    file = exam_file(ignored=("penalty", "shuffle"))
    server = server_state(mid=server_exam(file))

    result = plan(local_state(file), server)

    assert quiet(result)
    assert result.notices == (
        IgnoredExamPolicy("mid", Path("exams/mid.md"), ("penalty", "shuffle")),
    )


#
# Inline questions and order
#
def test_inline_questions_are_pushed_before_the_exam_that_holds_them():
    inline = question_file("mid-a")
    file = exam_file(questions=("mid-a",), inline=(inline,))

    result = plan(local_state(file), server_state(), BaseState())

    assert [type(w) for w in result.writes if not isinstance(w, UpsertResource)][
        -2:
    ] == [
        UpsertQuestion,
        UpsertExam,
    ]
    ordered = order_writes(reversed(result.writes))
    kinds = [type(w) for w in ordered]
    assert kinds.index(UpsertQuestion) < kinds.index(UpsertExam)


def test_an_inline_question_already_on_the_server_is_not_pushed_again():
    from codehood.push.plan import ServerQuestion
    from codehood.push.wire import question_payload

    inline = question_file("mid-a")
    file = exam_file(questions=("mid-a",), inline=(inline,))
    entry = RemoteEntry(question_payload(inline), rev=inline.version, updated_at=STAMP)
    server = replace(
        server_state(mid=server_exam(file)),
        questions={"mid-a": ServerQuestion(inline.version, entry, "PUBLISHED")},
    )
    base = replace(
        base_of(server),
        questions={"mid-a": BaseEntry(entry.payload, entry.rev, entry.updated_at)},
    )

    assert quiet(plan(local_state(file), server, base))


def test_a_deleted_inline_question_is_pruned_after_the_exam_stops_holding_it():
    inline = question_file("mid-a")
    file = exam_file(questions=("mid-a",), inline=(inline,))
    from codehood.push.plan import ServerQuestion
    from codehood.push.wire import question_payload

    entry = RemoteEntry(question_payload(inline), rev=inline.version, updated_at=STAMP)
    server = replace(
        server_state(mid=server_exam(file)),
        questions={"mid-a": ServerQuestion(inline.version, entry, "PUBLISHED")},
    )
    base = replace(
        base_of(server),
        questions={"mid-a": BaseEntry(entry.payload, entry.rev, entry.updated_at)},
    )
    edited = replace(file, questions=(), inline=())

    result = plan(local_state(edited), server, base)

    kinds = [type(w) for w in order_writes(result.writes)]
    assert DeleteQuestion in kinds and UpsertExam in kinds
    assert kinds.index(DeleteQuestion) < kinds.index(UpsertExam)


def test_the_write_order_puts_exam_deletes_after_questions_and_upserts_last():
    writes = [
        UpsertExam("a", {}, "DRAFT", "v1:x", Path("a.md")),
        DeleteExam("b"),
        UpsertQuestion("q", "md5:x", question_file().question, Path("q.md")),
        DeleteQuestion("r"),
    ]

    ordered = order_writes(writes)

    assert [type(w) for w in ordered] == [
        UpsertQuestion,
        DeleteQuestion,
        DeleteExam,
        UpsertExam,
    ]
    assert write_rank(DeleteExam("x")) < write_rank(writes[0])


#
# Base
#
def test_the_exams_of_the_base_are_stored_in_their_own_collection(tmp_path):
    assert "exams" in COLLECTIONS
    state = BaseState(exams={"mid": BaseEntry({"slug": "mid"}, "v1:x", STAMP)})

    save_base(tmp_path, state)

    assert load_base(tmp_path).exams == state.exams


#
# Review fixes
#
def with_question(file: ExamFile, inline: QuestionFile, **exam_changes):
    """
    A server and a base that hold `file` and its inline question.
    """
    from codehood.push.plan import ServerQuestion
    from codehood.push.wire import question_payload

    entry = RemoteEntry(question_payload(inline), rev=inline.version, updated_at=STAMP)
    server = replace(
        server_state(mid=server_exam(file, **exam_changes)),
        questions={inline.slug: ServerQuestion(inline.version, entry, "PUBLISHED")},
    )
    base = replace(
        base_of(server),
        questions={inline.slug: BaseEntry(entry.payload, entry.rev, entry.updated_at)},
    )
    return server, base


def pruned(result: Plan) -> list[str]:
    return [w.slug for w in result.writes if isinstance(w, DeleteQuestion)]


def test_the_inline_questions_of_an_invalid_exam_are_not_pruned():
    inline = question_file("mid-a")
    file = exam_file(questions=("mid-a",), inline=(inline,))
    server, base = with_question(file, inline)
    invalid = InvalidExam("mid", Path("exams/mid.md"), "broken")

    result = plan(local_state(invalid), server, base)

    assert pruned(result) == []
    assert result.base_updates == ()
    assert result.rejected


def test_the_questions_of_a_live_exam_whose_file_is_gone_are_not_pruned():
    inline = question_file("mid-a")
    file = exam_file(questions=("mid-a",), inline=(inline,))
    server, base = with_question(file, inline, status="ONGOING")

    result = plan(local_state(), server, base)

    assert pruned(result) == []


def test_a_question_deleted_under_an_exam_that_includes_it_is_not_pruned():
    included = question_file("a")
    file = exam_file(questions=("a",))
    server, base = with_question(file, included)
    invalid = InvalidExam(
        "mid", Path("exams/mid.md"), "include 'a' matches no question"
    )

    assert pruned(plan(local_state(invalid), server, base)) == []


def test_a_kept_exam_does_not_stop_a_question_from_being_written():
    inline = question_file("mid-a")
    file = exam_file(questions=("mid-a",), inline=(inline,))
    server, base = with_question(file, inline)
    body = "---\ntitle: Q\n---\n\nWhat now?\n\n- [ ] 3\n- [*] 4\n"
    edited = replace(
        inline,
        version=question_version(body.encode()),
        question=mdq.parse(body, kind="question", ids="fill"),
    )
    invalid = InvalidExam("mid", Path("exams/mid.md"), "broken")
    local = replace(local_state(invalid), questions=(edited,))

    result = plan(local, server, base)

    assert [w.slug for w in result.writes if isinstance(w, UpsertQuestion)] == ["mid-a"]


def test_an_unrelated_question_is_still_pruned_next_to_a_kept_exam():
    inline = question_file("mid-a")
    other = question_file("other")
    file = exam_file(questions=("mid-a",), inline=(inline,))
    server, base = with_question(file, inline)
    server2, base2 = with_question(file, other)
    server = replace(server, questions={**server.questions, **server2.questions})
    base = replace(base, questions={**base.questions, **base2.questions})
    invalid = InvalidExam("mid", Path("exams/mid.md"), "broken")

    assert pruned(plan(local_state(invalid), server, base)) == ["other"]


def test_tags_that_are_not_alphabetical_converge():
    file = exam_file(tags=("b", "a"))
    server = server_state(mid=server_exam(file))
    assert exam_payload(file)["tags"] == ["a", "b"]
    read = read_exam(exam_payload(file))

    assert project_exam(read) == exam_payload(file)
    assert quiet(plan(local_state(file), server))


def test_a_file_that_gets_a_new_start_after_dropping_it_is_a_write_not_a_conflict():
    s1, s2 = "2026-03-15T14:00:00.000Z", "2026-04-01T09:00:00.000Z"
    declared = exam_file(scheduled_at=s1)
    server = server_state(mid=server_exam(declared))
    base = base_of(server)

    omitted = plan(local_state(replace(declared, scheduled_at=None)), server, base)
    assert quiet(omitted)

    again = plan(
        local_state(replace(declared, scheduled_at=s2)),
        server,
        base_of(server),
    )
    (write,) = exam_writes(again)
    assert isinstance(write, UpsertExam) and write.payload["scheduledAt"] == s2


def test_the_reschedule_cycle_through_an_omitting_push_is_not_a_conflict():
    s1, s2 = "2026-03-15T14:00:00.000Z", "2026-04-01T09:00:00.000Z"
    declared = exam_file(scheduled_at=s1, duration={"hours": 2, "minutes": 0})
    server = server_state(mid=server_exam(declared))
    omitting = replace(declared, scheduled_at=None, duration=None, title="Other")

    first = plan(local_state(omitting), server, base_of(server))
    (write,) = exam_writes(first)
    assert isinstance(write, UpsertExam)
    assert write.payload["scheduledAt"] == s1
    assert write.payload["duration"] == {"hours": 2, "minutes": 0}
    (confirmation,) = [c for c in first.confirmations if c.write == write]
    assert confirmation.update.entry is not None
    assert confirmation.update.entry.payload["scheduledAt"] == s1

    # The push went through: the server holds the new title, the base too.
    pushed = server_state(
        mid=server_exam(omitting, scheduledAt=s1, duration=write.payload["duration"])
    )
    base = base_of(pushed)
    redeclared = replace(omitting, scheduled_at=s2, duration={"hours": 3, "minutes": 0})
    second = plan(local_state(redeclared), pushed, base)

    assert second.conflicts == ()
    (write,) = exam_writes(second)
    assert isinstance(write, UpsertExam)
    assert write.payload["scheduledAt"] == s2
    assert write.payload["duration"] == {"hours": 3, "minutes": 0}


def test_an_instructor_change_to_a_key_the_file_omits_is_a_pull_not_an_overwrite():
    declared = exam_file(scheduled_at="2026-03-15T14:00:00.000Z")
    base = base_of(server_state(mid=server_exam(declared)))
    server = server_state(
        mid=server_exam(declared, scheduledAt="2026-05-01T10:00:00.000Z")
    )
    omitting = replace(declared, scheduled_at=None)

    result = plan(local_state(omitting), server, base)

    assert exam_writes(result) == []
    assert [pull.fields for pull in result.pulls] == [("scheduledAt",)]


def test_a_value_the_server_set_and_the_cli_never_wrote_is_never_a_change():
    file = exam_file(scheduled_at=None, duration=None)
    base = base_of(server_state(mid=server_exam(file)))
    server = server_state(
        mid=server_exam(
            file,
            scheduledAt="2026-05-01T10:00:00.000Z",
            duration={"hours": 1, "minutes": 0},
        )
    )

    assert quiet(plan(local_state(file), server, base))
    result = plan(local_state(replace(file, title="New")), server, base)
    (write,) = exam_writes(result)
    assert isinstance(write, UpsertExam)
    assert "scheduledAt" not in write.payload and "duration" not in write.payload
