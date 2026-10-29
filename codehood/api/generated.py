# This file is AUTO-GENERATED. DO NOT EDIT!

from __future__ import annotations

from typing import Literal

import httpx
from pydantic import ConfigDict, Field, TypeAdapter

from ..models.base import Model
from .base import CodehoodAPIError, auth_headers, get_client, query_params


class BlobMissingInput(Model):
    hashes: list[str]


class BlobMissingResult(Model):
    missing: list[str]


class CalendarEventCreate(Model):
    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["REGULAR", "HOLIDAY", "CANCELLED"] | None = None
    title: str
    description: str | None = None
    week: int
    rev: str | None = None
    repositories: list[str] | None = None
    time_slot: str = Field(alias="timeSlot")


class CourseAttendanceResponseStudentsItem(Model):
    model_config = ConfigDict(populate_by_name=True)

    username: str
    name: str
    email: str
    school_id: str | None = Field(alias="schoolId")
    status: Literal["ACTIVE", "DROPPED"]
    cells: dict[str, Literal["present", "absent", "before-enrollment"]]
    present: int
    total: int


class CourseCreate(Model):
    model_config = ConfigDict(populate_by_name=True)

    description: str | None = None
    discipline: str
    edition: str
    instructor: str | None = None
    rev: str | None = None
    start_at: str = Field(alias="startAt")
    end_at: str = Field(alias="endAt")


class CourseGradesResponseStudentsItemShape(Model):
    kind: Literal["empty"]


class CourseGradesResponseStudentsItemShape2(Model):
    kind: Literal["in-progress"]


class CourseGradesResponseStudentsItemShape3(Model):
    kind: Literal["missed"]


class CourseGradesResponseStudentsItemShape4(Model):
    kind: Literal["pending"]


class CourseGradesResponseStudentsItemShape5(Model):
    kind: Literal["total"]
    total: float


class DataCode(Model):
    type: Literal["CODE"]
    content: str
    language: str


class DataLink(Model):
    type: Literal["LINK"]
    url: str


class DataMd(Model):
    type: Literal["MD"]
    content: str


class Deleted(Model):
    success: bool
    message: str
    deleted: bool


