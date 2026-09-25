import random

import pytest

from app.game import GameError, generate_derangement, validate_assignment


@pytest.mark.parametrize("count", [2, 3, 4, 5, 7, 10])
def test_derangement_no_self_assignment_and_permutation(count):
    ids = [f"p{i}" for i in range(count)]
    mapping = generate_derangement(ids)

    assert set(mapping.keys()) == set(ids)
    assert sorted(mapping.values()) == sorted(ids)
    for giver, receiver in mapping.items():
        assert giver != receiver


def test_derangement_is_randomised():
    ids = [f"p{i}" for i in range(7)]
    results = {tuple(sorted(generate_derangement(ids).items())) for _ in range(50)}
    # With 7 players there are many derangements; 50 draws should not all match.
    assert len(results) > 1


def test_derangement_deterministic_with_seed():
    ids = [f"p{i}" for i in range(7)]
    a = generate_derangement(ids, rng=random.Random(123))
    b = generate_derangement(ids, rng=random.Random(123))
    assert a == b


@pytest.mark.parametrize("count", [0, 1])
def test_derangement_requires_two_players(count):
    with pytest.raises(GameError):
        generate_derangement([f"p{i}" for i in range(count)])


def test_derangement_rejects_duplicate_ids():
    with pytest.raises(GameError):
        generate_derangement(["a", "a", "b"])


def test_validate_assignment_accepts_valid():
    ids = ["a", "b", "c", "d"]
    validate_assignment({"a": "b", "b": "a", "c": "d", "d": "c"}, ids)


def test_validate_assignment_rejects_self_assignment():
    ids = ["a", "b", "c"]
    with pytest.raises(GameError):
        validate_assignment({"a": "a", "b": "c", "c": "b"}, ids)


def test_validate_assignment_rejects_duplicate_receiver():
    ids = ["a", "b", "c"]
    with pytest.raises(GameError):
        validate_assignment({"a": "b", "b": "b", "c": "a"}, ids)
