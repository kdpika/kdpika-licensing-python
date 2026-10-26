"""Phase C only. Ephemeral signatures, mocked transport, synthetic hardware/time."""
import asyncio
import hashlib
import threading
from datetime import timedelta

import pytest

from kdpika_licensing import AllSeatsInUseError, AsyncLicenseClient, LicenseClient
from kdpika_licensing._floating import FloatingState, lease_valid
from kdpika_licensing._json import canonical
from kdpika_licensing.models import HttpResponse
from test_security import MockTransport, NOW


class SeatTransport(MockTransport):
    def __init__(self, now):
        super().__init__(now)
        self.seat_token = "flt_" + "A" * 43
        self.held = False
        self.full = False
        self.fail_heartbeat_once = False
        self.bad_hash = False
        self.request_bodies = []
        self.changes["floating"] = self.policy()

    def policy(self):
        session = None
        if self.held:
            session = {"id": "ses_fixture", "token_hash": hashlib.sha256(self.seat_token.encode()).hexdigest(),
                       "checked_out_at": self.now[0].isoformat(), "last_heartbeat_at": self.now[0].isoformat(),
                       "expires_at": (self.now[0] + timedelta(seconds=600)).isoformat()}
            if self.bad_hash:
                session["token_hash"] = "0" * 64
        return {"max_concurrent_sessions": 1, "heartbeat_interval_seconds": 180,
                "session_timeout_seconds": 600, "session": session}

    def answer(self, body, status=200):
        return HttpResponse.from_bytes(status, {}, canonical(body))

    def request(self, method, path, body=None, headers=None):
        self.request_bodies.append((path, body))
        if path.endswith(("/checkout", "/heartbeat", "/checkin")):
            self.calls.append((method, path))
            if self.network:
                from kdpika_licensing import NetworkError
                raise NetworkError()
            if path.endswith("/checkout"):
                if self.full:
                    return self.answer({"success": False, "error": {"code": "ALL_SEATS_IN_USE"}}, 409)
                self.held = True
            elif path.endswith("/heartbeat") and self.fail_heartbeat_once:
                self.fail_heartbeat_once = False
                self.held = False
                return self.answer({"success": False, "error": {"code": "SESSION_NOT_FOUND"}}, 409)
            elif path.endswith("/checkin"):
                self.held = False
                return self.answer({"success": True, "checked_in": True})
            self.changes["floating"] = self.policy()
            return self.answer({"success": True, "session_token": self.seat_token,
                                "license": self.signed(self.last_device)})
        if path.endswith("/validate") and not self.held:
            return self.answer({"success": False, "error": {"code": "SESSION_NOT_FOUND"}}, 409)
        if path.endswith("/activate"):
            self.changes["floating"] = self.policy()
        return super().request(method, path, body, headers)


@pytest.fixture
def app(tmp_path):
    now = [NOW]
    transport = SeatTransport(now)
    client = LicenseClient("app_synthetic", "sandbox", "https://licenses.example.invalid",
                           storage_dir=tmp_path, prefer_keyring=False, transport=transport,
                           clock=lambda: now[0])
    yield client, transport, now
    client._floating.stop()
    with client._local.lock():
        client._floating.clear()


def activate(client):
    result = client.activate("SYNTHETIC-FLOATING-LICENSE")
    assert result.valid and result.feature("export")
    return result


def test_activation_automatically_checks_out_and_starts_heartbeat(app):
    client, transport, _ = app
    result = activate(client)
    assert client._floating.thread.is_alive()
    assert client._floating.interval == 180
    assert result.payload["floating"]["session"]["id"] == "ses_fixture"
    requests = [path.rsplit("/", 1)[-1] for _, path in transport.calls]
    assert requests.count("activate") == 1 and requests.count("checkout") == 1
    assert client.validate().valid
    assert transport.request_bodies[-1][1]["session_token"] == transport.seat_token


def test_checkout_repeats_without_extra_identity_or_timer(app):
    client, transport, _ = app
    activate(client)
    thread = client._floating.thread
    assert client.checkout().valid and client.checkout().valid
    assert client._floating.thread is thread
    assert client._floating.token() == transport.seat_token


