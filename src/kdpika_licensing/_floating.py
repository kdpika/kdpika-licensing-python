"""Private seat state and a stoppable heartbeat; no offline seat extension."""
from __future__ import annotations

import hashlib
import threading
import weakref
from datetime import datetime
from typing import Any

from ._storage import LocalStateStore
from ._verification import timestamp
from .errors import StorageError


def lease_valid(payload: dict[str, Any], token: str | None, now: datetime) -> bool:
    if "floating" not in payload:
        return False
    policy = payload["floating"]
    if policy is None:
        return True
    if not isinstance(policy, dict) or not isinstance(policy.get("max_concurrent_sessions"), int) or isinstance(policy["max_concurrent_sessions"], bool) or policy["max_concurrent_sessions"] < 1:
        return False
    session = policy.get("session")
    if not isinstance(session, dict) or not token:
        return False
    try:
        return (now < timestamp(session["expires_at"])
                and session.get("token_hash") == hashlib.sha256(token.encode()).hexdigest())
    except (ValueError, TypeError, KeyError, OverflowError):
        return False


class FloatingState:
    def __init__(self, store: LocalStateStore) -> None:
        self.store = store
        self.path = store.root / "floating-session.json"
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.interval = 180

    def token(self) -> str | None:
        try:
            value = (self.store._read_json(self.path) or {}).get("session_token")
            return value if isinstance(value, str) and value.startswith("flt_") and len(value) == 47 else None
        except StorageError:
            return None

    def save(self, token: str) -> None:
        self.store._write_json(self.path, {"session_token": token})

    def clear(self) -> None:
        self.store._unlink(self.path)

    def stop(self) -> None:
        self.stop_event.set()

    def start(self, owner: Any) -> None:
        if self.thread is not None and self.thread.is_alive() and not self.stop_event.is_set():
            return
        stop = threading.Event()
        self.stop_event = stop
        reference = weakref.ref(owner)

        def run() -> None:
            while not stop.wait(self.interval):
                client = reference()
                if client is None:
                    return
                try:
                    if not client._background_heartbeat(stop):
                        return
                finally:
                    del client

        self.thread = threading.Thread(target=run, name="kdpika-seat-heartbeat", daemon=True)
        self.thread.start()
