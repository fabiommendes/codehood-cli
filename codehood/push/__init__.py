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
    EventKey,
    EventKind,
    Holiday,
    Section,
    TimeOfDay,
    TimeSlot,
    Weekday,
    allocate,
    parse_calendar,
)
from .errors import (
    CalendarError,
    QuestionParseError,
    RepositoryError,
    ResourceLinkError,
    SlugCollisionError,
)
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
from .links import (
    RepositoryLink,
    attach_repositories,
    attach_resources,
    extract_repository_links,
    extract_resource_links,
    rewrite_event_links,
    rewrite_repository_links,
    rewrite_resource_links,
)
from .plan import (
    DeleteCalendarEvent,
    DeleteGradeColumn,
    DeleteQuestion,
    DeleteRepository,
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
    UpsertRepository,
    UpsertResource,
    UpsertTimeSlot,
    WarnRepositoryKept,
    WarnTimeSlotPinned,
    plan_push,
    plan_repositories,
)
from .question import AnyQuestion, QuestionFile, question_version, scan_questions
from .repository import (
    MAX_FILE_BYTES,
    RepositoryEntry,
    RepositoryTree,
    batch_entries,
    blob_sha,
    scan_repositories,
    tree_sha,
)
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
from .run import (
    HttpRepositoryApi,
    OpResult,
    RepositoryApi,
    fetch_server_state,
    fetch_students,
    run_plan,
)

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
    "UpsertRepository",
    "WarnRepositoryKept",
    "DeleteRepository",
    "PushOp",
    "plan_push",
    "plan_repositories",
    #: Calendar
    "Calendar",
    "Allocation",
    "Section",
    "Holiday",
    "TimeSlot",
    "TimeOfDay",
    "Duration",
    "Event",
    "EventKey",
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
    "attach_resources",
    "extract_resource_links",
    "rewrite_event_links",
    "rewrite_resource_links",
    #: Repositories
    "MAX_FILE_BYTES",
    "RepositoryEntry",
    "RepositoryTree",
    "RepositoryLink",
    "batch_entries",
    "blob_sha",
    "tree_sha",
    "scan_repositories",
    "attach_repositories",
    "extract_repository_links",
    "rewrite_repository_links",
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
    "ResourceLinkError",
    "RepositoryError",
    #: Shell
    "OpResult",
    "RepositoryApi",
    "HttpRepositoryApi",
    "fetch_server_state",
    "fetch_students",
    "run_plan",
]
