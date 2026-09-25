"""Room store abstraction.

Two backends implement the same tiny interface:

* :class:`~app.memory_store.MemoryStore`   - in-process, for dev/tests.
* :class:`~app.firebase_store.FirebaseStore` - Firebase Realtime Database.

The interface is intentionally minimal: the room is the unit of atomicity, and
``save`` also publishes a monotonically increasing revision that browsers watch
to know when to re-fetch their rendered view.
"""

from __future__ import annotations

from typing import Optional, Protocol

from . import config
from .models import Room


class RoomStore(Protocol):
    def create_room(self) -> Room: ...
    def get(self, code: str) -> Optional[Room]: ...
    def save(self, room: Room) -> None: ...
    def delete(self, code: str) -> None: ...
    def get_rev(self, code: str) -> int: ...


_store: Optional[RoomStore] = None


def get_store() -> RoomStore:
    """Return the process-wide store, chosen from configuration."""
    global _store
    if _store is None:
        backend = config.settings.resolved_store_backend()
        if backend == "firebase":
            from .firebase_store import FirebaseStore

            _store = FirebaseStore()
        else:
            from .memory_store import MemoryStore

            _store = MemoryStore()
    return _store


def reset_store() -> None:
    """Test hook: forget the cached store so a new backend is built."""
    global _store
    _store = None


__all__ = ["RoomStore", "get_store", "reset_store"]
