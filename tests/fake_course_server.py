"""
Test helper: a stateful fake of one course on the Codehood server.

It answers the endpoints `ch push` reads and writes from a dict per entity
kind, so a second push sees what the first one stored. Each stored entity
carries the `rev` it was sent with and an `updatedAt` from a counter.
`edit` changes an entity the way the web would: new content and a newer
`updatedAt`, same `rev`.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx

DISCIPLINE = "cs101"
COURSE = "ada_2026-1"
BASE = f"/api/course/{DISCIPLINE}/{COURSE}"
COLLECTION = "/api/course"

__all__ = ["BASE", "COLLECTION", "FakeCourseServer"]


class FakeCourseServer:
    """
    The server side of a push, kept in memory.
    """

    def __init__(self) -> None:
        self.course: dict | None = None
        self.resources: dict[str, dict] = {}
        self.time_slots: dict[str, dict] = {}
        self.events: dict[tuple[int, str], dict] = {}
        self.calls: list[tuple[str, str]] = []
        #: Paths whose write answers 500.
        self.failing: set[str] = set()
        self.clock = 0

    def tick(self) -> str:
        self.clock += 1
        return f"2026-02-01T00:00:{self.clock:02d}Z"

    @property
    def writes(self) -> list[tuple[str, str]]:
        return [call for call in self.calls if call[0] != "GET"]

    def edit(self, kind: str, key: str | tuple[int, str], **changes) -> None:
        """
        Change an entity as the web does: its `rev` stays, `updatedAt` moves.
        """
        entity = getattr(self, kind)[key]
        entity.update(changes)
        entity["updatedAt"] = self.tick()

    def create_resource(self, slug: str, **changes) -> None:
        """
        A resource that only the server knows.
        """
        self.resources[slug] = {
            "slug": slug,
            "title": slug,
            "description": None,
            "data": {"type": "MD", "content": "web"},
            "event": None,
            "rev": "web",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": self.tick(),
            **changes,
        }

    def transport(self) -> Callable[[httpx.Request], httpx.Response]:
        return self.handle

    def handle(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.calls.append((method, path))
        if method != "GET" and path in self.failing:
            return httpx.Response(500, json={"message": "boom"})
        if path == COLLECTION and method == "PUT":
            return self.put_course(json.loads(request.content))
        if path == BASE and method == "GET":
            if self.course is None:
                return httpx.Response(404, json={"message": "not found"})
            return httpx.Response(200, json=self.course)
        if method == "GET" and path in (
            f"{BASE}/question",
            f"{BASE}/grade-column",
            f"{BASE}/roll-call",
            f"{BASE}/repository",
        ):
            return httpx.Response(200, json=[])
        if path == f"{BASE}/resource":
            return self.resource_collection(request)
        if path == f"{BASE}/time-slot":
            return self.time_slot_collection(request)
        if path == f"{BASE}/calendar-event":
            return self.event_collection(request)
        if method == "DELETE":
            return self.delete(path)
        raise AssertionError(f"unexpected request: {method} {path}")

    def put_course(self, body: dict) -> httpx.Response:
        from test_cli_push import _course_json

        self.course = _course_json(
            description=body["description"],
            startAt=body["startAt"],
            endAt=body["endAt"],
            rev=body["rev"],
            updatedAt=self.tick(),
        )
        return httpx.Response(200, json=self.course)

    def resource_collection(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=list(self.resources.values()))
        body = json.loads(request.content)
        stored = {
            "createdAt": "2026-01-01T00:00:00Z",
            **body,
            "updatedAt": self.tick(),
        }
        self.resources[body["slug"]] = stored
        return httpx.Response(200, json=stored)

    def time_slot_collection(self, request: httpx.Request) -> httpx.Response:
        from test_cli_push import _timeslot_json

        if request.method == "GET":
            return httpx.Response(200, json=list(self.time_slots.values()))
        body = json.loads(request.content)
        stored = _timeslot_json(
            body["slug"],
            title=body["title"],
            day=body["day"],
            start=body["start"],
            duration=body["duration"],
            updatedAt=self.tick(),
        )
        self.time_slots[body["slug"]] = stored
        return httpx.Response(200, json=stored)

    def event_collection(self, request: httpx.Request) -> httpx.Response:
        from test_cli_push import _calendar_event_json

        if request.method == "GET":
            return httpx.Response(200, json=list(self.events.values()))
        body = json.loads(request.content)
        slot = self.time_slots.get(body["timeSlot"])
        stored = _calendar_event_json(
            body["week"],
            body["timeSlot"],
            kind=body["kind"],
            title=body["title"],
            description=body["description"],
            rev=body["rev"],
            repositories=body["repositories"],
            updatedAt=self.tick(),
        )
        if slot is not None:
            stored["timeSlot"] = {
                key: slot[key] for key in ("slug", "day", "start", "duration")
            }
        self.events[(body["week"], body["timeSlot"])] = stored
        return httpx.Response(200, json=stored)

    def delete(self, path: str) -> httpx.Response:
        parts = path.removeprefix(BASE + "/").split("/")
        if parts[0] == "resource":
            self.resources.pop(parts[1], None)
        elif parts[0] == "time-slot":
            self.time_slots.pop(parts[1], None)
        elif parts[0] == "calendar-event":
            self.events.pop((int(parts[1]), parts[2]), None)
        return httpx.Response(
            200, json={"success": True, "message": "deleted", "deleted": True}
        )
