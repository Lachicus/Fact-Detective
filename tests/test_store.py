"""The store is built once per process, even under concurrent first requests."""

import threading
import time

from app import config
from app.memory_store import MemoryStore
from app.store import get_store, reset_store


def test_get_store_is_cached():
    reset_store()
    first = get_store()
    assert get_store() is first
    reset_store()


def test_concurrent_first_requests_build_one_store(monkeypatch):
    """FastAPI runs sync routes in a threadpool, so the first requests race.

    Without the lock in ``get_store`` every thread that arrives during the
    build would construct its own store (and the Firebase backend would try to
    initialize the admin app more than once).
    """
    reset_store()
    builds = []
    original_init = MemoryStore.__init__

    def slow_counting_init(self, ttl_seconds=None):
        builds.append(1)
        # Widen the window in which a second thread could slip in.
        time.sleep(0.05)
        original_init(self, ttl_seconds)

    monkeypatch.setattr(MemoryStore, "__init__", slow_counting_init)

    results = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        results.append(get_store())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 8
    assert len(builds) == 1
    assert all(store is results[0] for store in results)
    reset_store()


def test_reset_store_forces_a_new_backend():
    reset_store()
    first = get_store()
    reset_store()
    assert get_store() is not first
    reset_store()


def test_memory_backend_is_the_default_without_firebase_credentials(monkeypatch):
    monkeypatch.setattr(config.settings, "store_backend", "")
    monkeypatch.setattr(config.settings, "firebase_database_url", "")
    monkeypatch.setattr(config.settings, "firebase_service_account", "")
    monkeypatch.setattr(config.settings, "google_application_credentials", "")
    assert config.settings.resolved_store_backend() == "memory"
