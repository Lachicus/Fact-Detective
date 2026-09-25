import asyncio
import time

from app.game import Phase
from app.main import expire_investigation, room_manager
from tests.conftest import setup_room_with_players, submit_facts


def _play_to_guessing(client, n=3):
    room, players = setup_room_with_players(client, n)
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    submit_facts(client, room["room_code"], players)
    client.post(
        f"/api/rooms/{room['room_code']}/start",
        json={"token": room["host_token"], "investigation_minutes": 10},
    )
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "end_investigation"},
    )
    return room, players


def test_guess_before_guessing_phase_rejected(client):
    room, players = setup_room_with_players(client, 3)
    resp = client.post(
        f"/api/rooms/{room['room_code']}/guess",
        json={"token": players[0]["participant_token"], "target_id": players[1]["participant_id"]},
    )
    assert resp.status_code == 400


def test_self_guess_rejected(client):
    room, players = _play_to_guessing(client, 3)
    resp = client.post(
        f"/api/rooms/{room['room_code']}/guess",
        json={"token": players[0]["participant_token"], "target_id": players[0]["participant_id"]},
    )
    assert resp.status_code == 400


def test_duplicate_guess_rejected(client):
    room, players = _play_to_guessing(client, 3)
    first = client.post(
        f"/api/rooms/{room['room_code']}/guess",
        json={"token": players[0]["participant_token"], "target_id": players[1]["participant_id"]},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/rooms/{room['room_code']}/guess",
        json={"token": players[0]["participant_token"], "target_id": players[2]["participant_id"]},
    )
    assert second.status_code == 400


def test_guess_unknown_target_rejected(client):
    room, players = _play_to_guessing(client, 3)
    resp = client.post(
        f"/api/rooms/{room['room_code']}/guess",
        json={"token": players[0]["participant_token"], "target_id": "ghost"},
    )
    assert resp.status_code == 400


def test_full_guess_and_reveal_flow(client):
    room, players = _play_to_guessing(client, 3)
    for i, p in enumerate(players):
        target = players[(i + 1) % len(players)]["participant_id"]
        resp = client.post(
            f"/api/rooms/{room['room_code']}/guess",
            json={"token": p["participant_token"], "target_id": target},
        )
        assert resp.status_code == 200

    reveal = client.post(
        f"/api/rooms/{room['room_code']}/reveal",
        json={"token": room["host_token"]},
    )
    assert reveal.status_code == 200
    assert reveal.json()["phase"] == Phase.REVEAL

    for p in players:
        state = client.get(
            f"/api/rooms/{room['room_code']}/state",
            params={"token": p["participant_token"]},
        ).json()
        assert state["reveal"] is not None
        assert isinstance(state["reveal"]["correct"], bool)


def test_one_at_a_time_reveal(client):
    room, players = _play_to_guessing(client, 3)
    for i, p in enumerate(players):
        client.post(
            f"/api/rooms/{room['room_code']}/guess",
            json={"token": p["participant_token"], "target_id": players[(i + 1) % 3]["participant_id"]},
        )
    # End guessing without revealing.
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "end_guessing"},
    )
    # Reveal only player 0.
    resp = client.post(
        f"/api/rooms/{room['room_code']}/reveal",
        json={"token": room["host_token"], "target_id": players[0]["participant_id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["revealed"] == [players[0]["participant_id"]]

    s0 = client.get(
        f"/api/rooms/{room['room_code']}/state",
        params={"token": players[0]["participant_token"]},
    ).json()
    s1 = client.get(
        f"/api/rooms/{room['room_code']}/state",
        params={"token": players[1]["participant_token"]},
    ).json()
    assert s0["reveal"] is not None
    assert s1["reveal"] is None


def test_timer_expiry_transitions_to_guessing(client):
    room, players = setup_room_with_players(client, 2)
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    submit_facts(client, room["room_code"], players)
    client.post(
        f"/api/rooms/{room['room_code']}/start",
        json={"token": room["host_token"], "investigation_minutes": 3},
    )
    # Force the authoritative end time into the past, then fire the timer logic.
    live_room = room_manager.get(room["room_code"])
    live_room.investigation_ends_at = time.time() - 1
    asyncio.run(expire_investigation(room["room_code"]))

    state = client.get(
        f"/api/rooms/{room['room_code']}/state",
        params={"token": room["host_token"]},
    ).json()
    assert state["phase"] == Phase.GUESSING


def test_end_game(client):
    room, players = _play_to_guessing(client, 2)
    resp = client.post(
        f"/api/rooms/{room['room_code']}/end",
        json={"token": room["host_token"]},
    )
    assert resp.status_code == 200
    assert resp.json()["phase"] == Phase.FINISHED
