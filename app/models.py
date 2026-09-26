"""Domain models with Realtime Database (de)serialization.

The store owns persistence. These dataclasses are the in-memory shape and know
how to round-trip to/from plain JSON-compatible dicts (RTDB stores JSON).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .game import FACT_MAX_LENGTH, GameError, Phase, generate_derangement
from .security import generate_id, generate_token


@dataclass
class Player:
    id: str
    name: str
    token: str
    fact: Optional[str] = None
    submitted: bool = False
    guess: Optional[str] = None
    guessed: bool = False

    # -- serialization -------------------------------------------------
    def public_dict(self) -> dict:
        """Safe for *any* participant to know about another participant."""
        return {
            "id": self.id,
            "name": self.name,
            "submitted": self.submitted,
            "guessed": self.guessed,
        }

    def host_dict(self) -> dict:
        """Host-only view. The host runs the game and may see everything."""
        return {
            "id": self.id,
            "name": self.name,
            "fact": self.fact,
            "submitted": self.submitted,
            "guess": self.guess,
            "guessed": self.guessed,
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "token": self.token,
            "fact": self.fact,
            "submitted": self.submitted,
            "guess": self.guess,
            "guessed": self.guessed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Player":
        return cls(
            id=d["id"],
            name=d["name"],
            token=d["token"],
            fact=d.get("fact"),
            submitted=bool(d.get("submitted")),
            guess=d.get("guess"),
            guessed=bool(d.get("guessed")),
        )


@dataclass
class Room:
    code: str
    host_token: str
    state: str = Phase.LOBBY
    players: Dict[str, Player] = field(default_factory=dict)
    # token -> player_id, so we can resolve a session token to a player.
    tokens: Dict[str, str] = field(default_factory=dict)
    # player_id -> owner player_id whose fact this player received.
    assignments: Dict[str, str] = field(default_factory=dict)
    # Player ids whose reveal has been shown to them (supports one-at-a-time reveals).
    revealed_players: List[str] = field(default_factory=list)
    investigation_minutes: int = 10
    investigation_started_at: Optional[float] = None
    investigation_ends_at: Optional[float] = None
    # Wall-clock timestamp used for lazy idle cleanup on serverless.
    last_activity: float = 0.0
    # Set when the host closes the session (participants see an "ended" screen).
    ended: bool = False

    # -- helpers -------------------------------------------------------
    def player_by_token(self, token: Optional[str]) -> Optional[Player]:
        if not token:
            return None
        pid = self.tokens.get(token)
        if not pid:
            return None
        return self.players.get(pid)

    def is_host(self, token: Optional[str]) -> bool:
        return bool(token) and token == self.host_token

    def facts_submitted_count(self) -> int:
        return sum(1 for p in self.players.values() if p.submitted)

    def all_facts_submitted(self) -> bool:
        return bool(self.players) and all(p.submitted for p in self.players.values())

    def guesses_count(self) -> int:
        return sum(1 for p in self.players.values() if p.guessed)

    def all_guessed(self) -> bool:
        return bool(self.players) and all(p.guessed for p in self.players.values())

    def all_revealed(self) -> bool:
        return bool(self.players) and all(pid in self.revealed_players for pid in self.players)

    def add_player(self, name: str) -> Player:
        player = Player(id=generate_id(), name=name, token=generate_token())
        self.players[player.id] = player
        self.tokens[player.token] = player.id
        return player

    def remove_player(self, player_id: str) -> Player:
        """Remove a participant and every trace of them from the room.

        Their session token stops resolving, so a kicked player is bounced back
        to the landing page on their next request.
        """
        player = self.players.pop(player_id, None)
        if player is None:
            raise GameError("Unknown participant.")
        self.tokens.pop(player.token, None)
        # Drop the kicked player from the assignment map on both sides, so the
        # remaining mapping never points at somebody who is no longer here.
        self.assignments.pop(player_id, None)
        for giver_id, owner_id in list(self.assignments.items()):
            if owner_id == player_id:
                del self.assignments[giver_id]
        if player_id in self.revealed_players:
            self.revealed_players.remove(player_id)
        return player

    def restart_session(self) -> None:
        """Empty the room back to a fresh lobby, keeping code and host token.

        Used by the host to start over: every participant has to re-join.
        """
        self.players.clear()
        self.tokens.clear()
        self.assignments.clear()
        self.revealed_players.clear()
        self.investigation_started_at = None
        self.investigation_ends_at = None
        self.ended = False
        self.state = Phase.LOBBY

    def reveal_everyone(self) -> None:
        self.revealed_players = list(self.players.keys())

    def create_derangement_map(self) -> Dict[str, str]:
        """Assign every player someone else's fact (see ``game.generate_derangement``)."""
        ids = list(self.players.keys())
        mapping = generate_derangement(ids)
        self.assignments = mapping
        return mapping

    def touch(self) -> None:
        self.last_activity = time.time()

    # -- serialization -------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "host_token": self.host_token,
            "state": self.state,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "tokens": dict(self.tokens),
            "assignments": dict(self.assignments),
            "revealed_players": list(self.revealed_players),
            "investigation_minutes": self.investigation_minutes,
            "investigation_started_at": self.investigation_started_at,
            "investigation_ends_at": self.investigation_ends_at,
            "last_activity": self.last_activity,
            "ended": self.ended,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Room":
        players = {
            pid: Player.from_dict(pdata)
            for pid, pdata in (d.get("players") or {}).items()
        }
        return cls(
            code=d["code"],
            host_token=d["host_token"],
            state=d.get("state", Phase.LOBBY),
            players=players,
            tokens=dict(d.get("tokens") or {}),
            assignments=dict(d.get("assignments") or {}),
            revealed_players=list(d.get("revealed_players") or []),
            investigation_minutes=int(d.get("investigation_minutes") or 10),
            investigation_started_at=d.get("investigation_started_at"),
            investigation_ends_at=d.get("investigation_ends_at"),
            last_activity=float(d.get("last_activity") or 0.0),
            ended=bool(d.get("ended")),
        )


__all__ = ["Player", "Room", "FACT_MAX_LENGTH"]