def test_last_seat_refusal_is_typed_on_explicit_checkout(app):
    client, transport, _ = app
    activate(client)
    transport.full = True
    with pytest.raises(AllSeatsInUseError) as error:
        client.checkout()
    assert error.value.code == "ALL_SEATS_IN_USE"
    assert client._floating.token() is None
    assert not client._local.load_state()


def test_heartbeat_recovers_missing_session_once(app):
    client, transport, _ = app
    activate(client)
    transport.fail_heartbeat_once = True
    assert client.heartbeat().valid
    operations = [path.rsplit("/", 1)[-1] for _, path in transport.calls]
    assert operations[-2:] == ["heartbeat", "checkout"]


def test_background_heartbeat_updates_safe_error_without_extra_retries(app):
    client, transport, _ = app
    activate(client)
    assert client._background_heartbeat(threading.Event())
    transport.fail_heartbeat_once = True
    transport.full = True
    assert not client._background_heartbeat(threading.Event())
    assert client.last_floating_error == "ALL_SEATS_IN_USE"


def test_validate_recovers_a_server_expired_session(app):
    client, transport, _ = app
    activate(client)
    transport.held = False
    assert client.validate().valid
    assert transport.calls[-1][1].endswith("/checkout")


def test_cache_offline_and_held_result_stop_at_lease_expiry(app):
    client, transport, now = app
    result = activate(client)
    transport.network = True
    now[0] += timedelta(seconds=599)
    assert result.feature("export") and client.validate().valid
    now[0] += timedelta(seconds=1)
    assert not result.feature("export")
    denied = client.validate()
    assert not denied.valid and denied.error_code == "SESSION_EXPIRED"
    assert denied.feature("export", True) is False


def test_checkin_immediately_invalidates_held_result_even_on_network_failure(app):
    client, transport, _ = app
    result = activate(client)
    transport.network = True
    assert client.checkin().error_code == "NETWORK_ERROR"
    assert not result.feature("export")
    assert client._floating.token() is None
    assert not client._local.load_state()
    assert client._floating.stop_event.is_set()


def test_checkin_and_close_free_seat_but_keep_activation(app):
    client, transport, _ = app
    result = activate(client)
    client.close()
    assert not transport.held and client.activated
    assert not result.feature("export")
    assert client.checkout().valid
    assert client.checkin().valid


def test_wrong_signed_token_hash_never_grants_or_retains_seat(app):
    client, transport, _ = app
    transport.bad_hash = True
    result = client.activate("SYNTHETIC-FLOATING-LICENSE")
    assert not result.valid and result.error_code == "SESSION_EXPIRED"
    assert client._floating.token() is None and not client._local.load_state()


def test_timer_can_be_exercised_without_waiting_or_live_network(app, monkeypatch):
    client, _, _ = app
    activate(client)
    client._floating.stop()
    callbacks = []
    class FakeThread:
        def __init__(self, *, target, **kwargs):
            callbacks.append(target)
        def start(self):
            pass
        def is_alive(self):
            return True
    monkeypatch.setattr("kdpika_licensing._floating.threading.Thread", FakeThread)
    monkeypatch.setattr(client, "_background_heartbeat", lambda event: False)
    state = FloatingState(client._local)
    state.save("flt_" + "B" * 43)
    state.start(client)
    waits = []
    state.stop_event.wait = lambda seconds: waits.append(seconds) or False
    callbacks[0]()
    assert waits == [180]
    state.stop()


def test_lossless_integer_policy_and_missing_field_fail_closed(app):
    client, transport, now = app
    result = activate(client)  # Real mock wire goes through lossless integer JSON parsing.
    assert lease_valid(result.payload, transport.seat_token, now[0])
    assert not lease_valid({}, transport.seat_token, now[0])
    assert lease_valid({"floating": None}, None, now[0])
    snapshot = dict(result.payload)
    snapshot["floating"] = dict(snapshot["floating"], max_concurrent_sessions=True)
    assert not lease_valid(snapshot, transport.seat_token, now[0])


def test_async_adapter_shares_the_same_lease_and_cleanup(app):
    client, _, _ = app
    async def run():
        async with AsyncLicenseClient(client) as async_client:
            assert (await async_client.activate("SYNTHETIC-FLOATING-LICENSE")).valid
            assert (await async_client.heartbeat()).valid
            assert (await async_client.checkin()).valid
            assert (await async_client.checkout()).valid
    asyncio.run(run())
    assert client._floating.token() is None