class Discipline(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    name: str
    created_at: str = Field(alias="createdAt")


class DisciplineCreate(Model):
    slug: str
    name: str


class Duration(Model):
    hours: int | None = None
    minutes: int | None = None


class Edition(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    name: str
    start_at: str = Field(alias="startAt")
    end_at: str = Field(alias="endAt")
    created_at: str = Field(alias="createdAt")


class EditionCreate(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    name: str
    start_at: str = Field(alias="startAt")
    end_at: str = Field(alias="endAt")


class Event(Model):
    model_config = ConfigDict(populate_by_name=True)

    week: int
    time_slot: str = Field(alias="timeSlot")


class EventsItem(Model):
    model_config = ConfigDict(populate_by_name=True)

    week: int
    title: str
    start_at: str = Field(alias="startAt")
    time_slot: str = Field(alias="timeSlot")


class ExamCreateQuestionsItem(Model):
    slug: str
    version: str | None = None


class ExamQuestionsItem(Model):
    slug: str
    version: str | None


class ExamsItem(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    title: str
    scheduled_at: str | None = Field(alias="scheduledAt")


class HealthResponse(Model):
    status: Literal["ok"]
    database: Literal["ok"]


class Instructor(Model):
    name: str
    username: str


class LoginRequest(Model):
    login: str
    password: str


class LoginResponse(Model):
    token: str


class LogoutResponse(Model):
    success: bool


class Question2QuestionEssay(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    author: str | None = None
    stem: str
    epilogue: str | None = None
    comment: str | None = None
    locale: str | None = None
    tags: list[str] | None = None
    weight: float | None = None
    meta: dict[str, object | None] | None = None
    type: Literal["essay"]
    content: Literal["code", "text", "plain"] | None = None
    highlight: str | None = None
    answer_key: str | None = Field(default=None, alias="answerKey")


class Question2QuestionMultipleChoiceChoicesItem(Model):
    id: str | None = None
    text: str
    score: float | None = None
    feedback: str | None = None
    comment: str | None = None


class Question2QuestionMultipleSelectionChoicesItem(Model):
    id: str | None = None
    text: str
    correct: bool
    feedback: str | None = None
    comment: str | None = None


class Question2QuestionOrderingAcceptItem(Model):
    lines: list[list[int | str]]
    feedback: str | None = None
    comment: str | None = None


class Question2QuestionShortAnswerAcceptItem(Model):
    pattern: str
    feedback: str | None = None
    comment: str | None = None


class Question2QuestionTrueFalseChoicesItem(Model):
    id: str | None = None
    text: str
    correct: bool
    marker: str | None = None
    feedback: str | None = None
    comment: str | None = None


class Question3QuestionEssay(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    stem: str
    epilogue: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    weight: float | None = None
    type: Literal["essay"]
    content: Literal["code", "text", "plain"] | None = None
    highlight: str | None = None


class Question3QuestionFillInBlanksItemNumeric(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: Literal["numeric"]
    unit: str | None = None
    domain: Literal["integer", "decimal", "fraction"]
    decimal_places: int | None = Field(default=None, alias="decimalPlaces")


class Question3QuestionMultipleChoiceChoicesItem(Model):
    id: str
    text: str


class Question3QuestionNumeric(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    stem: str
    epilogue: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    weight: float | None = None
    type: Literal["numeric"]
    unit: str | None = None
    domain: Literal["integer", "decimal", "fraction"]
    decimal_places: int | None = Field(default=None, alias="decimalPlaces")


class Question3QuestionOrdering(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    stem: str
    epilogue: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    weight: float | None = None
    type: Literal["ordering"]
    content: Literal["code", "text"]
    highlight: str | None = None
    indentation: Literal["fixed", "lenient", "strict"] | None = None
    unmatched: Literal["manual", "incorrect"]
    normalizations: list[Literal["dedent", "skip-blanks"]] | None = None
    max_level: int | None = Field(default=None, alias="maxLevel")
    pool: list[list[int | str]]


class Question3QuestionShortAnswerPreAcceptItem(Model):
    pattern: str
    feedback: str | None = None


class RepositoriesItem(Model):
    slug: str
    title: str


class Repository(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    title: str
    head: str | None
    tree: str | None
    message: str | None
    committed_at: str | None = Field(alias="committedAt")
    clone_url: str = Field(alias="cloneUrl")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class RepositoryCreate(Model):
    slug: str


class RepositoryDeleted(Model):
    deleted: bool


class ResourceCreateDataFile(Model):
    filename: str
    type: Literal["FILE"]
    buffer: str


class ResourceDataFile(Model):
    model_config = ConfigDict(populate_by_name=True)

    link: str
    mime_type: str = Field(alias="mimeType")
    filename: str
    type: Literal["FILE"]


class RollCallShape(Model):
    model_config = ConfigDict(populate_by_name=True)

    source: Literal["CODE", "MANUAL"]
    joined: Literal["ENROLLMENT", "ACCOUNT", None] | None
    note: str | None
    shared_with: list[str] = Field(alias="sharedWith")
    created_at: str = Field(alias="createdAt")


class Start(Model):
    hour: int
    minute: int


class Tolerance(Model):
    absolute: float | None = None
    relative: float | None = None


class UpdateCalendarEventRequest(Model):
    kind: Literal["REGULAR", "HOLIDAY", "CANCELLED"] | None = None
    title: str | None = None
    description: str | None = None
    rev: str | None = None
    repositories: list[str] | None = None


class UpdateCourseRequest(Model):
    model_config = ConfigDict(populate_by_name=True)

    description: str | None = None
    start_at: str | None = Field(default=None, alias="startAt")
    end_at: str | None = Field(default=None, alias="endAt")
    rev: str | None = None


class UpdateDisciplineRequest(Model):
    name: str | None = None


class UpdateEditionRequest(Model):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    start_at: str | None = Field(default=None, alias="startAt")
    end_at: str | None = Field(default=None, alias="endAt")


class UpdateRollCallRequestShape(Model):
    note: str | None = None


class UpdateUserRequest(Model):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    email: str | None = None
    github_id: str | None = Field(default=None, alias="githubId")
    school_id: str | None = Field(default=None, alias="schoolId")


class User(Model):
    username: str
    name: str


class UserCreate(Model):
    model_config = ConfigDict(populate_by_name=True)

    email: str
    name: str
    username: str
    role: Literal["STUDENT", "INSTRUCTOR", "ADMIN"]
    github_id: str | None = Field(default=None, alias="githubId")
    school_id: str | None = Field(default=None, alias="schoolId")
    password: str


class ValuesItem(Model):
    username: str
    value: float | str


class Course(Model):
    model_config = ConfigDict(populate_by_name=True)

    description: str | None
    discipline: DisciplineCreate
    edition: DisciplineCreate
    instructor: Instructor
    enrollment_count: int = Field(alias="enrollmentCount")
    rev: str | None
    start_at: str = Field(alias="startAt")
    end_at: str = Field(alias="endAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    joined_at: str = Field(alias="joinedAt")


class CourseAttendanceResponse(Model):
    events: list[EventsItem]
    students: list[CourseAttendanceResponseStudentsItem]


class CourseGradesResponseStudentsItem(Model):
    model_config = ConfigDict(populate_by_name=True)

    username: str
    name: str
    email: str
    school_id: str | None = Field(alias="schoolId")
    github_id: str | None = Field(alias="githubId")
    status: Literal["ACTIVE", "DROPPED"]
    results: dict[
        str,
        CourseGradesResponseStudentsItemShape5
        | CourseGradesResponseStudentsItemShape4
        | CourseGradesResponseStudentsItemShape2
        | CourseGradesResponseStudentsItemShape3
        | CourseGradesResponseStudentsItemShape,
    ]


class Exam(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    type: Literal["PRACTICE", "QUIZ", "EXAM"]
    status: Literal["DRAFT", "ARCHIVED", "SCHEDULED", "ONGOING", "COMPLETED"]
    title: str
    description: str | None
    preamble: str | None
    format: Literal["PLAINTEXT", "MARKDOWN", "HTML"]
    scheduled_at: str | None = Field(alias="scheduledAt")
    duration: Duration | None
    extra_time: Duration | None = Field(alias="extraTime")
    grades_released_at: str | None = Field(alias="gradesReleasedAt")
    author: str
    rev: str | None
    tags: list[str]
    questions: list[ExamQuestionsItem]
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ExamCreate(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    type: Literal["PRACTICE", "QUIZ", "EXAM"] | None = None
    status: Literal["DRAFT", "ARCHIVED", "SCHEDULED", "ONGOING", "COMPLETED"] | None = (
        None
    )
    title: str
    description: str | None = None
    preamble: str | None = None
    format: Literal["PLAINTEXT", "MARKDOWN", "HTML"] | None = None
    scheduled_at: str | None = Field(default=None, alias="scheduledAt")
    duration: Duration | None = None
    rev: str | None = None
    tags: list[str] | None = None
    questions: list[ExamCreateQuestionsItem] | None = None


class GradeColumn(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    title: str
    kind: Literal["NUMBER", "LABEL"]
    position: int
    released_at: str | None = Field(alias="releasedAt")
    rev: str | None
    values: list[ValuesItem]
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class GradeColumnCreate(Model):
    slug: str
    title: str
    kind: Literal["NUMBER", "LABEL"]
    position: int
    rev: str | None = None
    values: list[ValuesItem]


class Question2QuestionFillInBlanksItemMultipleChoice(Model):
    id: str
    type: Literal["multiple-choice"]
    choices: list[Question2QuestionMultipleChoiceChoicesItem]


class Question2QuestionFillInBlanksItemNumeric(Model):
    model_config = ConfigDict(populate_by_name=True)

    answer: float | str
    unit: str | None = None
    domain: Literal["integer", "decimal", "fraction"] | None = None
    decimal_places: int | None = Field(default=None, alias="decimalPlaces")
    tolerance: Tolerance | None = None
    id: str
    type: Literal["numeric"]
    incorrect_feedback: str | None = Field(default=None, alias="incorrectFeedback")


class Question2QuestionFillInBlanksItemShortAnswer(Model):
    model_config = ConfigDict(populate_by_name=True)

    accept: list[str | Question2QuestionShortAnswerAcceptItem] | None = None
    reject: list[str | Question2QuestionShortAnswerAcceptItem] | None = None
    pre_accept: list[str | Question2QuestionShortAnswerAcceptItem] | None = Field(
        default=None, alias="preAccept"
    )
    pre_reject: list[str | Question2QuestionShortAnswerAcceptItem] | None = Field(
        default=None, alias="preReject"
    )
    id: str
    type: Literal["short-answer"]
    incorrect_feedback: str | None = Field(default=None, alias="incorrectFeedback")


class Question2QuestionMultipleChoice(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    author: str | None = None
    stem: str
    epilogue: str | None = None
    comment: str | None = None
    locale: str | None = None
    tags: list[str] | None = None
    weight: float | None = None
    meta: dict[str, object | None] | None = None
    type: Literal["multiple-choice"]
    choices: list[Question2QuestionMultipleChoiceChoicesItem]
    grading: Literal["partial", "symmetric", "inherit"] | None = None
    shuffle: bool | Literal["inherit"] | None = None


class Question2QuestionMultipleSelection(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    author: str | None = None
    stem: str
    epilogue: str | None = None
    comment: str | None = None
    locale: str | None = None
    tags: list[str] | None = None
    weight: float | None = None
    meta: dict[str, object | None] | None = None
    type: Literal["multiple-selection"]
    choices: list[Question2QuestionMultipleSelectionChoicesItem]
    grading: Literal["partial", "all-or-nothing", "symmetric", "inherit"] | None = None
    shuffle: bool | Literal["inherit"] | None = None


class Question2QuestionNumeric(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    author: str | None = None
    stem: str
    epilogue: str | None = None
    comment: str | None = None
    locale: str | None = None
    tags: list[str] | None = None
    weight: float | None = None
    meta: dict[str, object | None] | None = None
    answer: float | str
    unit: str | None = None
    domain: Literal["integer", "decimal", "fraction"] | None = None
    decimal_places: int | None = Field(default=None, alias="decimalPlaces")
    tolerance: Tolerance | None = None
    type: Literal["numeric"]
    incorrect_feedback: str | None = Field(default=None, alias="incorrectFeedback")


class Question2QuestionOrdering(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    author: str | None = None
    stem: str
    epilogue: str | None = None
    comment: str | None = None
    locale: str | None = None
    tags: list[str] | None = None
    weight: float | None = None
    meta: dict[str, object | None] | None = None
    type: Literal["ordering"]
    lines: list[list[int | str]]
    extra: list[list[int | str]] | None = None
    accept: list[Question2QuestionOrderingAcceptItem] | None = None
    reject: list[Question2QuestionOrderingAcceptItem] | None = None
    content: Literal["code", "text"]
    highlight: str | None = None
    indentation: Literal["fixed", "lenient", "strict"] | None = None
    unmatched: Literal["manual", "incorrect"] | None = None
    incorrect_feedback: str | None = Field(default=None, alias="incorrectFeedback")
    normalizations: list[Literal["dedent", "skip-blanks"]] | None = None


class Question2QuestionShortAnswer(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    author: str | None = None
    stem: str
    epilogue: str | None = None
    comment: str | None = None
    locale: str | None = None
    tags: list[str] | None = None
    weight: float | None = None
    meta: dict[str, object | None] | None = None
    accept: list[str | Question2QuestionShortAnswerAcceptItem] | None = None
    reject: list[str | Question2QuestionShortAnswerAcceptItem] | None = None
    pre_accept: list[str | Question2QuestionShortAnswerAcceptItem] | None = Field(
        default=None, alias="preAccept"
    )
    pre_reject: list[str | Question2QuestionShortAnswerAcceptItem] | None = Field(
        default=None, alias="preReject"
    )
    type: Literal["short-answer"]
    diacritics: Literal["fold", "keep"] | None = None
    unmatched: Literal["manual", "incorrect"] | None = None
    incorrect_feedback: str | None = Field(default=None, alias="incorrectFeedback")


class Question2QuestionTrueFalse(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    author: str | None = None
    stem: str
    epilogue: str | None = None
    comment: str | None = None
    locale: str | None = None
    tags: list[str] | None = None
    weight: float | None = None
    meta: dict[str, object | None] | None = None
    type: Literal["true-false"]
    choices: list[Question2QuestionTrueFalseChoicesItem]
    grading: (
        Literal["partial", "no-mistakes", "all-or-nothing", "symmetric", "inherit"]
        | None
    ) = None
    shuffle: bool | Literal["inherit"] | None = None


class Question3QuestionFillInBlanksItemMultipleChoice(Model):
    id: str
    type: Literal["multiple-choice"]
    choices: list[Question3QuestionMultipleChoiceChoicesItem]


class Question3QuestionFillInBlanksItemShortAnswer(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: Literal["short-answer"]
    unmatched: Literal["manual", "incorrect"]
    pre_accept: list[str | Question3QuestionShortAnswerPreAcceptItem] | None = Field(
        default=None, alias="preAccept"
    )
    pre_reject: list[str | Question3QuestionShortAnswerPreAcceptItem] | None = Field(
        default=None, alias="preReject"
    )


class Question3QuestionMultipleChoice(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    stem: str
    epilogue: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    weight: float | None = None
    type: Literal["multiple-choice"]
    shuffle: bool | Literal["inherit"] | None = None
    grading: Literal["partial", "symmetric", "inherit"] | None = None
    choices: list[Question3QuestionMultipleChoiceChoicesItem]


class Question3QuestionMultipleSelection(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    stem: str
    epilogue: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    weight: float | None = None
    type: Literal["multiple-selection"]
    shuffle: bool | Literal["inherit"] | None = None
    grading: Literal["partial", "all-or-nothing", "symmetric", "inherit"] | None = None
    choices: list[Question3QuestionMultipleChoiceChoicesItem]


class Question3QuestionShortAnswer(Model):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    stem: str
    epilogue: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    weight: float | None = None
    type: Literal["short-answer"]
    diacritics: Literal["fold", "keep"] | None = None
    unmatched: Literal["manual", "incorrect"]
    pre_accept: list[str | Question3QuestionShortAnswerPreAcceptItem] | None = Field(
        default=None, alias="preAccept"
    )
    pre_reject: list[str | Question3QuestionShortAnswerPreAcceptItem] | None = Field(
        default=None, alias="preReject"
    )


class Question3QuestionTrueFalse(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    stem: str
    epilogue: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    weight: float | None = None
    type: Literal["true-false"]
    shuffle: bool | Literal["inherit"] | None = None
    grading: (
        Literal["partial", "no-mistakes", "all-or-nothing", "symmetric", "inherit"]
        | None
    ) = None
    choices: list[Question3QuestionMultipleChoiceChoicesItem]


class Resource(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    title: str
    description: str | None
    data: DataLink | ResourceDataFile | DataCode | DataMd
    event: Event | None
    rev: str | None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class ResourceCreate(Model):
    slug: str
    title: str
    rev: str | None = None
    description: str | None = None
    event: Event | None = None
    data: DataLink | ResourceCreateDataFile | DataCode | DataMd


class RollCall(Model):
    model_config = ConfigDict(populate_by_name=True)

    week: int
    time_slot: str = Field(alias="timeSlot")
    acts_as_invite: bool = Field(alias="actsAsInvite")
    closes_at: str = Field(alias="closesAt")
    attendances: dict[str, RollCallShape]
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class TimeSlot(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    title: str | None
    day: Literal[
        "SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"
    ]
    start: Start
    duration: Duration
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class TimeSlotAtCalendarEvent(Model):
    slug: str
    day: Literal[
        "SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"
    ]
    start: Start
    duration: Duration


class TimeSlotCreate(Model):
    slug: str
    title: str | None = None
    day: Literal[
        "SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"
    ]
    start: Start
    duration: Duration


class UpdateExamRequest(Model):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["PRACTICE", "QUIZ", "EXAM"] | None = None
    status: Literal["DRAFT", "ARCHIVED", "SCHEDULED", "ONGOING", "COMPLETED"] | None = (
        None
    )
    title: str | None = None
    description: str | None = None
    preamble: str | None = None
    format: Literal["PLAINTEXT", "MARKDOWN", "HTML"] | None = None
    scheduled_at: str | None = Field(default=None, alias="scheduledAt")
    duration: Duration | None = None
    rev: str | None = None
    tags: list[str] | None = None
    questions: list[ExamCreateQuestionsItem] | None = None
    extra_time: Duration | None = Field(default=None, alias="extraTime")


class UpdateGradeColumnRequest(Model):
    title: str | None = None
    kind: Literal["NUMBER", "LABEL"] | None = None
    position: int | None = None
    rev: str | None = None
    values: list[ValuesItem] | None = None


class UpdateResourceRequest(Model):
    title: str | None = None
    rev: str | None = None
    description: str | None = None
    event: Event | None = None
    data: DataLink | ResourceCreateDataFile | DataCode | DataMd | None = None


class UpdateRollCallRequest(Model):
    model_config = ConfigDict(populate_by_name=True)

    acts_as_invite: bool | None = Field(default=None, alias="actsAsInvite")
    attendances: dict[str, UpdateRollCallRequestShape | None] | None = None


class UpdateTimeslotRequest(Model):
    title: str | None = None
    day: (
        Literal[
            "SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"
        ]
        | None
    ) = None
    start: Start | None = None
    duration: Duration | None = None


class CalendarEvent(Model):
    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["REGULAR", "HOLIDAY", "CANCELLED"]
    title: str
    description: str | None
    start_at: str = Field(alias="startAt")
    week: int
    time_slot: TimeSlotAtCalendarEvent = Field(alias="timeSlot")
    rev: str | None
    repositories: list[RepositoriesItem]
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class CourseGradesResponse(Model):
    exams: list[ExamsItem]
    students: list[CourseGradesResponseStudentsItem]


class Question2QuestionFillIn(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    author: str | None = None
    stem: str
    epilogue: str | None = None
    comment: str | None = None
    locale: str | None = None
    tags: list[str] | None = None
    weight: float | None = None
    meta: dict[str, object | None] | None = None
    type: Literal["fill-in"]
    blanks: list[
        Question2QuestionFillInBlanksItemMultipleChoice
        | Question2QuestionFillInBlanksItemShortAnswer
        | Question2QuestionFillInBlanksItemNumeric
    ]
    grading: (
        Literal["partial", "no-mistakes", "all-or-nothing", "symmetric", "inherit"]
        | None
    ) = None
    shuffle: bool | Literal["inherit"] | None = None
    diacritics: Literal["fold", "keep"] | None = None
    unmatched: Literal["manual", "incorrect"] | None = None


class Question3QuestionFillIn(Model):
    id: str | None = None
    uuid: str | None = None
    title: str | None = None
    stem: str
    epilogue: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    weight: float | None = None
    type: Literal["fill-in"]
    shuffle: bool | Literal["inherit"] | None = None
    grading: (
        Literal["partial", "no-mistakes", "all-or-nothing", "symmetric", "inherit"]
        | None
    ) = None
    diacritics: Literal["fold", "keep"] | None = None
    blanks: list[
        Question3QuestionFillInBlanksItemMultipleChoice
        | Question3QuestionFillInBlanksItemShortAnswer
        | Question3QuestionFillInBlanksItemNumeric
    ]


class Question2(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
    version: str
    rev: str | None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    question: (
        Question2QuestionMultipleChoice
        | Question2QuestionMultipleSelection
        | Question2QuestionTrueFalse
        | Question2QuestionNumeric
        | Question2QuestionShortAnswer
        | Question2QuestionEssay
        | Question2QuestionFillIn
        | Question2QuestionOrdering
    )


class Question3(Model):
    model_config = ConfigDict(populate_by_name=True)

    slug: str
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
    version: str
    rev: str | None
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    question: (
        Question3QuestionMultipleChoice
        | Question3QuestionMultipleSelection
        | Question3QuestionTrueFalse
        | Question3QuestionNumeric
        | Question3QuestionShortAnswer
        | Question3QuestionEssay
        | Question3QuestionFillIn
        | Question3QuestionOrdering
    )


class QuestionCreate(Model):
    slug: str
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
    version: str
    rev: str | None = None
    question: (
        Question2QuestionMultipleChoice
        | Question2QuestionMultipleSelection
        | Question2QuestionTrueFalse
        | Question2QuestionNumeric
        | Question2QuestionShortAnswer
        | Question2QuestionEssay
        | Question2QuestionFillIn
        | Question2QuestionOrdering
    )


class UpdateQuestionRequest(Model):
    status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"] | None = None
    version: str | None = None
    rev: str | None = None
    question: (
        Question2QuestionMultipleChoice
        | Question2QuestionMultipleSelection
        | Question2QuestionTrueFalse
        | Question2QuestionNumeric
        | Question2QuestionShortAnswer
        | Question2QuestionEssay
        | Question2QuestionFillIn
        | Question2QuestionOrdering
        | None
    ) = None


class HealthError(CodehoodAPIError):
    class Payload(Model):
        status: Literal["error"]
        database: Literal["unreachable"]

    payload: Payload

    @property
    def database(self) -> Literal["unreachable"]:
        return self.payload.database


class InvalidCredentials(CodehoodAPIError):
    class Payload(Model):
        type: Literal["error"]
        code: Literal["not-allowed"]
        status: Literal[401]
        message: str
        action: str
        timestamp: str | None

    payload: Payload

    @property
    def type(self) -> Literal["error"]:
        return self.payload.type

    @property
    def code(self) -> Literal["not-allowed"]:
        return self.payload.code

    @property
    def message(self) -> str:
        return self.payload.message

    @property
    def action(self) -> str:
        return self.payload.action

    @property
    def timestamp(self) -> str | None:
        return self.payload.timestamp


def blob_missing(
    *, body: BlobMissingInput, client: httpx.Client | None = None
) -> BlobMissingResult:
    """
    List the hashes the server has no blob for.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/blob/missing",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return BlobMissingResult.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def course_attendance(
    *, discipline: str, course: str, client: httpx.Client | None = None
) -> CourseAttendanceResponse:
    """
    View the attendance of every student
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/attendance".format(
            discipline=discipline, course=course
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return CourseAttendanceResponse.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def course_grades(
    *, discipline: str, course: str, client: httpx.Client | None = None
) -> CourseGradesResponse:
    """
    View the exam results of every student
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/grades".format(
            discipline=discipline, course=course
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return CourseGradesResponse.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_calendar_event(
    *,
    discipline: str,
    course: str,
    body: CalendarEventCreate,
    client: httpx.Client | None = None,
) -> CalendarEvent:
    """
    Creates a new Calendar Event.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/course/{discipline}/{course}/calendar-event".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return CalendarEvent.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_course(*, body: CourseCreate, client: httpx.Client | None = None) -> Course:
    """
    Creates a new Course.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/course",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Course.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_discipline(
    *, body: DisciplineCreate, client: httpx.Client | None = None
) -> Discipline:
    """
    Creates a new Discipline.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/discipline",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Discipline.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_edition(
    *, body: EditionCreate, client: httpx.Client | None = None
) -> Edition:
    """
    Creates a new Edition.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/edition",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Edition.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_exam(
    *,
    discipline: str,
    course: str,
    body: ExamCreate,
    client: httpx.Client | None = None,
) -> Exam:
    """
    Creates a new Exam.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/course/{discipline}/{course}/exam".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Exam.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_grade_column(
    *,
    discipline: str,
    course: str,
    body: GradeColumnCreate,
    client: httpx.Client | None = None,
) -> GradeColumn:
    """
    Creates a new Grade Column.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/course/{discipline}/{course}/grade-column".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return GradeColumn.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_question(
    *,
    discipline: str,
    course: str,
    body: QuestionCreate,
    client: httpx.Client | None = None,
) -> Question2 | Question3:
    """
    Creates a new Question.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/course/{discipline}/{course}/question".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(Question2 | Question3).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_resource(
    *,
    discipline: str,
    course: str,
    body: ResourceCreate,
    client: httpx.Client | None = None,
) -> Resource:
    """
    Creates a new Resource.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/course/{discipline}/{course}/resource".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Resource.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_timeslot(
    *,
    discipline: str,
    course: str,
    body: TimeSlotCreate,
    client: httpx.Client | None = None,
) -> TimeSlot:
    """
    Creates a new TimeSlot.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/course/{discipline}/{course}/time-slot".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TimeSlot.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def create_user(*, body: UserCreate, client: httpx.Client | None = None) -> User:
    """
    Creates a new User.
    """
    client = client if client is not None else get_client()
    response = client.post(
        "/api/user",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return User.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_calendar_event(
    *,
    discipline: str,
    course: str,
    week: str,
    time_slot: str,
    client: httpx.Client | None = None,
) -> Deleted:
    """
    Delete a single Calendar Event by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}/calendar-event/{week}/{timeSlot}".format(
            discipline=discipline, course=course, week=week, timeSlot=time_slot
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_course(
    *, discipline: str, course: str, client: httpx.Client | None = None
) -> Deleted:
    """
    Delete a single Course by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}".format(
            discipline=discipline, course=course
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_discipline(*, slug: str, client: httpx.Client | None = None) -> Deleted:
    """
    Delete a single Discipline by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/discipline/{slug}".format(slug=slug), headers=auth_headers(client)
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_edition(*, slug: str, client: httpx.Client | None = None) -> Deleted:
    """
    Delete a single Edition by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/edition/{slug}".format(slug=slug), headers=auth_headers(client)
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_exam(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> Deleted:
    """
    Delete a single Exam by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}/exam/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_grade_column(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> Deleted:
    """
    Delete a single Grade Column by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}/grade-column/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_question(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> Deleted:
    """
    Delete a single Question by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}/question/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_resource(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> Deleted:
    """
    Delete a single Resource by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}/resource/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_roll_call(
    *,
    discipline: str,
    course: str,
    week: str,
    time_slot: str,
    client: httpx.Client | None = None,
) -> Deleted:
    """
    Delete a single Roll Call by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}/roll-call/{week}/{timeSlot}".format(
            discipline=discipline, course=course, week=week, timeSlot=time_slot
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_timeslot(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> Deleted:
    """
    Delete a single TimeSlot by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}/time-slot/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def delete_user(*, username: str, client: httpx.Client | None = None) -> Deleted:
    """
    Delete a single User by primary key.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/user/{username}".format(username=username), headers=auth_headers(client)
    )
    if response.status_code == 200:
        return Deleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def health(*, client: httpx.Client | None = None) -> HealthResponse:
    """
    Liveness/readiness probe
    """
    client = client if client is not None else get_client()
    response = client.get("/api/health")
    if response.status_code == 503:
        raise HealthError(
            response.status_code, HealthError.Payload.model_validate(response.json())
        )
    if response.status_code == 200:
        return HealthResponse.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_calendar_event(
    *,
    discipline: str,
    course: str,
    from_: str | None = None,
    to: str | None = None,
    kinds: list[Literal["REGULAR", "HOLIDAY", "CANCELLED"]] | None = None,
    weeks: list[int] | None = None,
    limit: int | None = None,
    client: httpx.Client | None = None,
) -> list[CalendarEvent]:
    """
    Find multiple Calendar Events.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/calendar-event".format(
            discipline=discipline, course=course
        ),
        params=query_params(
            {"from": from_, "to": to, "kinds": kinds, "weeks": weeks, "limit": limit}
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[CalendarEvent]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_course(
    *,
    instructor: str | None = None,
    discipline: str | None = None,
    edition: str | None = None,
    client: httpx.Client | None = None,
) -> list[Course]:
    """
    Find multiple Courses.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course",
        params=query_params(
            {"instructor": instructor, "discipline": discipline, "edition": edition}
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[Course]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_discipline(
    *, slugs: list[str] | None = None, client: httpx.Client | None = None
) -> list[Discipline]:
    """
    Find multiple Disciplines.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/discipline",
        params=query_params({"slugs": slugs}),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[Discipline]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_edition(
    *,
    slugs: list[str] | None = None,
    active: bool | None = None,
    client: httpx.Client | None = None,
) -> list[Edition]:
    """
    Find multiple Editions.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/edition",
        params=query_params({"slugs": slugs, "active": active}),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[Edition]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_exam(
    *,
    discipline: str,
    course: str,
    exams: list[str] | None = None,
    statuses: list[Literal["DRAFT", "ARCHIVED", "SCHEDULED", "ONGOING", "COMPLETED"]]
    | None = None,
    types: list[Literal["PRACTICE", "QUIZ", "EXAM"]] | None = None,
    tags: list[str] | None = None,
    client: httpx.Client | None = None,
) -> list[Exam]:
    """
    Find multiple Exams.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/exam".format(
            discipline=discipline, course=course
        ),
        params=query_params(
            {"exams": exams, "statuses": statuses, "types": types, "tags": tags}
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[Exam]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_grade_column(
    *, discipline: str, course: str, client: httpx.Client | None = None
) -> list[GradeColumn]:
    """
    Find multiple Grade Columns.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/grade-column".format(
            discipline=discipline, course=course
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[GradeColumn]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_question(
    *,
    discipline: str,
    course: str,
    slugs: list[str] | None = None,
    statuses: list[Literal["DRAFT", "PUBLISHED", "ARCHIVED"]] | None = None,
    types: list[
        Literal[
            "multiple-choice",
            "multiple-selection",
            "true-false",
            "essay",
            "numeric",
            "short-answer",
            "fill-in",
            "ordering",
        ]
    ]
    | None = None,
    tags: list[str] | None = None,
    public: bool | None = None,
    client: httpx.Client | None = None,
) -> list[Question2 | Question3]:
    """
    Find multiple Questions.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/question".format(
            discipline=discipline, course=course
        ),
        params=query_params(
            {
                "slugs": slugs,
                "statuses": statuses,
                "types": types,
                "tags": tags,
                "public": public,
            }
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[Question2 | Question3]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_resource(
    *,
    discipline: str,
    course: str,
    types: list[Literal["LINK", "FILE", "CODE", "MD"]] | None = None,
    slugs: list[str] | None = None,
    client: httpx.Client | None = None,
) -> list[Resource]:
    """
    Find multiple Resources.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/resource".format(
            discipline=discipline, course=course
        ),
        params=query_params({"types": types, "slugs": slugs}),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[Resource]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_roll_call(
    *, discipline: str, course: str, client: httpx.Client | None = None
) -> list[RollCall]:
    """
    Find multiple Roll Calls.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/roll-call".format(
            discipline=discipline, course=course
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[RollCall]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_timeslot(
    *,
    discipline: str,
    course: str,
    days: list[
        Literal[
            "SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"
        ]
    ]
    | None = None,
    client: httpx.Client | None = None,
) -> list[TimeSlot]:
    """
    Find multiple Time Slots.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/time-slot".format(
            discipline=discipline, course=course
        ),
        params=query_params({"days": days}),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[TimeSlot]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def list_user(
    *,
    usernames: list[str] | None = None,
    take: int | None = None,
    client: httpx.Client | None = None,
) -> list[User]:
    """
    Find multiple Users.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/user",
        params=query_params({"usernames": usernames, "take": take}),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[User]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def login(*, body: LoginRequest, client: httpx.Client | None = None) -> LoginResponse:
    client = client if client is not None else get_client()
    response = client.post(
        "/api/auth/login", json=body.model_dump(mode="json", by_alias=True)
    )
    if response.status_code == 401:
        raise InvalidCredentials(
            response.status_code,
            InvalidCredentials.Payload.model_validate(response.json()),
        )
    if response.status_code == 200:
        return LoginResponse.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def logout(*, client: httpx.Client | None = None) -> LogoutResponse:
    """
    Logs out the current user.
    """
    client = client if client is not None else get_client()
    response = client.post("/api/auth/logout", headers=auth_headers(client))
    if response.status_code == 200:
        return LogoutResponse.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_calendar_event(
    *,
    discipline: str,
    course: str,
    week: str,
    time_slot: str,
    client: httpx.Client | None = None,
) -> CalendarEvent:
    """
    Find a single Calendar Event.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/calendar-event/{week}/{timeSlot}".format(
            discipline=discipline, course=course, week=week, timeSlot=time_slot
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return CalendarEvent.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_course(
    *, discipline: str, course: str, client: httpx.Client | None = None
) -> Course:
    """
    Find a single Course.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}".format(
            discipline=discipline, course=course
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Course.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_discipline(*, slug: str, client: httpx.Client | None = None) -> Discipline:
    """
    Find a single Discipline.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/discipline/{slug}".format(slug=slug), headers=auth_headers(client)
    )
    if response.status_code == 200:
        return Discipline.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_edition(*, slug: str, client: httpx.Client | None = None) -> Edition:
    """
    Find a single Edition.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/edition/{slug}".format(slug=slug), headers=auth_headers(client)
    )
    if response.status_code == 200:
        return Edition.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_exam(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> Exam:
    """
    Find a single Exam.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/exam/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Exam.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_grade_column(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> GradeColumn:
    """
    Find a single Grade Column.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/grade-column/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return GradeColumn.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_question(
    *,
    discipline: str,
    course: str,
    slug: str,
    public: bool | None = None,
    client: httpx.Client | None = None,
) -> Question2 | Question3:
    """
    Find a single Question.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/question/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        params=query_params({"public": public}),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(Question2 | Question3).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_resource(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> Resource:
    """
    Find a single Resource.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/resource/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Resource.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_roll_call(
    *,
    discipline: str,
    course: str,
    week: str,
    time_slot: str,
    client: httpx.Client | None = None,
) -> RollCall:
    """
    Find a single Roll Call.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/roll-call/{week}/{timeSlot}".format(
            discipline=discipline, course=course, week=week, timeSlot=time_slot
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return RollCall.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_timeslot(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> TimeSlot:
    """
    Find a single TimeSlot.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/time-slot/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TimeSlot.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def read_user(*, username: str, client: httpx.Client | None = None) -> User:
    """
    Find a single User.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/user/{username}".format(username=username), headers=auth_headers(client)
    )
    if response.status_code == 200:
        return User.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def repository_delete(
    *, discipline: str, course: str, slug: str, client: httpx.Client | None = None
) -> RepositoryDeleted:
    """
    Delete a single Repository.
    """
    client = client if client is not None else get_client()
    response = client.delete(
        "/api/course/{discipline}/{course}/repository/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return RepositoryDeleted.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def repository_list(
    *, discipline: str, course: str, client: httpx.Client | None = None
) -> list[Repository]:
    """
    Find multiple Repositories.
    """
    client = client if client is not None else get_client()
    response = client.get(
        "/api/course/{discipline}/{course}/repository".format(
            discipline=discipline, course=course
        ),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(list[Repository]).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def repository_upsert(
    *,
    discipline: str,
    course: str,
    body: RepositoryCreate,
    client: httpx.Client | None = None,
) -> Repository:
    """
    Upsert a single Repository.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/course/{discipline}/{course}/repository".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Repository.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_calendar_event(
    *,
    discipline: str,
    course: str,
    week: str,
    time_slot: str,
    body: UpdateCalendarEventRequest,
    client: httpx.Client | None = None,
) -> CalendarEvent:
    """
    Update a single Calendar Event.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/course/{discipline}/{course}/calendar-event/{week}/{timeSlot}".format(
            discipline=discipline, course=course, week=week, timeSlot=time_slot
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return CalendarEvent.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_course(
    *,
    discipline: str,
    course: str,
    body: UpdateCourseRequest,
    client: httpx.Client | None = None,
) -> Course:
    """
    Update a single Course.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/course/{discipline}/{course}".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Course.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_discipline(
    *, slug: str, body: UpdateDisciplineRequest, client: httpx.Client | None = None
) -> Discipline:
    """
    Update a single Discipline.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/discipline/{slug}".format(slug=slug),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Discipline.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_edition(
    *, slug: str, body: UpdateEditionRequest, client: httpx.Client | None = None
) -> Edition:
    """
    Update a single Edition.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/edition/{slug}".format(slug=slug),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Edition.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_exam(
    *,
    discipline: str,
    course: str,
    slug: str,
    body: UpdateExamRequest,
    client: httpx.Client | None = None,
) -> Exam:
    """
    Update a single Exam.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/course/{discipline}/{course}/exam/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Exam.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_grade_column(
    *,
    discipline: str,
    course: str,
    slug: str,
    body: UpdateGradeColumnRequest,
    client: httpx.Client | None = None,
) -> GradeColumn:
    """
    Update a single Grade Column.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/course/{discipline}/{course}/grade-column/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return GradeColumn.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_question(
    *,
    discipline: str,
    course: str,
    slug: str,
    body: UpdateQuestionRequest,
    client: httpx.Client | None = None,
) -> Question2 | Question3:
    """
    Update a single Question.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/course/{discipline}/{course}/question/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(Question2 | Question3).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_resource(
    *,
    discipline: str,
    course: str,
    slug: str,
    body: UpdateResourceRequest,
    client: httpx.Client | None = None,
) -> Resource:
    """
    Update a single Resource.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/course/{discipline}/{course}/resource/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Resource.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_roll_call(
    *,
    discipline: str,
    course: str,
    week: str,
    time_slot: str,
    body: UpdateRollCallRequest,
    client: httpx.Client | None = None,
) -> RollCall:
    """
    Update a single Roll Call.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/course/{discipline}/{course}/roll-call/{week}/{timeSlot}".format(
            discipline=discipline, course=course, week=week, timeSlot=time_slot
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return RollCall.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_timeslot(
    *,
    discipline: str,
    course: str,
    slug: str,
    body: UpdateTimeslotRequest,
    client: httpx.Client | None = None,
) -> TimeSlot:
    """
    Update a single TimeSlot.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/course/{discipline}/{course}/time-slot/{slug}".format(
            discipline=discipline, course=course, slug=slug
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TimeSlot.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def update_user(
    *, username: str, body: UpdateUserRequest, client: httpx.Client | None = None
) -> User:
    """
    Update a single User.
    """
    client = client if client is not None else get_client()
    response = client.patch(
        "/api/user/{username}".format(username=username),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return User.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_calendar_event(
    *,
    discipline: str,
    course: str,
    body: CalendarEventCreate,
    client: httpx.Client | None = None,
) -> CalendarEvent:
    """
    Upsert a single Calendar Event. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/course/{discipline}/{course}/calendar-event".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return CalendarEvent.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_course(*, body: CourseCreate, client: httpx.Client | None = None) -> Course:
    """
    Upsert a single Course. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/course",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Course.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_discipline(
    *, body: DisciplineCreate, client: httpx.Client | None = None
) -> Discipline:
    """
    Upsert a single Discipline. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/discipline",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Discipline.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_edition(
    *, body: EditionCreate, client: httpx.Client | None = None
) -> Edition:
    """
    Upsert a single Edition. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/edition",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Edition.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_exam(
    *,
    discipline: str,
    course: str,
    body: ExamCreate,
    client: httpx.Client | None = None,
) -> Exam:
    """
    Upsert a single Exam. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/course/{discipline}/{course}/exam".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Exam.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_grade_column(
    *,
    discipline: str,
    course: str,
    body: GradeColumnCreate,
    client: httpx.Client | None = None,
) -> GradeColumn:
    """
    Upsert a single Grade Column. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/course/{discipline}/{course}/grade-column".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return GradeColumn.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_question(
    *,
    discipline: str,
    course: str,
    body: QuestionCreate,
    client: httpx.Client | None = None,
) -> Question2 | Question3:
    """
    Upsert a single Question. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/course/{discipline}/{course}/question".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TypeAdapter(Question2 | Question3).validate_python(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_resource(
    *,
    discipline: str,
    course: str,
    body: ResourceCreate,
    client: httpx.Client | None = None,
) -> Resource:
    """
    Upsert a single Resource. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/course/{discipline}/{course}/resource".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return Resource.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_timeslot(
    *,
    discipline: str,
    course: str,
    body: TimeSlotCreate,
    client: httpx.Client | None = None,
) -> TimeSlot:
    """
    Upsert a single TimeSlot. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/course/{discipline}/{course}/time-slot".format(
            discipline=discipline, course=course
        ),
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return TimeSlot.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())


def upsert_user(*, body: UserCreate, client: httpx.Client | None = None) -> User:
    """
    Upsert a single User. Creates if it does not exist, update otherwise.
    """
    client = client if client is not None else get_client()
    response = client.put(
        "/api/user",
        json=body.model_dump(mode="json", by_alias=True),
        headers=auth_headers(client),
    )
    if response.status_code == 200:
        return User.model_validate(response.json())
    response.raise_for_status()
    raise CodehoodAPIError(response.status_code, Model())
