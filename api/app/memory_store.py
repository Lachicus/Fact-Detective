"""In-process room store for local development and the test suite.

Not suitable for production on serverless: each instance would keep its own
copy of the rooms. Production uses :class:`app.firebase_store.FirebaseStore`.
"""

from __future__ import annotations

import time
from typing import Dict, Optional

from . import config
from .models import Room
from .security import generate_room_code, generate_token

_UNSET = object()


class MemoryStore:
    def __init__(self, ttl_seconds: int | None = None) -> None:
        self.rooms: Dict[str, Room] = {}
        self.revs: Dict[str, int] = {}
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else config.settings.room_ttl_seconds

    def create_room(self) -> Room:
        code = generate_room_code()
        while code in self.rooms:
            code = generate_room_code()
        room = Room(code=code, host_token=generate_token(), last_activity=time.time())
        self.rooms[code] = room
        self.revs[code] = 0
        return room

    def get(self, code: str) -> Optional[Room]:
        room = self.rooms.get(code)
        if room is None:
            return None
        if self.ttl_seconds and time.time() - room.last_activity > self.ttl_seconds:
            self.delete(code)
            return None
        return room

    def save(self, room: Room) -> None:
        room.touch()
        self.rooms[room.code] = room
        self.revs[room.code] = self.revs.get(room.code, 0) + 1

    def delete(self, code: str) -> None:
        self.rooms.pop(code, None)
        self.revs.pop(code, None)

    def get_rev(self, code: str) -> int:
        return self.revs.get(code, 0)


__all__ = ["MemoryStore", "_UNSET"]
