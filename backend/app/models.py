"""In-memory domain models.

Everything lives in the FastAPI process. There is intentionally no database:
if the process restarts, the game is gone. That is acceptable for a one-off
team activity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from .game import FACT_MAX_LENGTH, Phase
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
    connected: bool = False
    websocket: object = field(default=None, repr=False, compare=False)

    # -- serialization -------------------------------------------------
    def public_dict(self) -> dict:
        """Safe for *any* participant to know about another participant."""
        return {
            "id": self.id,
            "name": self.name,
            "submitted": self.submitted,
            "guessed": self.guessed,
            "connected": self.connected,
        }

    def self_dict(self) -> dict:
        """A participant's private view of themselves (never their own fact)."""
        return {
            "id": self.id,
            "name": self.name,
            "submitted": self.submitted,
            "guessed": self.guessed,
            "fact_length": len(self.fact) if self.fact else 0,
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
            "connected": self.connected,
        }


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
    revealed_players: set = field(default_factory=set)
    investigation_minutes: int = 10
    investigation_started_at: Optional[float] = None
    investigation_ends_at: Optional[float] = None
    # Monotonic-ish wall clock timestamp for idle cleanup.
    last_activity: float = field(default=0.0)
    # Runtime-only handle for the authoritative timer task (never serialized).
    timer_task: object = field(default=None, repr=False, compare=False)

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

    def add_player(self, name: str) -> Player:
        player = Player(id=generate_id(), name=name, token=generate_token())
        self.players[player.id] = player
        self.tokens[player.token] = player.id
        return player

    def create_derangement_map(self) -> Dict[str, str]:
        """Assign every player someone else's fact (see ``game.generate_derangement``)."""
        from .game import generate_derangement

        ids = list(self.players.keys())
        mapping = generate_derangement(ids)
        # mapping: giver_id -> receiver_id (giver assigned the receiver's fact).
        # We store it as: player_id -> owner_id whose fact they received.
        self.assignments = mapping
        return mapping


__all__ = ["Player", "Room", "FACT_MAX_LENGTH"]
