"""Private Fact Detective — server-rendered FastAPI app.

Design:

* Full HTML is rendered server-side with Jinja2 (one view per role + phase).
* Session is an opaque token in an httpOnly cookie; tokens never reach JS.
* State lives in a :class:`RoomStore` (memory locally, Firebase RTDB in prod).
* Realtime is "RTDB as a change bus": the browser subscribes to the room
  revision counter and re-fetches the rendered fragment when it changes.
* No background tasks. The investigation timer expires lazily on request/tick.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Tuple

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, views
from .game import (
    MAX_PLAYERS,
    MIN_PLAYERS,
    GameError,
    Phase,
    assert_transition,
    clamp_investigation_minutes,
    sanitize_fact,
    sanitize_name,
    validate_assignment,
)
from .models import Player, Room
from .security import normalize_room_code
from .store import get_store

def _find_base_dir() -> Path:
    """Locate the project root (the directory that contains templates/)."""
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "templates").is_dir():
            return candidate
    return here.parent


BASE_DIR = _find_base_dir()
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Private Fact Detective", version="2.0.0")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Session handling (opaque token in an httpOnly cookie)
# ---------------------------------------------------------------------------
def _set_session(response, code: str, token: str, secure: bool) -> None:
    response.set_cookie(
        config.SESSION_COOKIE,
        f"{code}:{token}",
        max_age=config.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _read_session(request: Request) -> Tuple[Optional[str], Optional[str]]:
    raw = request.cookies.get(config.SESSION_COOKIE)
    if not raw or ":" not in raw:
        return None, None
    code, token = raw.split(":", 1)
    return normalize_room_code(code), token


def _is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "")
    return forwarded.split(",")[0].strip() == "https"


def _resolve_role(room: Room, token: Optional[str]) -> Tuple[Optional[str], Optional[Player]]:
    if room.is_host(token):
        return "host", None
    player = room.player_by_token(token)
    if player is not None:
        return "participant", player
    return None, None


def _require_participant(room: Room, token: Optional[str]) -> Player:
    player = room.player_by_token(token)
    if player is None:
        raise GameError("Invalid participant session.", status_code=401)
    return player


def _require_host(room: Room, token: Optional[str]) -> None:
    if not room.is_host(token):
        raise GameError("Invalid host session.", status_code=403)


# ---------------------------------------------------------------------------
# Lazy, serverless-friendly timer expiry
# ---------------------------------------------------------------------------
def _maybe_expire(room: Room) -> bool:
    """Advance INVESTIGATION -> GUESSING once the deadline has passed.

    There is no background task on serverless; any request that touches the
    room performs this check instead.
    """
    ends_at = room.investigation_ends_at
    if room.state == Phase.INVESTIGATION and ends_at and time.time() >= ends_at:
        room.state = Phase.GUESSING
        get_store().save(room)
        return True
    return False


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def _pfd_payload(room: Room) -> dict:
    rev = get_store().get_rev(room.code)
    firebase = (
        config.settings.web_firebase_config()
        if config.settings.resolved_store_backend() == "firebase"
        else {}
    )
    return {
        "roomCode": room.code,
        "rev": rev,
        "fragmentUrl": f"/rooms/{room.code}",
        "revUrl": f"/rooms/{room.code}/rev",
        "tickUrl": f"/rooms/{room.code}/tick",
        "firebase": firebase,
    }


def _render_room(request: Request, room: Room, role: str, player: Optional[Player], error: Optional[str] = None, status_code: int = 200):
    _maybe_expire(room)
    ctx = views.context_for(room, role, player)
    ctx["error"] = error
    ctx["pfd_json"] = json.dumps(_pfd_payload(room))
    return templates.TemplateResponse(request=request, name="room.html", context=ctx, status_code=status_code)


def _render_panel(request: Request, room: Room, role: str, player: Optional[Player], error: Optional[str] = None):
    _maybe_expire(room)
    ctx = views.context_for(room, role, player)
    ctx["error"] = error
    ctx["pfd_json"] = json.dumps(_pfd_payload(room))
    return templates.TemplateResponse(request=request, name="_room_body.html", context=ctx)


def _render_landing(request: Request, error: Optional[str] = None, prefill_room: str = "", status_code: int = 200):
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"error": error, "prefill_room": prefill_room, "pfd_json": "null"},
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    code, token = _read_session(request)
    if code:
        room = get_store().get(code)
        if room is not None:
            role, _player = _resolve_role(room, token)
            if role:
                return RedirectResponse(url=f"/rooms/{code}", status_code=303)
    return _render_landing(request)


@app.post("/rooms")
def create_room(request: Request):
    room = get_store().create_room()
    response = RedirectResponse(url=f"/rooms/{room.code}", status_code=303)
    _set_session(response, room.code, room.host_token, secure=_is_https(request))
    return response


@app.get("/rooms/{room_code}", response_class=HTMLResponse)
def room_page(request: Request, room_code: str, fragment: int = Query(0)):
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return _render_landing(request, error="That room was not found (it may have expired).", status_code=404)

    session_code, token = _read_session(request)
    if session_code != code:
        return _render_landing(request, prefill_room=code)

    role, player = _resolve_role(room, token)
    if role is None:
        return _render_landing(request, prefill_room=code, error="Your session is no longer valid for this room.")

    if fragment:
        return _render_panel(request, room, role, player)
    return _render_room(request, room, role, player)


@app.get("/rooms/{room_code}/rev")
def room_rev(room_code: str):
    code = normalize_room_code(room_code)
    store = get_store()
    if store.get(code) is None:
        return JSONResponse({"rev": 0, "exists": False})
    return {"rev": store.get_rev(code), "exists": True}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "store": config.settings.resolved_store_backend()}


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------
@app.post("/join")
def join_by_code(request: Request, room_code: str = Form(""), name: str = Form("")):
    """Landing-page join form: resolves the code and delegates."""
    code = normalize_room_code(room_code)
    if not code:
        return _render_landing(request, error="Enter a room code to join.")
    return join_room(request, code, name)


@app.post("/rooms/{room_code}/join")
def join_room(request: Request, room_code: str, name: str = Form("")):
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return _render_landing(request, error="That room was not found (it may have expired).", status_code=404)
    try:
        if room.state != Phase.LOBBY:
            raise GameError("This room is no longer accepting new players.")
        if len(room.players) >= MAX_PLAYERS:
            raise GameError("This room is full.")
        clean_name = sanitize_name(name)
        if any(p.name.lower() == clean_name.lower() for p in room.players.values()):
            raise GameError("That display name is already taken in this room.")
        player = room.add_player(clean_name)
        store.save(room)
    except GameError as exc:
        return _render_landing(request, error=exc.message, prefill_room=code, status_code=exc.status_code)

    response = RedirectResponse(url=f"/rooms/{code}", status_code=303)
    _set_session(response, code, player.token, secure=_is_https(request))
    return response


# ---------------------------------------------------------------------------
# Participant actions
# ---------------------------------------------------------------------------
@app.post("/rooms/{room_code}/facts")
def submit_fact(request: Request, room_code: str, fact: str = Form("")):
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return _render_landing(request, error="That room was not found.", status_code=404)
    _code, token = _read_session(request)
    try:
        player = _require_participant(room, token)
        if room.state != Phase.FACT_COLLECTION:
            raise GameError("Facts can only be submitted during fact collection.")
        if player.submitted:
            raise GameError("You have already submitted a fact.")
        clean_fact = sanitize_fact(fact)
        player.fact = clean_fact
        player.submitted = True
        if room.all_facts_submitted() and len(room.players) >= MIN_PLAYERS:
            room.state = Phase.READY
        store.save(room)
    except GameError as exc:
        role, p = _resolve_role(room, token)
        if role:
            return _render_room(request, room, role, p, error=exc.message, status_code=exc.status_code)
        return _render_landing(request, error=exc.message, prefill_room=code, status_code=exc.status_code)

    return RedirectResponse(url=f"/rooms/{code}", status_code=303)


@app.post("/rooms/{room_code}/guess")
def submit_guess(request: Request, room_code: str, target_id: str = Form("")):
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return _render_landing(request, error="That room was not found.", status_code=404)
    _code, token = _read_session(request)
    try:
        player = _require_participant(room, token)
        if room.state != Phase.GUESSING:
            raise GameError("Guesses can only be submitted during the guessing phase.")
        if player.guessed:
            raise GameError("You have already submitted a guess.")
        if not target_id:
            raise GameError("Choose a participant before submitting.")
        if target_id == player.id:
            raise GameError("You cannot guess yourself.")
        if target_id not in room.players:
            raise GameError("That participant is not in this room.")
        player.guess = target_id
        player.guessed = True
        if room.all_guessed():
            assert_transition(room.state, Phase.REVEAL)
            room.state = Phase.REVEAL
        store.save(room)
    except GameError as exc:
        role, p = _resolve_role(room, token)
        if role:
            return _render_room(request, room, role, p, error=exc.message, status_code=exc.status_code)
        return _render_landing(request, error=exc.message, prefill_room=code, status_code=exc.status_code)

    return RedirectResponse(url=f"/rooms/{code}", status_code=303)


# ---------------------------------------------------------------------------
# Host actions
# ---------------------------------------------------------------------------
@app.post("/rooms/{room_code}/start")
def start_investigation(request: Request, room_code: str, investigation_minutes: int = Form(10)):
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return _render_landing(request, error="That room was not found.", status_code=404)
    _code, token = _read_session(request)
    try:
        _require_host(room, token)
        _start_investigation(room, investigation_minutes)
        store.save(room)
    except GameError as exc:
        role, p = _resolve_role(room, token)
        if role:
            return _render_room(request, room, role, p, error=exc.message, status_code=exc.status_code)
        return _render_landing(request, error=exc.message, prefill_room=code, status_code=exc.status_code)

    return RedirectResponse(url=f"/rooms/{code}", status_code=303)


def _start_investigation(room: Room, minutes: Optional[int]) -> None:
    if room.state not in (Phase.READY, Phase.FACT_COLLECTION):
        raise GameError("The investigation can only be started once facts are collected.")
    if len(room.players) < MIN_PLAYERS:
        raise GameError("At least 2 participants are required.")
    if not room.all_facts_submitted():
        raise GameError("Not everyone has submitted a fact yet.")

    resolved_minutes = clamp_investigation_minutes(minutes)
    mapping = room.create_derangement_map()
    validate_assignment(mapping, list(room.players.keys()))

    assert_transition(room.state, Phase.ASSIGNMENT)
    room.state = Phase.ASSIGNMENT

    room.assignments = mapping
    room.investigation_minutes = resolved_minutes
    now = time.time()
    room.investigation_started_at = now
    room.investigation_ends_at = now + resolved_minutes * 60
    room.revealed_players = []

    assert_transition(Phase.ASSIGNMENT, Phase.INVESTIGATION)
    room.state = Phase.INVESTIGATION


def _reset_for_new_round(room: Room) -> None:
    """Reuse the same players for a fresh round, without a new room."""
    for player in room.players.values():
        player.fact = None
        player.submitted = False
        player.guess = None
        player.guessed = False
    room.assignments = {}
    room.investigation_started_at = None
    room.investigation_ends_at = None
    room.revealed_players = []
    room.ended = False
    room.state = Phase.FACT_COLLECTION


@app.post("/rooms/{room_code}/host/action")
def host_action(request: Request, room_code: str, action: str = Form("")):
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return _render_landing(request, error="That room was not found.", status_code=404)
    _code, token = _read_session(request)
    try:
        _require_host(room, token)
        _apply_host_action(room, (action or "").strip())
        store.save(room)
    except GameError as exc:
        role, p = _resolve_role(room, token)
        if role:
            return _render_room(request, room, role, p, error=exc.message, status_code=exc.status_code)
        return _render_landing(request, error=exc.message, prefill_room=code, status_code=exc.status_code)

    return RedirectResponse(url=f"/rooms/{code}", status_code=303)


def _apply_host_action(room: Room, action: str) -> None:
    if action == "start_fact_collection":
        assert_transition(room.state, Phase.FACT_COLLECTION)
        room.state = Phase.FACT_COLLECTION

    elif action in ("reset_facts", "new_round"):
        _reset_for_new_round(room)

    elif action in ("end_investigation", "start_guessing"):
        if room.state != Phase.INVESTIGATION:
            raise GameError("Investigation is not currently running.")
        assert_transition(room.state, Phase.GUESSING)
        room.state = Phase.GUESSING

    elif action == "end_guessing":
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
        room.revealed_players = list(room.players.keys())

    elif action == "finish":
        room.state = Phase.FINISHED

    elif action == "start_investigation":
        _start_investigation(room, room.investigation_minutes)

    else:
        raise GameError(f"Unknown host action: {action!r}.")


@app.post("/rooms/{room_code}/reveal")
def reveal_results(request: Request, room_code: str, target_id: str = Form("")):
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return _render_landing(request, error="That room was not found.", status_code=404)
    _code, token = _read_session(request)
    try:
        _require_host(room, token)
        if room.state == Phase.GUESSING:
            room.state = Phase.REVEAL
        if room.state != Phase.REVEAL:
            raise GameError("Results can only be revealed after guessing.")
        target = (target_id or "").strip()
        if target:
            if target not in room.players:
                raise GameError("Unknown participant.")
            if target not in room.revealed_players:
                room.revealed_players.append(target)
        else:
            room.revealed_players = list(room.players.keys())
        store.save(room)
    except GameError as exc:
        role, p = _resolve_role(room, token)
        if role:
            return _render_room(request, room, role, p, error=exc.message, status_code=exc.status_code)
        return _render_landing(request, error=exc.message, prefill_room=code, status_code=exc.status_code)

    return RedirectResponse(url=f"/rooms/{code}", status_code=303)


@app.post("/rooms/{room_code}/end")
def end_game(request: Request, room_code: str):
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return _render_landing(request, error="That room was not found.", status_code=404)
    _code, token = _read_session(request)
    try:
        _require_host(room, token)
        # Close the session for everyone, then return the host to the landing page.
        room.ended = True
        store.save(room)
    except GameError as exc:
        role, p = _resolve_role(room, token)
        if role:
            return _render_room(request, room, role, p, error=exc.message, status_code=exc.status_code)
        return _render_landing(request, error=exc.message, prefill_room=code, status_code=exc.status_code)

    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(config.SESSION_COOKIE, path="/")
    return response


@app.post("/rooms/{room_code}/tick")
def tick(request: Request, room_code: str):
    """Lazy timer expiry trigger. Safe to call repeatedly."""
    code = normalize_room_code(room_code)
    store = get_store()
    room = store.get(code)
    if room is None:
        return JSONResponse({"ok": False, "exists": False}, status_code=404)
    changed = _maybe_expire(room)
    return {"ok": True, "changed": changed, "rev": store.get_rev(code)}


__all__ = ["app"]
