"""In-memory room registry with idle cleanup and authoritative timers."""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Dict, List, Optional

from .game import GameError, Phase
from .models import Room
from .security import generate_room_code, generate_token

# Rooms idle for longer than this are garbage-collected.
INACTIVITY_TIMEOUT_SECONDS = 2 * 60 * 60  # 2 hours


class RoomManager:
    def __init__(self, inactivity_timeout: int = INACTIVITY_TIMEOUT_SECONDS) -> None:
        self.rooms: Dict[str, Room] = {}
        self.inactivity_timeout = inactivity_timeout

    # -- lifecycle -----------------------------------------------------
    def create_room(self) -> Room:
        code = generate_room_code()
        while code in self.rooms:
            code = generate_room_code()
        room = Room(
            code=code,
            host_token=generate_token(),
            last_activity=time.time(),
        )
        self.rooms[code] = room
        return room

    def get(self, code: str) -> Optional[Room]:
        return self.rooms.get(code)

    def get_or_error(self, code: str) -> Room:
        room = self.rooms.get(code)
        if room is None:
            raise GameError("Room not found.", status_code=404)
        return room

    def delete(self, code: str) -> None:
        room = self.rooms.pop(code, None)
        if room is not None:
            self.cancel_timer(room)

    def touch(self, room: Room) -> None:
        room.last_activity = time.time()

    # -- timers --------------------------------------------------------
    def schedule_timer(
        self,
        room: Room,
        delay_seconds: float,
        on_expire: Callable[[str], Awaitable[None]],
    ) -> None:
        """Schedule the authoritative investigation expiry for ``room``."""
        self.cancel_timer(room)

        async def _runner() -> None:
            try:
                await asyncio.sleep(max(0.0, delay_seconds))
                await on_expire(room.code)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Never let a timer crash the server.
                pass

        room.timer_task = asyncio.create_task(_runner())

    def cancel_timer(self, room: Room) -> None:
        task = getattr(room, "timer_task", None)
        if task is not None and not task.done():
            task.cancel()
        room.timer_task = None

    # -- cleanup -------------------------------------------------------
    def cleanup_expired(self, now: Optional[float] = None) -> List[str]:
        now = now if now is not None else time.time()
        expired = [
            code
            for code, room in self.rooms.items()
            if now - room.last_activity > self.inactivity_timeout
        ]
        for code in expired:
            self.delete(code)
        return expired

    def reset_room_for_new_game(self, room: Room) -> None:
        """Host-triggered reset of fact collection (clears facts/assignments)."""
        self.cancel_timer(room)
        for player in room.players.values():
            player.fact = None
            player.submitted = False
            player.guess = None
            player.guessed = False
        room.assignments = {}
        room.investigation_started_at = None
        room.investigation_ends_at = None
        if room.state not in (Phase.LOBBY, Phase.FACT_COLLECTION):
            room.state = Phase.FACT_COLLECTION


__all__ = ["RoomManager", "INACTIVITY_TIMEOUT_SECONDS"]
