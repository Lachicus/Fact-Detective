"""Post-reveal results board: who guessed right/wrong, and who owns what.

Also guards the privacy boundary: the board contains every fact and its owner,
so it must stay hidden from participants until the reveal is complete.
"""

from app.game import Phase
from app.models import Room
from app.views import host_context, participant_context, results_board, results_visible
from conftest import join, player_id_named, room_of


def build_room(memory_store, host, facts, assignments, guesses):
    """Drive a room to GUESSING with a known assignment/guess pattern.

    ``facts``/``assignments``/``guesses`` are keyed by player name.
    ``assignments`` maps a player to the *owner* of the fact they received.
    """
    actors = {}
    for name in facts:
        actors[name] = join(host, name)

    host.post("/host/action", {"action": "start_fact_collection"}, follow_redirects=False)
    for name, fact in facts.items():
        response = actors[name].post("/facts", {"fact": fact})
        assert response.status_code == 303, response.text

    host.post("/start", {"investigation_minutes": 3})
    room = room_of(memory_store, host)
    assert room.state == Phase.INVESTIGATION

    # Replace the random derangement with a deterministic, known one.
    room.assignments = {
        player_id_named(memory_store, host, name): player_id_named(memory_store, host, owner)
        for name, owner in assignments.items()
    }
    for name, guessed in guesses.items():
        player = room.players[player_id_named(memory_store, host, name)]
        player.guess = player_id_named(memory_store, host, guessed)
        player.guessed = True
    room.state = Phase.GUESSING
    memory_store.save(room)
    return room, actors


def three_player_room(memory_store, host):
    """Alice and Cleo guess right, Bob guesses wrong."""
    return build_room(
        memory_store,
        host,
        facts={"Alice": "Ate a shoe", "Bob": "Swam with dolphins", "Cleo": "Met a pope"},
        assignments={"Alice": "Bob", "Bob": "Cleo", "Cleo": "Alice"},
        guesses={"Alice": "Bob", "Bob": "Alice", "Cleo": "Alice"},
    )


def board_by_name(room):
    return {row["player_name"]: row for row in results_board(room)}


def test_guess_is_correct_when_it_names_the_fact_owner(memory_store, host):
    room, _actors = three_player_room(memory_store, host)
    board = board_by_name(room)

    assert board["Alice"]["correct"] is True
    assert board["Cleo"]["correct"] is True
    assert board["Bob"]["correct"] is False
    assert board["Bob"]["guess_name"] == "Alice"
    assert board["Bob"]["owner_name"] == "Cleo"
    assert board["Alice"]["fact"] == "Swam with dolphins"


def test_scores_and_ranks(memory_store, host):
    room, _actors = three_player_room(memory_store, host)
    board = board_by_name(room)

    assert board["Alice"]["points"] == 1
    assert board["Cleo"]["points"] == 1
    assert board["Bob"]["points"] == 0
    # Alice and Cleo tie for first; Bob is third, not second.
    assert board["Alice"]["rank"] == 1
    assert board["Cleo"]["rank"] == 1
    assert board["Bob"]["rank"] == 3
    # The board is sorted best first.
    assert [row["rank"] for row in results_board(room)] == [1, 1, 3]


def test_participant_cannot_see_results_before_the_reveal(memory_store, host):
    room, _actors = three_player_room(memory_store, host)
    player = room.players[player_id_named(memory_store, host, "Alice")]

    assert results_visible(room) is False
    assert participant_context(room, player)["results"] is None
    assert host_context(room)["results"] is None


def test_participant_cannot_see_results_while_revealing_one_at_a_time(memory_store, host):
    room, _actors = three_player_room(memory_store, host)
    alice_id = player_id_named(memory_store, host, "Alice")
    host.post("/host/action", {"action": "reveal_all"}, follow_redirects=False)
    room = room_of(memory_store, host)
    assert room.state == Phase.REVEAL
    room.revealed_players = [alice_id]

    assert results_visible(room) is False
    assert participant_context(room, room.players[alice_id])["results"] is None
    # The host may always see the scoreboard from the reveal phase onwards.
    assert host_context(room)["results"] is not None


def test_participants_see_the_full_board_once_everyone_is_revealed(memory_store, host):
    room, _actors = three_player_room(memory_store, host)
    host.post("/host/action", {"action": "reveal_all"}, follow_redirects=False)
    room = room_of(memory_store, host)
    assert room.state == Phase.REVEAL

    assert results_visible(room) is True
    for player in room.players.values():
        ctx = participant_context(room, player)
        assert ctx["results"] is not None
        assert len(ctx["results"]) == 3
        assert ctx["your_rank"] is not None
        # Every player's fact is now visible, as requested.
        assert {row["fact"] for row in ctx["results"]} == {
            "Ate a shoe",
            "Swam with dolphins",
            "Met a pope",
        }


def test_own_points_are_reported_to_each_participant(memory_store, host):
    room, _actors = three_player_room(memory_store, host)
    host.post("/host/action", {"action": "reveal_all"}, follow_redirects=False)
    room = room_of(memory_store, host)

    ctx = participant_context(room, room.players[player_id_named(memory_store, host, "Bob")])
    assert ctx["your_points"] == 0
    assert ctx["your_rank"] == 3
    assert ctx["reveal"]["correct"] is False


def test_finish_reveals_everyone_so_the_board_is_reachable(memory_store, host):
    room, _actors = three_player_room(memory_store, host)
    host.post("/host/action", {"action": "end_guessing"}, follow_redirects=False)
    host.post("/host/action", {"action": "finish"}, follow_redirects=False)
    room = room_of(memory_store, host)

    assert room.state == Phase.FINISHED
    assert set(room.revealed_players) == set(room.players)
    assert results_visible(room) is True
    ctx = participant_context(room, next(iter(room.players.values())))
    assert ctx["results"] is not None
    assert ctx["reveal"] is not None


def test_results_never_leak_before_guessing_is_over(memory_store, host):
    room, _actors = three_player_room(memory_store, host)
    for player in room.players.values():
        body = participant_context(room, player)
        assert body["results"] is None
        assert body["your_points"] == 0
        assert body["your_rank"] is None
        # The assignment still hides its owner.
        assert set(body["assignment"]) == {"fact"}


def test_results_appear_in_the_rendered_panels(memory_store, host):
    _room, actors = three_player_room(memory_store, host)

    # Before the reveal: no board anywhere.
    assert "Results" not in actors["Alice"].panel().text

    host.post("/host/action", {"action": "reveal_all"}, follow_redirects=False)

    host_panel = host.panel().text
    assert "Results" in host_panel
    assert "Swam with dolphins" in host_panel
    assert "Score" in host_panel

    player_panel = actors["Alice"].panel().text
    assert "Results" in player_panel
    assert "Ate a shoe" in player_panel
    assert "Bob" in player_panel


def test_results_scored_zero_when_nobody_guessed():
    room = Room(code="ABCDE", host_token="host-token")
    room.state = Phase.REVEAL
    for index in range(2):
        player = room.add_player(f"P{index}")
        player.fact = f"fact {index}"
        player.submitted = True
    ids = list(room.players)
    room.assignments = {ids[0]: ids[1], ids[1]: ids[0]}
    room.reveal_everyone()

    assert results_visible(room) is True
    assert [row["points"] for row in results_board(room)] == [0, 0]
    assert [row["correct"] for row in results_board(room)] == [False, False]
    assert all(row["guess_name"] is None for row in results_board(room))
