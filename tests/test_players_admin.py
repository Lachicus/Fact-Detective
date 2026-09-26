"""Host player management: kick a participant and restart the session."""

from app.game import Phase
from conftest import join, player_id_named, room_of


def test_kick_removes_player_from_room(host, memory_store):
    alice = join(host, "Alice")
    join(host, "Bob")
    target = player_id_named(memory_store, host, "Alice")

    response = host.post("/host/kick", {"target_id": target})

    assert response.status_code == 303
    assert [p.name for p in room_of(memory_store, host).players.values()] == ["Bob"]
    # The kicked session stops resolving, so they land back on the landing page.
    kicked = alice.get()
    assert kicked.status_code == 200
    assert "no longer valid" in kicked.text


def test_kick_invalidates_the_kicked_token(host, memory_store):
    join(host, "Alice")
    target = player_id_named(memory_store, host, "Alice")
    token = room_of(memory_store, host).players[target].token

    host.post("/host/kick", {"target_id": target})

    assert room_of(memory_store, host).player_by_token(token) is None


def test_kick_requires_a_host_session(host, memory_store):
    alice = join(host, "Alice")
    bob = join(host, "Bob")
    alice_id = player_id_named(memory_store, host, "Alice")

    response = bob.post("/host/kick", {"target_id": alice_id})

    assert response.status_code == 403
    assert alice_id in room_of(memory_store, host).players
    assert alice.get().status_code == 200


def test_kick_is_blocked_once_the_investigation_started(host, memory_store):
    join(host, "Alice")
    join(host, "Bob")
    room = room_of(memory_store, host)
    room.state = Phase.INVESTIGATION
    target = player_id_named(memory_store, host, "Alice")

    response = host.post("/host/kick", {"target_id": target})

    assert response.status_code == 400
    assert "before the investigation" in response.text
    assert target in room_of(memory_store, host).players


def test_kick_rejects_unknown_player(host, memory_store):
    join(host, "Alice")

    response = host.post("/host/kick", {"target_id": "does-not-exist"})

    assert response.status_code == 400
    assert "Unknown participant" in response.text


def test_kick_rejects_an_empty_target(host, memory_store):
    join(host, "Alice")

    response = host.post("/host/kick", {"target_id": ""})

    assert response.status_code == 400
    assert len(room_of(memory_store, host).players) == 1


def test_kick_prunes_the_assignment_map(host, memory_store):
    join(host, "Alice")
    join(host, "Bob")
    join(host, "Cleo")
    room = room_of(memory_store, host)
    alice = player_id_named(memory_store, host, "Alice")
    bob = player_id_named(memory_store, host, "Bob")
    cleo = player_id_named(memory_store, host, "Cleo")
    # Alice received Bob's fact; Bob received Cleo's fact.
    room.assignments = {alice: bob, bob: cleo}

    host.post("/host/kick", {"target_id": bob})

    room = room_of(memory_store, host)
    assert bob not in room.players
    assert bob not in room.assignments
    assert bob not in room.assignments.values()
    # Alice received Bob's fact, so her entry goes too: the mapping must never
    # point at a player who is no longer in the room.
    assert room.assignments == {}
    assert player_id_named(memory_store, host, "Alice") == alice
    assert player_id_named(memory_store, host, "Cleo") == cleo


def test_kick_is_offered_in_the_host_ui_only_while_removable(host, memory_store):
    join(host, "Alice")
    panel = host.panel().text
    assert "/host/kick" in panel
    assert "/host/restart" in panel

    room_of(memory_store, host).state = Phase.INVESTIGATION
    panel = host.panel().text
    assert "/host/kick" not in panel
    assert "/host/restart" not in panel


def test_restart_session_empties_the_room_and_keeps_the_host(host, memory_store):
    join(host, "Alice")
    join(host, "Bob")
    room = room_of(memory_store, host)
    room.state = Phase.FINISHED
    room.assignments = {p.id: p.id for p in room.players.values()}
    room.revealed_players = list(room.players)
    room.ended = True

    response = host.post("/host/restart")

    assert response.status_code == 303
    room = room_of(memory_store, host)
    assert room.state == Phase.LOBBY
    assert room.players == {}
    assert room.tokens == {}
    assert room.assignments == {}
    assert room.revealed_players == []
    assert room.ended is False
    # The host keeps control of the same room code.
    page = host.get()
    assert page.status_code == 200
    assert "Host Dashboard" in page.text
    assert "No players yet" in page.text


def test_restart_requires_a_host_session(host, memory_store):
    join(host, "Alice")
    alice = join(host, "Bob")
    room_of(memory_store, host).state = Phase.INVESTIGATION

    response = alice.post("/host/restart")

    assert response.status_code == 403
    assert len(room_of(memory_store, host).players) == 2
    assert room_of(memory_store, host).state == Phase.INVESTIGATION
