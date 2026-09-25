from tests.conftest import create_room, join_player, setup_room_with_players, submit_facts


def _advance_to_ready(client, room, players):
    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "start_fact_collection"},
    )
    submit_facts(client, room["room_code"], players)


def _start_investigation(client, room):
    resp = client.post(
        f"/api/rooms/{room['room_code']}/start",
        json={"token": room["host_token"], "investigation_minutes": 10},
    )
    assert resp.status_code == 200, resp.text


def test_participant_state_hides_other_facts_and_owner(client):
    room, players = setup_room_with_players(client, 7)
    _advance_to_ready(client, room, players)
    _start_investigation(client, room)

    for p in players:
        state = client.get(
            f"/api/rooms/{room['room_code']}/state",
            params={"token": p["participant_token"]},
        ).json()

        # The participant gets exactly one fact, their assignment.
        assert state["assignment"] is not None
        assigned_fact = state["assignment"]["fact"]

        # No owner identity is exposed anywhere before the reveal.
        blob = str(state)
        secret = {
            "Secret fact number 1",
            "Secret fact number 2",
            "Secret fact number 3",
            "Secret fact number 4",
            "Secret fact number 5",
            "Secret fact number 6",
            "Secret fact number 7",
        }
        # Only the assigned fact may appear; no other facts leak.
        visible = {f for f in secret if f in blob}
        assert visible <= {assigned_fact}
        assert "owner_id" not in state["assignment"]
        assert "reveal" not in state or state.get("reveal") is None


def test_participant_cannot_receive_own_fact(client):
    room, players = setup_room_with_players(client, 7)
    _advance_to_ready(client, room, players)
    _start_investigation(client, room)

    facts = {p["participant_id"]: f"Secret fact number {i + 1}" for i, p in enumerate(players)}
    for p in players:
        state = client.get(
            f"/api/rooms/{room['room_code']}/state",
            params={"token": p["participant_token"]},
        ).json()
        own_fact = facts[p["participant_id"]]
        assert state["assignment"]["fact"] != own_fact


def test_host_can_see_complete_state(client):
    room, players = setup_room_with_players(client, 7)
    _advance_to_ready(client, room, players)
    _start_investigation(client, room)

    state = client.get(
        f"/api/rooms/{room['room_code']}/state",
        params={"token": room["host_token"]},
    ).json()

    assert state["role"] == "host"
    assert len(state["assignments"]) == 7
    # Host sees every fact.
    facts = {a["fact"] for a in state["assignments"]}
    assert len(facts) == 7
    for a in state["assignments"]:
        assert a["owner_name"]
        assert a["giver_name"]


def test_participant_token_cannot_access_host_state(client):
    room, players = setup_room_with_players(client, 2)
    state = client.get(
        f"/api/rooms/{room['room_code']}/state",
        params={"token": players[0]["participant_token"]},
    ).json()
    # Same endpoint, but participant view: no host-only fields.
    assert state["role"] == "participant"
    assert "assignments" not in state


def test_fact_not_visible_before_investigation(client):
    room, players = setup_room_with_players(client, 3)
    _advance_to_ready(client, room, players)
    # Still in READY: no assignment should be exposed.
    state = client.get(
        f"/api/rooms/{room['room_code']}/state",
        params={"token": players[0]["participant_token"]},
    ).json()
    assert state["assignment"] is None


def test_reveal_exposes_owner_only_after_reveal(client):
    room, players = setup_room_with_players(client, 3)
    _advance_to_ready(client, room, players)
    _start_investigation(client, room)

    client.post(
        f"/api/rooms/{room['room_code']}/host/action",
        json={"token": room["host_token"], "action": "end_investigation"},
    )
    for i, p in enumerate(players):
        target = players[(i + 1) % len(players)]["participant_id"]
        client.post(
            f"/api/rooms/{room['room_code']}/guess",
            json={"token": p["participant_token"], "target_id": target},
        )
    client.post(
        f"/api/rooms/{room['room_code']}/reveal",
        json={"token": room["host_token"]},
    )

    state = client.get(
        f"/api/rooms/{room['room_code']}/state",
        params={"token": players[0]["participant_token"]},
    ).json()
    assert state["reveal"] is not None
    assert state["reveal"]["owner_name"]
    assert state["reveal"]["owner_id"]
