import os
import sys

import pytest
from fastapi.testclient import TestClient

# Ensure the backend root (containing the ``app`` package) is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app, room_manager  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_rooms():
    room_manager.rooms.clear()
    yield
    room_manager.rooms.clear()


def create_room(client):
    resp = client.post("/api/rooms")
    assert resp.status_code == 200, resp.text
    return resp.json()


def join_player(client, room_code, name):
    resp = client.post(f"/api/rooms/{room_code}/join", json={"name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()


def setup_room_with_players(client, n=7):
    room = create_room(client)
    players = []
    for i in range(n):
        players.append(join_player(client, room["room_code"], f"Player{i + 1}"))
    return room, players


def submit_facts(client, room_code, players):
    for i, p in enumerate(players):
        resp = client.post(
            f"/api/rooms/{room_code}/facts",
            json={"token": p["participant_token"], "fact": f"Secret fact number {i + 1}"},
        )
        assert resp.status_code == 200, resp.text
