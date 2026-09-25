"""Request/response schemas (only requests strictly need validation)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CreateRoomRequest(BaseModel):
    pass


class JoinRoomRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)


class SubmitFactRequest(BaseModel):
    token: str
    fact: str = Field(..., min_length=1, max_length=500)


class StartGameRequest(BaseModel):
    token: str
    investigation_minutes: int = 10


class GuessRequest(BaseModel):
    token: str
    target_id: str


class HostActionRequest(BaseModel):
    token: str
    action: Optional[str] = None
    target_id: Optional[str] = None


class EndGameRequest(BaseModel):
    token: str


__all__ = [
    "CreateRoomRequest",
    "JoinRoomRequest",
    "SubmitFactRequest",
    "StartGameRequest",
    "GuessRequest",
    "HostActionRequest",
    "EndGameRequest",
]
