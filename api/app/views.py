"""Authorized view contexts.

Authorization happens here, never in the client. A participant's context is
built so that it *cannot* contain another player's fact or the owner identity
before the reveal; the host context is the only full view.
"""

from __future__ import annotations

import time
from typing import Optional

from .game import Phase
from .models import Player, Room

PHASE_LABELS = {
    Phase.LOBBY: "Lobby",
    Phase.FACT_COLLECTION: "Fact Collection",
    Phase.READY: "Ready",
    Phase.ASSIGNMENT: "Assigning…",
    Phase.INVESTIGATION: "Investigation",
    Phase.GUESSING: "Guessing",
    Phase.REVEAL: "Reveal",
    Phase.FINISHED: "Finished",
}


def investigation_payload(room: Room) -> Optional[dict]:
    if room.investigation_ends_at is None:
        return None
    return {
        "started_at": room.investigation_started_at,
        "ends_at": room.investigation_ends_at,
        "duration_seconds": room.investigation_minutes * 60,
        "server_now": time.time(),
    }


def assignment_for(room: Room, player: Player) -> Optional[dict]:
    """The only place a participant ever receives a fact.

    Deliberately excludes the owner id before the reveal.
    """
    if room.state not in (Phase.INVESTIGATION, Phase.GUESSING, Phase.REVEAL):
        return None
    owner_id = room.assignments.get(player.id)
    if not owner_id:
        return None
    owner = room.players.get(owner_id)
    if owner is None or owner.fact is None:
        return None
    return {"fact": owner.fact}


def reveal_for(room: Room, player: Player) -> Optional[dict]:
    """Personalized reveal, only once the host has revealed this player."""
    if room.state not in (Phase.REVEAL, Phase.FINISHED):
        return None
    if player.id not in room.revealed_players:
        return None
    owner_id = room.assignments.get(player.id)
    owner = room.players.get(owner_id) if owner_id else None
    guessed_owner = room.players.get(player.guess) if player.guess else None
    correct = bool(owner_id) and player.guess == owner_id
    return {
        "fact": owner.fact if owner else None,
        "owner_id": owner_id,
        "owner_name": owner.name if owner else None,
        "your_guess_id": player.guess,
        "your_guess_name": guessed_owner.name if guessed_owner else None,
        "correct": correct,
    }


def _base(room: Room, role: str) -> dict:
    return {
        "role": role,
        "phase": room.state,
        "phase_label": PHASE_LABELS.get(room.state, room.state),
        "room_code": room.code,
        "ended": room.ended,
        "players": [p.public_dict() for p in room.players.values()],
        "facts_submitted": room.facts_submitted_count(),
        "facts_total": len(room.players),
        "guesses_submitted": room.guesses_count(),
        "investigation": investigation_payload(room),
        "server_now": time.time(),
    }


def participant_context(room: Room, player: Player) -> dict:
    """Authorized context for a single participant."""
    ctx = _base(room, "participant")
    ctx.update(
        {
            "you": {
                "id": player.id,
                "name": player.name,
                "submitted": player.submitted,
                "guessed": player.guessed,
            },
            "assignment": assignment_for(room, player),
            "reveal": reveal_for(room, player),
            "revealed_count": len(room.revealed_players),
        }
    )
    return ctx


def host_context(room: Room) -> dict:
    """Authorized context for the host (host may see everything)."""
    assignments_view = []
    for giver_id, owner_id in room.assignments.items():
        giver = room.players.get(giver_id)
        owner = room.players.get(owner_id)
        if giver and owner:
            assignments_view.append(
                {
                    "giver_id": giver.id,
                    "giver_name": giver.name,
                    "owner_id": owner.id,
                    "owner_name": owner.name,
                    "fact": owner.fact,
                }
            )
    ctx = _base(room, "host")
    ctx.update(
        {
            "host_players": [p.host_dict() for p in room.players.values()],
            "investigation_minutes": room.investigation_minutes,
            "assignments": assignments_view,
            "revealed_players": sorted(room.revealed_players),
        }
    )
    return ctx


def context_for(room: Room, role: str, player: Optional[Player]) -> dict:
    if role == "host":
        return host_context(room)
    assert player is not None
    return participant_context(room, player)


__all__ = [
    "PHASE_LABELS",
    "investigation_payload",
    "assignment_for",
    "reveal_for",
    "participant_context",
    "host_context",
    "context_for",
]
