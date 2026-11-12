"""
The body a `PUT` carries is the payload the plan compares and the base
records, plus `rev`: the stored entity answers with the same fields.
"""

from __future__ import annotations

import json

import httpx
import pytest

from codehood.api import base as base_module
from codehood.push.calendar import Duration, Event, TimeOfDay, TimeSlot
from codehood.push.grades import GradeColumn
from codehood.push.plan import (
    UpsertCalendarEvent,
    UpsertGradeColumn,
    UpsertTimeSlot,
    Write,
)
from codehood.push.run import run_plan
from codehood.push.wire import event_payload, grade_column_payload, time_slot_payload


@pytest.fixture(autouse=True)
def credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(base_module, "CREDENTIALS_PATH", tmp_path / "credentials.toml")
    base_module.save_token("http://localhost:4321", "test-token")


STAMP = {"createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-02T00:00:00Z"}


def sent_body(op: Write, answer: dict) -> tuple[dict, list]:
    """
    The JSON body `run_plan` sends for `op`, and the results it yields.
    """
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=answer)

    client = httpx.Client(
        base_url="http://localhost:4321", transport=httpx.MockTransport(handler)
    )
    results = list(
        run_plan([op], discipline="cs101", course="ada_2026-1", client=client)
    )
    assert len(bodies) == 1, results
    return bodies[0], results


def test_a_time_slot_is_sent_with_its_duration_carried_into_hours():
    slot = TimeSlot("lab", "MONDAY", TimeOfDay(9, 0), Duration(0, 90), "Lab")
    answer = {
        "id": 1,
        "courseId": 1,
        "slug": "lab",
        "title": "Lab",
        "day": "MONDAY",
        "start": {"hour": 9, "minute": 0},
        "duration": {"hours": 1, "minutes": 30},
        **STAMP,
    }

    body, results = sent_body(UpsertTimeSlot(slot), answer)

    assert body == time_slot_payload(slot)
    assert results[0].updated_at == "2026-01-02T00:00:00Z"
    assert results[0].rev is None


def test_an_event_is_sent_with_its_repositories_sorted():
    event = Event(1, "mon", "Intro", "Text", repositories=("zeta", "alpha"))
    answer = {
        "kind": "REGULAR",
        "title": "Intro",
        "description": "Text",
        "startAt": "2026-01-05T00:00:00Z",
        "week": 1,
        "timeSlot": {
            "slug": "mon",
            "day": "MONDAY",
            "start": {"hour": 14, "minute": 0},
            "duration": {"hours": 2, "minutes": 0},
        },
        "rev": "r-event",
        "repositories": [
            {"slug": "alpha", "title": "Alpha"},
            {"slug": "zeta", "title": "Zeta"},
        ],
        **STAMP,
    }

    body, results = sent_body(UpsertCalendarEvent(event), answer)

    assert body == {**event_payload(event), "rev": event.ref}
    assert (results[0].rev, results[0].updated_at) == (
        "r-event",
        "2026-01-02T00:00:00Z",
    )


def test_a_grade_column_is_sent_trimmed_and_ordered_by_username():
    column = GradeColumn("p1", " Test 1 ", "number", 0, (("zed", 7), ("amy", 9.5)))
    answer = {
        "slug": "p1",
        "title": "Test 1",
        "kind": "NUMBER",
        "position": 0,
        "rev": column.rev,
        "releasedAt": None,
        "values": [{"username": "amy", "value": 9.5}, {"username": "zed", "value": 7}],
        **STAMP,
    }

    body, results = sent_body(UpsertGradeColumn(column), answer)

    assert body == {**grade_column_payload(column), "rev": column.rev}
    assert results[0].rev == column.rev
