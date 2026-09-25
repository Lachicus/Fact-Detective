"""Private Fact Detective — FastAPI backend.

Single persistent process, in-memory state, WebSocket realtime events.
No database by design.
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Body, FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .game import (
    Phase,
    GameError,
    assert_transition,
    clamp_investigation_minutes,
    sanitize_fact,
    sanitize_name,
    validate_assignment,
    MIN_PLAYERS,
    MAX_PLAYERS,
)
from .models import Player, Room
from .rooms import RoomManager
from .schemas import (
    EndGameRequest,
    GuessRequest,
    HostActionRequest,
    JoinRoomRequest,
    StartGameRequest,
    SubmitFactRequest,
)
from .security import normalize_room_code
from .websocket import manager, participant_key

room_manager = RoomManager()

# How often the idle-room sweeper runs.
CLEANUP_INTERVAL_SECONDS = 10 * 60


# ---------------------------------------------------------------------------
# Serialization helpers (authorization happens here, not in the client)
# ---------------------------------------------------------------------------
def phase_payload(room: Room) -> dict:
    return {
        "type": "phase_change",
        "phase": room.state,
        "room_code": room.code,
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


def build_player_state(room: Room, player: Player) -> dict:
    """Authorized snapshot for a single participant."""
    reveal = reveal_for(room, player)
    return {
        "type": "state",
        "role": "participant",
        "room_code": room.code,
        "phase": room.state,
        "you": {
            "id": player.id,
            "name": player.name,
            "submitted": player.submitted,
            "guessed": player.guessed,
        },
        "players": [p.public_dict() for p in room.players.values()],
        "facts_submitted": room.facts_submitted_count(),
        "facts_total": len(room.players),
        "guesses_submitted": room.guesses_count(),
        "investigation": investigation_payload(room),
        "assignment": assignment_for(room, player),
        "reveal": reveal,
        "revealed_count": len(room.revealed_players),
        "server_now": time.time(),
    }


def build_host_state(room: Room) -> dict:
    """Authorized snapshot for the host (host may see everything)."""
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
    return {
        "type": "state",
        "role": "host",
        "room_code": room.code,
        "phase": room.state,
        "players": [p.host_dict() for p in room.players.values()],
        "facts_submitted": room.facts_submitted_count(),
        "facts_total": len(room.players),
        "guesses_submitted": room.guesses_count(),
        "investigation_minutes": room.investigation_minutes,
        "investigation": investigation_payload(room),
        "assignments": assignments_view,
        "revealed_players": sorted(room.revealed_players),
        "server_now": time.time(),
    }


async def push_states(room: Room) -> None:
    """Send every connected client the snapshot it is authorized to see."""
    await manager.send(room.code, manager.HOST_KEY, build_host_state(room))
    for player in room.players.values():
        await manager.send(
            room.code,
            participant_key(player.id),
            build_player_state(room, player),
        )


async def announce_phase(room: Room) -> None:
    await manager.broadcast(room.code, phase_payload(room))
    await push_states(room)


async def send_error(room_code: str, sender_key: str, message: str) -> None:
    await manager.send(room_code, sender_key, {"type": "error", "message": message})


# ---------------------------------------------------------------------------
# Timer handling (server-authoritative)
# ---------------------------------------------------------------------------
async def expire_investigation(room_code: str) -> None:
    room = room_manager.get(room_code)
    if room is None or room.state != Phase.INVESTIGATION:
        return
    room.state = Phase.GUESSING
    room_manager.touch(room)
    await announce_phase(room)


def schedule_investigation_timer(room: Room) -> None:
    delay = (room.investigation_ends_at or time.time()) - time.time()
    room_manager.schedule_timer(room, delay, expire_investigation)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
async def _cleanup_loop() -> None:
    while True:
        try:
            room_manager.cleanup_expired()
        except Exception:
            pass
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    app.state.cleanup_task = task
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Private Fact Detective", version="1.0.0", lifespan=lifespan)

_origins = os.environ.get("CORS_ALLOW_ORIGINS", "*")
allow_origins = ["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GameError)
async def game_error_handler(_: Request, exc: GameError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "rooms": len(room_manager.rooms)}


@app.post("/api/rooms")
async def create_room() -> dict:
    room = room_manager.create_room()
    return {
        "room_code": room.code,
        "host_token": room.host_token,
        "phase": room.state,
    }


@app.post("/api/rooms/{room_code}/join")
async def join_room(room_code: str, body: JoinRoomRequest) -> dict:
    code = normalize_room_code(room_code)
    room = room_manager.get_or_error(code)
    if room.state != Phase.LOBBY:
        raise GameError("This room is no longer accepting new players.")
    if len(room.players) >= MAX_PLAYERS:
        raise GameError("This room is full.")
    name = sanitize_name(body.name)
    if any(p.name.lower() == name.lower() for p in room.players.values()):
        raise GameError("That display name is already taken in this room.")
    player = room.add_player(name)
    room_manager.touch(room)
    await manager.broadcast(
        room.code,
        {
            "type": "player_joined",
            "player": player.public_dict(),
            "player_count": len(room.players),
        },
    )
    await push_states(room)
    return {
        "participant_id": player.id,
        "participant_token": player.token,
        "room_code": room.code,
        "phase": room.state,
    }


def _require_participant(room: Room, token: Optional[str]) -> Player:
    player = room.player_by_token(token)
    if player is None:
        raise GameError("Invalid participant session.", status_code=401)
    return player


def _require_host(room: Room, token: Optional[str]) -> None:
    if not room.is_host(token):
        raise GameError("Invalid host session.", status_code=403)


@app.post("/api/rooms/{room_code}/facts")
async def submit_fact(room_code: str, body: SubmitFactRequest) -> dict:
    code = normalize_room_code(room_code)
    room = room_manager.get_or_error(code)
    player = _require_participant(room, body.token)
    if room.state != Phase.FACT_COLLECTION:
        raise GameError("Facts can only be submitted during fact collection.")
    if player.submitted:
        raise GameError("You have already submitted a fact.")
    fact = sanitize_fact(body.fact)
    player.fact = fact
    player.submitted = True
    room_manager.touch(room)

    if room.all_facts_submitted() and len(room.players) >= MIN_PLAYERS:
        room.state = Phase.READY

    await manager.broadcast(
        room.code,
        {
            "type": "fact_submitted",
            "player": player.public_dict(),
            "facts_submitted": room.facts_submitted_count(),
            "facts_total": len(room.players),
        },
    )
    await announce_phase(room)
    return {"ok": True, "submitted": True}


@app.post("/api/rooms/{room_code}/guess")
async def submit_guess(room_code: str, body: GuessRequest) -> dict:
    code = normalize_room_code(room_code)
    room = room_manager.get_or_error(code)
    player = _require_participant(room, body.token)
    if room.state != Phase.GUESSING:
        raise GameError("Guesses can only be submitted during the guessing phase.")
    if player.guessed:
        raise GameError("You have already submitted a guess.")
    if body.target_id == player.id:
        raise GameError("You cannot guess yourself.")
    if body.target_id not in room.players:
        raise GameError("That participant is not in this room.")
    player.guess = body.target_id
    player.guessed = True
    room_manager.touch(room)

    # When everyone has guessed, move to the reveal phase automatically.
    if room.state == Phase.GUESSING and room.all_guessed():
        assert_transition(room.state, Phase.REVEAL)
        room.state = Phase.REVEAL

    await manager.broadcast(
        room.code,
        {
            "type": "guess_submitted",
            "player_id": player.id,
            "guesses_submitted": room.guesses_count(),
            "guesses_total": len(room.players),
        },
    )
    await push_states(room)
    return {"ok": True, "guessed": True}


@app.post("/api/rooms/{room_code}/start")
async def start_investigation(room_code: str, body: StartGameRequest) -> dict:
    code = normalize_room_code(room_code)
    room = room_manager.get_or_error(code)
    _require_host(room, body.token)
    _start_investigation(room, body.investigation_minutes)
    await announce_phase(room)
    return {"ok": True, "phase": room.state, "investigation": investigation_payload(room)}


def _start_investigation(room: Room, minutes: Optional[int]) -> None:
    if room.state not in (Phase.READY, Phase.FACT_COLLECTION):
        raise GameError("The investigation can only be started once facts are collected.")
    if len(room.players) < MIN_PLAYERS:
        raise GameError("At least 2 participants are required.")
    if not room.all_facts_submitted():
        raise GameError("Not everyone has submitted a fact yet.")

    # Validate everything before mutating room state, so a failed request
    # leaves the phase untouched.
    resolved_minutes = clamp_investigation_minutes(minutes)
    mapping = room.create_derangement_map()
    validate_assignment(mapping, list(room.players.keys()))

    assert_transition(room.state, Phase.ASSIGNMENT)
    room.state = Phase.ASSIGNMENT

    room.assignments = mapping
    room.investigation_minutes = resolved_minutes
    now = time.time()
    room.investigation_started_at = now
    room.investigation_ends_at = now + room.investigation_minutes * 60
    room.revealed_players = set()

    assert_transition(Phase.ASSIGNMENT, Phase.INVESTIGATION)
    room.state = Phase.INVESTIGATION
    room_manager.touch(room)
    schedule_investigation_timer(room)


@app.post("/api/rooms/{room_code}/end")
async def end_game(room_code: str, body: EndGameRequest) -> dict:
    code = normalize_room_code(room_code)
    room = room_manager.get_or_error(code)
    _require_host(room, body.token)
    room_manager.cancel_timer(room)
    room.state = Phase.FINISHED
    room_manager.touch(room)
    await announce_phase(room)
    return {"ok": True, "phase": room.state}


@app.post("/api/rooms/{room_code}/host/action")
async def host_action(room_code: str, body: HostActionRequest) -> dict:
    code = normalize_room_code(room_code)
    room = room_manager.get_or_error(code)
    _require_host(room, body.token)
    action = (body.action or "").strip()
    await _apply_host_action(room, action)
    return {"ok": True, "phase": room.state}


async def _apply_host_action(room: Room, action: str) -> None:
    if action == "start_fact_collection":
        assert_transition(room.state, Phase.FACT_COLLECTION)
        room.state = Phase.FACT_COLLECTION

    elif action == "reset_facts":
        room_manager.reset_room_for_new_game(room)

    elif action in ("end_investigation", "start_guessing"):
        if room.state != Phase.INVESTIGATION:
            raise GameError("Investigation is not currently running.")
        room_manager.cancel_timer(room)
        assert_transition(room.state, Phase.GUESSING)
        room.state = Phase.GUESSING

    elif action == "end_guessing":
        # Idempotent: if everyone already guessed we auto-advanced to REVEAL.
        if room.state == Phase.REVEAL:
            pass
        elif room.state == Phase.GUESSING:
            assert_transition(room.state, Phase.REVEAL)
            room.state = Phase.REVEAL
        else:
            raise GameError("Guessing is not currently running.")

    elif action == "reveal_all":
        if room.state == Phase.GUESSING:
            room.state = Phase.REVEAL
        if room.state != Phase.REVEAL:
            raise GameError("Results can only be revealed after guessing.")
        room.revealed_players = set(room.players.keys())

    elif action == "finish":
        room_manager.cancel_timer(room)
        room.state = Phase.FINISHED

    elif action == "start_investigation":
        _start_investigation(room, room.investigation_minutes)

    else:
        raise GameError(f"Unknown host action: {action!r}.")

    room_manager.touch(room)
    await announce_phase(room)


@app.post("/api/rooms/{room_code}/reveal")
async def reveal_results(room_code: str, body: HostActionRequest = Body(...)) -> dict:
    """Reveal one participant (``target_id``) or everyone (omit ``target_id``)."""
    code = normalize_room_code(room_code)
    room = room_manager.get_or_error(code)
    _require_host(room, body.token)
    if room.state == Phase.GUESSING:
        room.state = Phase.REVEAL
    if room.state != Phase.REVEAL:
        raise GameError("Results can only be revealed after guessing.")

    target_id = getattr(body, "target_id", None)
    if target_id:
        if target_id not in room.players:
            raise GameError("Unknown participant.")
        room.revealed_players.add(target_id)
    else:
        room.revealed_players = set(room.players.keys())

    room_manager.touch(room)
    await announce_phase(room)
    return {"ok": True, "phase": room.state, "revealed": sorted(room.revealed_players)}


@app.get("/api/rooms/{room_code}/state")
async def get_state(room_code: str, token: str = Query(...)) -> dict:
    code = normalize_room_code(room_code)
    room = room_manager.get_or_error(code)
    if room.is_host(token):
        return build_host_state(room)
    player = room.player_by_token(token)
    if player is None:
        raise GameError("Invalid session.", status_code=401)
    return build_player_state(room, player)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws/{room_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, token: str = Query(...)) -> None:
    code = normalize_room_code(room_code)
    room = room_manager.get(code)
    if room is None:
        await websocket.close(code=4404)
        return

    if room.is_host(token):
        sender_key = manager.HOST_KEY
        player: Optional[Player] = None
    else:
        player = room.player_by_token(token)
        if player is None:
            await websocket.close(code=4401)
            return
        sender_key = participant_key(player.id)

    await manager.connect(code, sender_key, websocket)
    if player is not None:
        player.connected = True
        player.websocket = websocket
    room_manager.touch(room)
    await push_states(room)

    try:
        while True:
            raw = await websocket.receive_text()
            if raw == "ping" or raw == '"ping"':
                await manager.send(code, sender_key, {"type": "pong"})
            else:
                await manager.send(code, sender_key, {"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(code, sender_key)
        if player is not None:
            player.connected = False
            player.websocket = None
            room = room_manager.get(code)
            if room is not None:
                room_manager.touch(room)
                await manager.broadcast(
                    room.code,
                    {"type": "player_left", "player_id": player.id, "name": player.name},
                )
                await push_states(room)


__all__ = ["app"]
