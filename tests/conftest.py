"""Test suite for the server-rendered app in ``app/``.

The store is forced to ``memory`` before ``app`` is imported, so tests never
reach Firebase even though the local ``.env`` selects it.
"""

import os

os.environ["PFD_STORE"] = "memory"

import pytest
from fastapi.testclient import TestClient

from app import store as store_module
from app.main import app as fastapi_app
from app.memory_store import MemoryStore


class Actor:
    """One browser session (its own cookie jar) acting inside a room."""

    def __init__(self, client: TestClient, code: str):
        self.client = client
        self.code = code

    def get(self, path: str = "", **kwargs):
        return self.client.get(f"/rooms/{self.code}{path}", **kwargs)

    def panel(self, **kwargs):
        """The realtime fragment: just the phase panel, no page shell."""
        return self.get("?fragment=1", **kwargs)

    def post(self, path: str, data=None, **kwargs):
        # ``TestClient`` follows redirects by default; tests assert on the
        # redirect itself, so opt out unless a test asks for the final page.
        kwargs.setdefault("follow_redirects", False)
        return self.client.post(f"/rooms/{self.code}{path}", data=data or {}, **kwargs)


@pytest.fixture(autouse=True)
def memory_store():
    """A fresh in-process store for every test."""
    fresh = MemoryStore()
    store_module._store = fresh
    yield fresh
    store_module._store = None


@pytest.fixture()
def host(memory_store):
    """A host session with a freshly created room."""
    with TestClient(fastapi_app) as client:
        response = client.post("/rooms", follow_redirects=False)
        assert response.status_code == 303
        yield Actor(client, response.headers["location"].rsplit("/", 1)[-1])


def join(host: Actor, name: str) -> Actor:
    """A participant session that has joined the host's room."""
    client = TestClient(fastapi_app)
    response = client.post(
        f"/rooms/{host.code}/join", data={"name": name}, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    return Actor(client, host.code)


def room_of(memory_store, host: Actor):
    return memory_store.rooms[host.code]


def player_id_named(memory_store, host: Actor, name: str) -> str:
    for player in room_of(memory_store, host).players.values():
        if player.name == name:
            return player.id
    raise AssertionError(f"no player named {name!r}")
