from tests.conftest import setup_room_with_players, submit_facts


def test_cannot_submit_fact_in_lobby(client):
    room, players = setup_room_with_players(client, 2)
    resp = client.post(
        f"/api/rooms/{room['room_code']}/facts",
        json={"token": players[0]["participant_token"], "fact": "Hello"},
    )
    assert resp.status_code == 400


def test_cannot_start_before_all_facts_submitted(client):
    room, players = setup_room_with_players(client, 3)
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    client.post(
        f"/api/rooms/{room['room_code']}/facts",
        json={"token": players[0]["participant_token"], "fact": "Only one fact"},
    )
    resp = client.post(
        f"/api/rooms/{room['room_code']}/start",
        json={"token": room["host_token"], "investigation_minutes": 10},
    )
    assert resp.status_code == 400


def test_ready_phase_after_all_facts(client):
    room, players = setup_room_with_players(client, 3)
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    submit_facts(client, room["room_code"], players)
    state = client.get(
        f"/api/rooms/{room['room_code']}/state",
        params={"token": room["host_token"]},
    ).json()
    assert state["phase"] == "READY"


def test_cannot_submit_fact_twice(client):
    room, players = setup_room_with_players(client, 2)
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    first = client.post(
        f"/api/rooms/{room['room_code']}/facts",
        json={"token": players[0]["participant_token"], "fact": "First"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/rooms/{room['room_code']}/facts",
        json={"token": players[0]["participant_token"], "fact": "Second"},
    )
    assert second.status_code == 400


def test_empty_fact_rejected(client):
    room, players = setup_room_with_players(client, 2)
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    resp = client.post(
        f"/api/rooms/{room['room_code']}/facts",
        json={"token": players[0]["participant_token"], "fact": "   "},
    )
    assert resp.status_code == 400


def test_invalid_token_rejected(client):
    room, players = setup_room_with_players(client, 2)
    resp = client.post(
        f"/api/rooms/{room['room_code']}/start",
        json={"token": "not-a-real-host-token", "investigation_minutes": 10},
    )
    assert resp.status_code == 403


def test_host_cannot_skip_phases(client):
    room, players = setup_room_with_players(client, 3)
    # LOBBY -> REVEAL is invalid.
    resp = client.post(
        f"/api/rooms/{room['room_code']}/reveal",
        json={"token": room["host_token"]},
    )
    assert resp.status_code == 400


def test_players_cannot_join_after_lobby(client):
    room, players = setup_room_with_players(client, 2)
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    resp = client.post(f"/api/rooms/{room['room_code']}/join", json={"name": "Latecomer"})
    assert resp.status_code == 400


def test_duplicate_names_rejected(client):
    room, players = setup_room_with_players(client, 1)
    resp = client.post(f"/api/rooms/{room['room_code']}/join", json={"name": "Player1"})
    assert resp.status_code == 400


def test_investigation_duration_bounds(client):
    room, players = setup_room_with_players(client, 2)
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    submit_facts(client, room["room_code"], players)
    too_short = client.post(
        f"/api/rooms/{room['room_code']}/start",
        json={"token": room["host_token"], "investigation_minutes": 1},
    )
    assert too_short.status_code == 400
    too_long = client.post(
        f"/api/rooms/{room['room_code']}/start",
        json={"token": room["host_token"], "investigation_minutes": 60},
    )
    assert too_long.status_code == 400
    ok = client.post(
        f"/api/rooms/{room['room_code']}/start",
        json={"token": room["host_token"], "investigation_minutes": 7},
    )
    assert ok.status_code == 200
