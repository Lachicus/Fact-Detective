"""End-to-end simulation of the complete 7-player game over REST + WebSockets.

This is the acceptance test described in the project brief: it plays a full
game and asserts that no participant can observe another participant's secret
information before the reveal.
"""

import json
from contextlib import ExitStack

from tests.conftest import create_room, join_player, submit_facts


def _wait_for_state(websocket, predicate, limit=100):
    """Read messages until a 'state' message satisfies ``predicate``."""
    for _ in range(limit):
        message = websocket.receive_json()
        if message.get("type") == "state" and predicate(message):
            return message
    raise AssertionError("Did not receive expected state over WebSocket.")


def test_full_seven_player_game(client):
    n = 7
    room = create_room(client)
    code = room["room_code"]
    host_token = room["host_token"]

    players = [join_player(client, code, f"Player{i + 1}") for i in range(n)]
    facts = {p["participant_id"]: f"Secret fact number {i + 1}" for i, p in enumerate(players)}
    fact_texts = set(facts.values())

    with ExitStack() as stack:
        host_ws = stack.enter_context(
            client.websocket_connect(f"/ws/{code}?token={host_token}")
        )
        player_ws = [
            stack.enter_context(
                client.websocket_connect(f"/ws/{code}?token={p['participant_token']}")
            )
            for p in players
        ]

        # --- LOBBY -> FACT_COLLECTION -------------------------------------
        client.post(
            f"/api/rooms/{code}/host/action",
            json={"token": host_token, "action": "start_fact_collection"},
        )
        submit_facts(client, code, players)

        host_state = _wait_for_state(host_ws, lambda m: m["phase"] in ("READY",))
        assert host_state["facts_submitted"] == n

        # --- READY -> INVESTIGATION (assign facts) -------------------------
        resp = client.post(
            f"/api/rooms/{code}/start",
            json={"token": host_token, "investigation_minutes": 3},
        )
        assert resp.status_code == 200, resp.text

        # Host sees the full mapping.
        host_state = _wait_for_state(host_ws, lambda m: m["phase"] == "INVESTIGATION")
        assert len(host_state["assignments"]) == n

        # Each participant receives exactly one fact, never their own.
        for i, p in enumerate(players):
            state = _wait_for_state(player_ws[i], lambda m: m["phase"] == "INVESTIGATION")
            assignment = state["assignment"]
            assert assignment is not None
            assert assignment["fact"] in fact_texts
            assert assignment["fact"] != facts[p["participant_id"]]
            # No owner identity is leaked.
            assert "owner_id" not in assignment
            assert "owner_name" not in assignment
            # The raw payload must not contain any other participant's fact.
            blob = json.dumps(state)
            leaked = {f for f in fact_texts if f in blob}
            assert leaked == {assignment["fact"]}

        # --- GUESSING ------------------------------------------------------
        client.post(
            f"/api/rooms/{code}/host/action",
            json={"token": host_token, "action": "end_investigation"},
        )
        for i, p in enumerate(players):
            target = players[(i + 1) % n]
            r = client.post(
                f"/api/rooms/{code}/guess",
                json={"token": p["participant_token"], "target_id": target["participant_id"]},
            )
            assert r.status_code == 200, r.text

        # Everyone guessed -> auto REVEAL.
        host_state = _wait_for_state(host_ws, lambda m: m["phase"] == "REVEAL")
        assert host_state["guesses_submitted"] == n

        # --- REVEAL --------------------------------------------------------
        client.post(
            f"/api/rooms/{code}/reveal",
            json={"token": host_token},
        )
        for i, p in enumerate(players):
            state = _wait_for_state(
                player_ws[i], lambda m: m.get("reveal") is not None
            )
            reveal = state["reveal"]
            assert reveal["owner_name"]
            assert reveal["owner_id"] != p["participant_id"]
            assert isinstance(reveal["correct"], bool)

        # --- FINISH --------------------------------------------------------
        client.post(f"/api/rooms/{code}/end", json={"token": host_token})
        host_state = _wait_for_state(host_ws, lambda m: m["phase"] == "FINISHED")
        assert host_state["phase"] == "FINISHED"


def test_no_self_assignment_over_many_games(client):
    """Repeat assignment to be confident nobody ever gets their own fact."""
    for _ in range(25):
        room = create_room(client)
        code = room["room_code"]
        players = [join_player(client, code, f"P{i}") for i in range(5)]
        client.post(
            f"/api/rooms/{code}/host/action",
            json={"token": room["host_token"], "action": "start_fact_collection"},
        )
        submit_facts(client, code, players)
        client.post(
            f"/api/rooms/{code}/start",
            json={"token": room["host_token"], "investigation_minutes": 5},
        )
        for p in players:
            state = client.get(
                f"/api/rooms/{code}/state", params={"token": p["participant_token"]}
            ).json()
            own_fact = None
            for q in players:
                if q["participant_id"] == p["participant_id"]:
                    idx = players.index(q)
                    own_fact = f"Secret fact number {idx + 1}"
            assert state["assignment"]["fact"] != own_fact
