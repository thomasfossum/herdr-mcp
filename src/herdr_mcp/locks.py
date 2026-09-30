"""In-process per-target serialisation.

Two ``agent prompt`` calls issued back to back can concatenate into a single
submitted line and lose the first Enter. A shared lock per agent target keeps
submit+settle ordered when several MCP calls arrive at once (an HTTP server
serving more than one caller, or a chat client firing twice in one second).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

_guard = threading.Lock()
_locks: dict[str, threading.RLock] = {}


def _lock_for(key: str) -> threading.RLock:
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


@contextmanager
def target_lock(key: str):
    lock = _lock_for(key)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()