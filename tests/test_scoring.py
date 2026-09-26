"""Scoring rules: correctness, points and ranking."""

from app.game import (
    POINTS_PER_CORRECT_GUESS,
    GameError,
    can_remove_players,
    is_correct_guess,
    points_for,
    rank_scores,
)
from app.game import Phase


def test_correct_guess_needs_both_ids():
    assert is_correct_guess("a", "a") is True
    assert is_correct_guess("a", "b") is False
    assert is_correct_guess(None, "a") is False
    assert is_correct_guess("a", None) is False
    assert is_correct_guess(None, None) is False


def test_points_for_correct_guess():
    assert points_for(True) == POINTS_PER_CORRECT_GUESS
    assert points_for(False) == 0


def test_rank_scores_orders_best_first():
    assert rank_scores({"a": 0, "b": 1, "c": 1}) == {"b": 1, "c": 1, "a": 3}


def test_rank_scores_shares_place_on_ties():
    ranks = rank_scores({"a": 1, "b": 1, "c": 1, "d": 0})
    assert ranks == {"a": 1, "b": 1, "c": 1, "d": 4}


def test_rank_scores_handles_empty_and_equal():
    assert rank_scores({}) == {}
    assert rank_scores({"a": 0, "b": 0}) == {"a": 1, "b": 1}


def test_can_remove_players_only_before_assignment():
    for phase in (Phase.LOBBY, Phase.FACT_COLLECTION, Phase.READY):
        assert can_remove_players(phase) is True
    for phase in (
        Phase.ASSIGNMENT,
        Phase.INVESTIGATION,
        Phase.GUESSING,
        Phase.REVEAL,
        Phase.FINISHED,
    ):
        assert can_remove_players(phase) is False


def test_game_error_keeps_status_code():
    assert GameError("nope").status_code == 400
    assert GameError("nope", status_code=403).status_code == 403
