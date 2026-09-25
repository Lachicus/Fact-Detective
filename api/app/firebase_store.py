"""Firebase Realtime Database-backed room store (production).

Layout::

    /rooms/{code}/data   ... the serialized Room
    /rooms/{code}/_rev   ... monotonically increasing revision counter

Browsers subscribe (read-only) to ``_rev`` and re-fetch their rendered view
whenever it changes. All writes happen here, server-side, through the Admin SDK,
so security rules can deny all client writes and all client reads except
``_rev``.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from . import config
from .models import Room
from .security import generate_room_code, generate_token


class FirebaseStore:
    def __init__(self) -> None:
        self._init_app()
        self.root = "/rooms"

    # -- admin sdk bootstrap -------------------------------------------
    def _init_app(self) -> None:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            return

        settings = config.settings
        if settings.firebase_service_account:
            cred = credentials.Certificate(json.loads(settings.firebase_service_account))
        else:
            # Falls back to GOOGLE_APPLICATION_CREDENTIALS / metadata server.
            cred = credentials.ApplicationDefault()

        firebase_admin.initialize_app(cred, {"databaseURL": settings.firebase_database_url})

    # -- helpers -------------------------------------------------------
    def _ref(self, code: str):
        from firebase_admin import db

        return db.reference(f"{self.root}/{code}")

    def _is_expired(self, room: Room) -> bool:
        ttl = config.settings.room_ttl_seconds
        return bool(ttl) and (time.time() - room.last_activity > ttl)

    # -- RoomStore interface -------------------------------------------
    def create_room(self) -> Room:
        ref = None
        code = generate_room_code()
        for _ in range(30):
            code = generate_room_code()
            ref = self._ref(code)
            if not ref.get():
                break
        assert ref is not None
        room = Room(code=code, host_token=generate_token(), last_activity=time.time())
        ref.child("data").set(room.to_dict())
        ref.child("_rev").set(0)
        return room

    def get(self, code: str) -> Optional[Room]:
        snapshot = self._ref(code).get()
        if not snapshot:
            return None
        data = snapshot.get("data")
        if not data:
            return None
        room = Room.from_dict(data)
        if self._is_expired(room):
            self.delete(code)
            return None
        return room

    def save(self, room: Room) -> None:
        room.touch()
        ref = self._ref(room.code)
        ref.child("data").set(room.to_dict())
        ref.child("_rev").transaction(lambda current: (current or 0) + 1)

    def delete(self, code: str) -> None:
        self._ref(code).delete()

    def get_rev(self, code: str) -> int:
        value = self._ref(code).child("_rev").get()
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0


__all__ = ["FirebaseStore"]
