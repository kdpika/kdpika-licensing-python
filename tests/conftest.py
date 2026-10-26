"""Default suite cannot open a real connection. All signing keys are ephemeral."""

import os
import socket
import threading

import pytest
from test_security import session as session


@pytest.fixture(autouse=True)
def synthetic_hardware(monkeypatch, request):
    if request.node.get_closest_marker("live"):
        return
    from kdpika_licensing import client
    from kdpika_licensing._fingerprint import hash_components
    monkeypatch.setattr(client, "collect_fingerprint", lambda product: hash_components(
        product, {"baseboard": "fixture-board", "cpu": "fixture-cpu"}))


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch, request):
    if request.node.get_closest_marker("live") and os.getenv("KDP_RUN_LIVE_SANDBOX") == "1":
        return

    # Windows builds asyncio's private wake-up pipe using socketpair's loopback
    # implementation. Allow only that stdlib operation, never ordinary sockets.
    internal = threading.local()
    original_pair = socket.socketpair

    def socketpair(*args, **kwargs):
        previous = getattr(internal, "socketpair", False)
        internal.socketpair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            internal.socketpair = previous

    def guarded(original):
        def reject(sock, address, *args, **kwargs):
            if (
                getattr(internal, "socketpair", False)
                and isinstance(address, tuple)
                and address[0] in {"127.0.0.1", "::1"}
            ):
                return original(sock, address, *args, **kwargs)
            raise AssertionError("Default tests must use a mock transport, not a live network")

        return reject

    monkeypatch.setattr(socket, "socketpair", socketpair)
    monkeypatch.setattr(socket.socket, "connect", guarded(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded(socket.socket.connect_ex))
