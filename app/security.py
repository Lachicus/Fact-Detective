"""Temporary session authentication helpers.

No accounts, no passwords: rooms are ephemeral events. We only issue
cryptographically random opaque tokens that map back to server-side state.
"""

from __future__ import annotations

import secrets
import string

# Ambiguous characters (0/O, 1/I/L) removed so codes are easy to read aloud.
_ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_ROOM_CODE_LENGTH = 5


def generate_room_code() -> str:
    """Return a short, human-friendly room code such as ``K7PX2``."""
    return "".join(secrets.choice(_ROOM_CODE_ALPHABET) for _ in range(_ROOM_CODE_LENGTH))


def generate_token() -> str:
    """Return a cryptographically secure URL-safe session token."""
    return secrets.token_urlsafe(32)


def generate_id() -> str:
    """Return a short random identifier used internally for entities."""
    return secrets.token_hex(8)


def normalize_room_code(room_code: str) -> str:
    """Normalize user input for room-code lookup."""
    return (room_code or "").strip().upper()


__all__ = [
    "generate_room_code",
    "generate_token",
    "generate_id",
    "normalize_room_code",
    "string",
]
