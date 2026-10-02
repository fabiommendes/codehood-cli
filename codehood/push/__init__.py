"""
`codehood push`: sync a course repository's course row, `calendar.md`,
`resources/` and grade columns to the server. See `dev/specs/to-do/push.md` and
`docs/design/mapping-local-filesystem.md`.

Functional core, imperative shell: `plan.plan_push` is a pure generator
that diffs a `LocalState` against a `ServerState` and yields a plan
(`plan.PushOp`); `run.run_plan` is the only thing here that touches HTTP.
"""

from __future__ import annotations

from .calendar import (
    Allocation,
    Calendar,
    Duration,
    Event,
    EventKind,
    Holiday,
    Section,
    TimeOfDay,
    TimeSlot,
    Weekday,
    allocate,
    parse_calendar,
)
from .errors import CalendarError, QuestionParseError, SlugCollisionError
from .grades import (
    ColumnSpec,
    GradeColumn,
    GradesCsv,
    GradesError,
    Roster,
    ServerStudent,
    build_roster,
    compute_columns,
    parse_grades_csv,
)
from .hook import load_grade_function
from .plan import (
    DeleteCalendarEvent,
    DeleteGradeColumn,
    DeleteQuestion,
    DeleteResource,
    DeleteTimeSlot,
    LocalState,
    PushOp,
    ServerEvent,
    ServerState,
    UpsertCalendarEvent,
    UpsertCourse,
    UpsertGradeColumn,
    UpsertQuestion,
    UpsertResource,
    UpsertTimeSlot,
    WarnTimeSlotPinned,
    plan_push,
)
from .question import AnyQuestion, QuestionFile, question_version, scan_questions
from .resource import (
    CodeData,
    FileData,
    MdData,
    ResourceData,
    ResourceFile,
    content_ref,
    scan_resources,
    slugify,
)
from .run import OpResult, fetch_server_state, fetch_students, run_plan

__all__ = [
    #: Plan
    "LocalState",
    "ServerState",
    "ServerEvent",
    "UpsertCourse",
    "UpsertResource",
    "DeleteResource",
    "UpsertQuestion",
    "DeleteQuestion",
    "UpsertTimeSlot",
    "DeleteTimeSlot",
    "UpsertCalendarEvent",
    "DeleteCalendarEvent",
    "WarnTimeSlotPinned",
    "UpsertGradeColumn",
    "DeleteGradeColumn",
    "PushOp",
    "plan_push",
    #: Calendar
    "Calendar",
    "Allocation",
    "Section",
    "Holiday",
    "TimeSlot",
    "TimeOfDay",
    "Duration",
    "Event",
    "EventKind",
    "Weekday",
    "parse_calendar",
    "allocate",
    #: Resources
    "ResourceFile",
    "ResourceData",
    "MdData",
    "CodeData",
    "FileData",
    "slugify",
    "content_ref",
    #: Questions
    "AnyQuestion",
    "QuestionFile",
    "question_version",
    "scan_questions",
    "scan_resources",
    #: Grade columns
    "ColumnSpec",
    "GradeColumn",
    "GradesCsv",
    "GradesError",
    "Roster",
    "ServerStudent",
    "build_roster",
    "compute_columns",
    "parse_grades_csv",
    "load_grade_function",
    #: Errors
    "SlugCollisionError",
    "QuestionParseError",
    "CalendarError",
    #: Shell
    "OpResult",
    "fetch_server_state",
    "fetch_students",
    "run_plan",
]
