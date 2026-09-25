"""WebSocket connection registry and message delivery."""

from __future__ import annotations

import asyncio
import json
from typing import Dict, Optional

from fastapi import WebSocket

from .models import Room


class ConnectionManager:
    """Tracks live sockets keyed by ``player_id`` (or ``host``)."""

    HOST_KEY = "__host__"

    def __init__(self) -> None:
        # room_code -> {sender_key: WebSocket}
        self._connections: Dict[str, Dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_code: str, sender_key: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(room_code, {})[sender_key] = websocket

    async def disconnect(self, room_code: str, sender_key: str) -> None:
        async with self._lock:
            room = self._connections.get(room_code)
            if room:
                room.pop(sender_key, None)
                if not room:
                    self._connections.pop(room_code, None)

    async def send(self, room_code: str, sender_key: str, payload: dict) -> None:
        async with self._lock:
            websocket = self._connections.get(room_code, {}).get(sender_key)
        if websocket is None:
            return
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception:
            # Socket died; the receive loop will clean it up.
            pass

    async def broadcast(self, room_code: str, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._connections.get(room_code, {}).values())
        data = json.dumps(payload)
        for websocket in sockets:
            try:
                await websocket.send_text(data)
            except Exception:
                pass

    def socket_count(self, room_code: str) -> int:
        return len(self._connections.get(room_code, {}))


manager = ConnectionManager()


def participant_key(player_id: str) -> str:
    return f"p:{player_id}"


__all__ = ["ConnectionManager", "manager", "participant_key", "Room", "Optional"]
