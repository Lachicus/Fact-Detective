"""Pure game rules: phases, derangement assignment and validation.

This module has no I/O so it can be unit-tested directly.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional


class Phase:
    LOBBY = "LOBBY"
    FACT_COLLECTION = "FACT_COLLECTION"
    READY = "READY"
    ASSIGNMENT = "ASSIGNMENT"
    INVESTIGATION = "INVESTIGATION"
    GUESSING = "GUESSING"
    REVEAL = "REVEAL"
    FINISHED = "FINISHED"


ALL_PHASES = [
    Phase.LOBBY,
    Phase.FACT_COLLECTION,
    Phase.READY,
    Phase.ASSIGNMENT,
    Phase.INVESTIGATION,
    Phase.GUESSING,
    Phase.REVEAL,
    Phase.FINISHED,
]

FACT_MAX_LENGTH = 500
FACT_MIN_LENGTH = 1
INVESTIGATION_MIN_MINUTES = 3
INVESTIGATION_MAX_MINUTES = 30
INVESTIGATION_DEFAULT_MINUTES = 10

MIN_PLAYERS = 2
MAX_PLAYERS = 30

POINTS_PER_CORRECT_GUESS = 1

# The host may only remove players while the round has not been assigned yet.
# Afterwards every player owns an assignment, so removing one would invalidate
# the derangement for everybody else.
PLAYER_MANAGEMENT_PHASES = frozenset({Phase.LOBBY, Phase.FACT_COLLECTION, Phase.READY})


class GameError(Exception):
    """Raised for invalid, user-correctable game actions."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def generate_derangement(player_ids: List[str], rng: Optional[random.Random] = None) -> Dict[str, str]:
    """Return a derangement mapping ``giver_id -> receiver_id``.

    Each giver is assigned exactly one *other* player's fact, and every player
    appears exactly once as a receiver. No player is assigned their own fact.

    Works for any ``len(player_ids) >= 2``. Raises ``GameError`` if impossible.
    """
    ids = list(player_ids)
    n = len(ids)
    if n < 2:
        raise GameError("At least 2 participants are required for an assignment.")
    if len(set(ids)) != n:
        raise GameError("Participant ids must be unique.")

    rng = rng or random.SystemRandom()

    # Retry-based shuffle: for n >= 2 the expected number of tries is small
    # (e^-1 chance of a valid permutation per shuffle), and this guarantees a
    # uniform derangement.
    for _ in range(10_000):
        receivers = ids[:]
        rng.shuffle(receivers)
        if all(giver != receiver for giver, receiver in zip(ids, receivers)):
            return {giver: receiver for giver, receiver in zip(ids, receivers)}

    # Deterministic fallback (rotation): always a valid derangement for n >= 2.
    return {ids[i]: ids[(i + 1) % n] for i in range(n)}


def validate_assignment(mapping: Dict[str, str], player_ids: List[str]) -> None:
    """Raise ``GameError`` unless ``mapping`` is a valid derangement."""
    ids = set(player_ids)
    if set(mapping.keys()) != ids:
        raise GameError("Assignment must cover every participant exactly once.")
    receivers = list(mapping.values())
    if len(receivers) != len(set(receivers)):
        raise GameError("Each fact must be assigned to exactly one participant.")
    if set(receivers) != ids:
        raise GameError("Assignment receivers must be the same set of participants.")
    for giver, receiver in mapping.items():
        if giver == receiver:
            raise GameError("A participant cannot receive their own fact.")


# Valid forward transitions. READY is reached automatically when all facts are in.
VALID_TRANSITIONS = {
    Phase.LOBBY: {Phase.FACT_COLLECTION},
    Phase.FACT_COLLECTION: {Phase.READY, Phase.LOBBY},
    Phase.READY: {Phase.FACT_COLLECTION, Phase.ASSIGNMENT, Phase.INVESTIGATION},
    Phase.ASSIGNMENT: {Phase.INVESTIGATION},
    Phase.INVESTIGATION: {Phase.GUESSING},
    Phase.GUESSING: {Phase.REVEAL},
    Phase.REVEAL: {Phase.FINISHED},
    Phase.FINISHED: set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())


def assert_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise GameError(f"Invalid phase transition: {current} -> {target}.")


def sanitize_fact(raw: Optional[str]) -> str:
    """Trim and validate a submitted fact."""
    fact = (raw or "").strip()
    if len(fact) < FACT_MIN_LENGTH:
        raise GameError("Fact cannot be empty.")
    if len(fact) > FACT_MAX_LENGTH:
        raise GameError(f"Fact is too long (max {FACT_MAX_LENGTH} characters).")
    return fact


def sanitize_name(raw: Optional[str]) -> str:
    name = (raw or "").strip()
    if not name:
        raise GameError("Display name is required.")
    if len(name) > 40:
        raise GameError("Display name is too long (max 40 characters).")
    return name


def clamp_investigation_minutes(raw: Optional[int]) -> int:
    if raw is None:
        return INVESTIGATION_DEFAULT_MINUTES
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        raise GameError("Investigation duration must be a whole number of minutes.")
    if not (INVESTIGATION_MIN_MINUTES <= minutes <= INVESTIGATION_MAX_MINUTES):
        raise GameError(
            f"Investigation duration must be between "
            f"{INVESTIGATION_MIN_MINUTES} and {INVESTIGATION_MAX_MINUTES} minutes."
        )
    return minutes


def can_remove_players(phase: str) -> bool:
    """Whether the host may still remove a participant from the room."""
    return phase in PLAYER_MANAGEMENT_PHASES


def is_correct_guess(guess_id: Optional[str], owner_id: Optional[str]) -> bool:
    """A guess is correct when it names the owner of the assigned fact."""
    return bool(guess_id) and bool(owner_id) and guess_id == owner_id


def points_for(correct: bool) -> int:
    return POINTS_PER_CORRECT_GUESS if correct else 0


def rank_scores(points: Dict[str, int]) -> Dict[str, int]:
    """Rank players by score, 1 being best.

    Ties share a place and the next place is skipped (1, 1, 3), so a tie never
    looks like a win over the player below it.
    """
    ordered = sorted(points.items(), key=lambda item: (-item[1], item[0]))
    ranks: Dict[str, int] = {}
    previous_value: Optional[int] = None
    previous_rank = 0
    for position, (player_id, value) in enumerate(ordered, start=1):
        rank = previous_rank if value == previous_value else position
        ranks[player_id] = rank
        previous_value = value
        previous_rank = rank
    return ranks


__all__ = [
    "Phase",
    "ALL_PHASES",
    "FACT_MAX_LENGTH",
    "FACT_MIN_LENGTH",
    "INVESTIGATION_MIN_MINUTES",
    "INVESTIGATION_MAX_MINUTES",
    "INVESTIGATION_DEFAULT_MINUTES",
    "MIN_PLAYERS",
    "MAX_PLAYERS",
    "POINTS_PER_CORRECT_GUESS",
    "PLAYER_MANAGEMENT_PHASES",
    "GameError",
    "generate_derangement",
    "validate_assignment",
    "VALID_TRANSITIONS",
    "can_transition",
    "assert_transition",
    "sanitize_fact",
    "sanitize_name",
    "clamp_investigation_minutes",
    "can_remove_players",
    "is_correct_guess",
    "points_for",
    "rank_scores",
]
