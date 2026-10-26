"""Whole-client policy regressions. No stored private keys and no customer data."""

import asyncio
import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from kdpika_licensing import (
    AsyncLicenseClient,
    ConfigurationError,
    LicenseClient,
    LicenseResult,
    NetworkError,
    SignatureVerificationError,
    StorageError,
)
from kdpika_licensing._fingerprint import hash_components
from kdpika_licensing._json import canonical, loads
from kdpika_licensing.models import HttpResponse

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


class MockTransport:
    def __init__(self, now):
        self.now = now
        self.private = Ed25519PrivateKey.generate()
        self.calls = []
        self.changes = {}
        self.status = None
        self.network = False
        self.bad_signature = False
        self.missing = None
        self.override = None
        self.key_override = None
        self.last_device = None

    @property
    def key(self):
        raw = self.private.public_key().public_bytes_raw()
        return {
            "algorithm": "Ed25519",
            "encoding": "base64url",
            "key_id": "ed25519_" + hashlib.sha256(raw).hexdigest()[:16],
            "public_key": b64(raw),
        }

    def signed(self, device):
        now = self.now[0]
        payload = {
            "license_id": "lic_synthetic",
            "product_id": "app_synthetic",
            "environment": "sandbox",
            "status": "active",
            "device": {"installation_hash": hashlib.sha256(device.encode()).hexdigest(),
                       "fingerprint": hash_components("app_synthetic", {"baseboard": "fixture-board", "cpu": "fixture-cpu"})
                       | {"policy": {"mode": "fuzzy", "min_matches": 2}}},
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "server_time": now.isoformat(),
            "next_validation_at": (now + timedelta(hours=1)).isoformat(),
            "offline_grace_until": (now + timedelta(days=2)).isoformat(),
            "features": {"export": True, "seats": 3, "string_false": "false"},
            "floating": None,
            "metered": False,
            "credit_balance": 0,
            "total_allocated": 0,
            "credit_transaction": None,
        }
        payload.update(self.changes)
        if self.missing:
            payload.pop(self.missing, None)
        encoded = canonical(payload)
        return {
            "payload": loads(encoded),
            "signature": b64(self.private.sign(encoded)) if not self.bad_signature else b64(bytes(64)),
            "algorithm": "Ed25519",
            "key_id": self.key["key_id"],
        }

    def request(self, method, path, body=None, headers=None):
        self.calls.append((method, path))
        if self.network:
            raise NetworkError("private upstream value must not appear")
        if self.override is not None:
            return self.override
        if path.endswith("public-key"):
            return HttpResponse(
                200,
                {},
                {"success": True, "key": self.key if self.key_override is None else self.key_override},
            )
        if self.status and path.endswith(("activate", "validate", "deactivate")):
            return HttpResponse(
                403,
                {},
                {
                    "success": False,
                    "error": {"code": self.status, "message": "DO_NOT_ECHO_SECRET"},
                    "request_id": "req_synthetic",
                },
            )
        if path.endswith("deactivate"):
            return HttpResponse(200, {}, {"success": True, "deactivated": True, "request_id": "req_released"})
        if path.endswith("activate"):
            self.last_device = body["device_id"]
        data = {"success": True, "license": self.signed(self.last_device), "request_id": "req_synthetic"}
        if path.endswith("activate"):
            data["activation_token"] = "act_synthetic_not_a_real_credential"
        return HttpResponse.from_bytes(200, {}, canonical(data))


@pytest.fixture
def session(tmp_path):
    now = [NOW]
    transport = MockTransport(now)

    def make(**kwargs):
        return LicenseClient(
            "app_synthetic",
            "sandbox",
            "https://licenses.example.invalid",
            storage_dir=tmp_path,
            prefer_keyring=False,
            transport=transport,
            clock=lambda: now[0],
            **kwargs,
        )

    return make, transport, now


def activate(client):
    result = client.activate("SYNTHETIC-NOT-A-REAL-KEY", "tester@example.invalid")
    assert result.valid and result.signature_valid and result.feature("export")
    return result


def denied(result):
    assert not result.valid
    assert not result.feature("export", True)
    assert result.feature_value("seats", 999) is None
    assert result.features == {}


@pytest.mark.parametrize(
    "changes",
    [
        {"environment": "live"},
        {"environment": 3},
        {"product_id": "another"},
        {"device": {}},
        {"device": None},
        {"status": "revoked"},
        {"status": "suspended"},
        {"status": "expired"},
        {"expires_at": "not-a-date"},
        {"expires_at": False},
        {"server_time": None},
        {"next_validation_at": "2026-10-20T12:00:00"},
        {"offline_grace_until": "bad"},
        {"next_validation_at": "2025-01-01T00:00:00Z"},
        {"offline_grace_until": "2025-01-01T00:00:00Z"},
        {"expires_at": "2025-01-01T00:00:00Z"},
    ],
)
def test_every_refused_signed_policy_denies_all_features(session, changes):
    make, transport, _ = session
    transport.changes = changes
    client = make()
    denied(client.activate("SYNTHETIC-NOT-A-REAL-KEY"))
    assert not client.activated


@pytest.mark.parametrize(
    "missing", ["server_time", "next_validation_at", "offline_grace_until", "expires_at"]
)
def test_missing_signed_time_is_not_lifetime(session, missing):
    make, transport, _ = session
    transport.missing = missing
    denied(make().activate("SYNTHETIC-NOT-A-REAL-KEY"))


@pytest.mark.parametrize(
    "code",
    [
        "INVALID_TOKEN",
        "LICENSE_REVOKED",
        "LICENSE_EXPIRED",
        "LICENSE_CANCELLED",
        "LICENSE_SUSPENDED",
        "DEVICE_MISMATCH",
        "MAX_DEVICES_REACHED",
        "RATE_LIMITED",
        "unknown-attacker-value",
    ],
)
def test_authoritative_refusals_never_reuse_old_cache(session, code):
    make, transport, _ = session
    client = make()
    activate(client)
    transport.status = code
    result = client.validate()
    denied(result)
    assert "DO_NOT_ECHO_SECRET" not in str(result) + result.message
    assert result.request_id == "req_synthetic"
    transport.network = True
    denied(client.check())


def test_fresh_restart_unicode_numeric_cache_roundtrip(session):
    make, transport, _ = session
    transport.changes = loads(
        b'{"product":"A\\u2028B\\u2029","features":{"export":true,"seats":19.0,"small":1.0e-7,"big":1.0e+20,"integer":9007199254740993}}'
    )
    first = make()
    result = activate(first)
    second = make()
    assert second.installation_id == first.installation_id
    transport.network = True
    cached = second.check()
    assert cached.valid and cached.source == "cache"
    assert cached.feature_value("seats") == 19.0
    assert cached.feature_value("integer") == 9007199254740993
    assert "payload" not in repr(result) and "act_synthetic" not in repr(result)


def test_held_result_expires_and_cannot_be_mutated_into_permission(session):
    make, _, now = session
    result = activate(make())
    result.payload["features"]["seats"] = 999
    copy = result.features
    copy["seats"] = 888
    assert result.feature_value("seats") == 3
    assert not result.feature("string_false")
    now[0] += timedelta(days=3)
    assert not result.feature("export", True)
    assert result.feature_value("seats", 999) is None


@pytest.mark.parametrize("valid,signed", [(False, True), (True, False), (False, False)])
def test_constructed_failure_defaults_never_enable(valid, signed):
    result = LicenseResult(valid, "local", {"features": {"export": True}}, signature_valid=signed)
    assert not result.feature("export", True)
    assert result.feature_value("seats", 999) is None


def test_time_rollbacks_grace_expiry_and_checkpoint(session):
    make, transport, now = session
    client = make()
    activate(client)
    now[0] -= timedelta(minutes=6)
    denied(client.check())
    now[0] = NOW
    activate(client)
    now[0] = NOW + timedelta(hours=2)
    transport.network = True
    assert client.check().source == "offline"
    now[0] += timedelta(days=3)
    assert client.check().error_code == "OFFLINE_GRACE_EXPIRED"
    denied(client.check())


def test_expiry_lifetime_and_unaware_clock(session):
    make, transport, now = session
    transport.changes = {"expires_at": None}
    assert activate(make()).expires_at is None
    now[0] = NOW.replace(tzinfo=None)
    denied(make().validate())


def test_pin_rotation_and_unknown_key_offline_do_not_downgrade(session):
    make, transport, _ = session
    client = make(verification_key=transport.key)
    activate(client)
    transport.private = Ed25519PrivateKey.generate()
    result = client.validate()
    assert result.error_code == "KEY_ROTATION_REQUIRED"
    denied(result)
    assert sum(p.endswith("public-key") for _, p in transport.calls) == 0


def test_unpinned_rotation_refetch_is_bounded(session, monkeypatch):
    make, transport, _ = session
    tick = [10.0]
    monkeypatch.setattr("kdpika_licensing.client.time.monotonic", lambda: tick[0])
    client = make()
    activate(client)
    transport.private = Ed25519PrivateKey.generate()
    denied(client.validate())
    assert sum(p.endswith("public-key") for _, p in transport.calls) == 1
    tick[0] += 11
    assert client.validate().valid
    assert sum(p.endswith("public-key") for _, p in transport.calls) == 2


@pytest.mark.parametrize(
    "key",
    [
        {},
        {"algorithm": "RSA"},
        {"algorithm": "Ed25519", "encoding": "base64url", "key_id": "wrong", "public_key": "bad"},
    ],
)
def test_malformed_fetched_key_fails(session, key):
    make, transport, _ = session
    transport.key_override = key
    denied(make().activate("SYNTHETIC-NOT-A-REAL-KEY"))


def test_bad_signature_does_not_leave_stale_grant(session):
    make, transport, _ = session
    client = make()
    activate(client)
    transport.bad_signature = True
    denied(client.validate())
    transport.network = True
    denied(client.check())


def test_corrupted_cache_recovers_online_not_by_new_identity(session):
    make, transport, _ = session
    client = make()
    activate(client)
    identity = client.installation_id
    client._local.state_path.write_bytes(b"{broken")
    assert client.validate().valid and client.installation_id == identity
    client._local.state_path.write_bytes(b"{broken")
    transport.network = True
    denied(client.validate())


def test_empty_bad_configuration_and_loopback_optin(tmp_path):
    for options in [
        {"product": ""},
        {"environment": "wrong"},
        {"base_url": "http://example.invalid"},
        {"base_url": "https://user:pass@example.invalid"},
        {"base_url": "https://example.invalid/x"},
        {"base_url": "http://127.0.0.1"},
    ]:
        with pytest.raises(ConfigurationError):
            LicenseClient(storage_dir=tmp_path, **{"product": "app_test", **options})
    LicenseClient(
        "app_test",
        base_url="http://127.0.0.1:1234",
        allow_loopback_http=True,
        storage_dir=tmp_path,
        prefer_keyring=False,
    )


def test_public_members_and_async_wrapper(session):
    make, transport, _ = session
    client = make()
    assert not client.activated
    denied(client.check())
    denied(client.deactivate())
    denied(client.activate(""))
    transport.network = True
    denied(client.activate("SYNTHETIC-NOT-A-REAL-KEY"))
    transport.network = False

    async def exercise():
        other = AsyncLicenseClient(client)
        assert not await other.is_activated()
        assert (await other.activate("SYNTHETIC-NOT-A-REAL-KEY")).valid
        assert await other.feature("export")
        assert await other.feature_value("seats") == 3
        assert (await other.check()).valid and (await other.validate()).valid
        assert other.storage_security == "permission-protected-file"
        released = await other.deactivate()
        assert released.valid and not released.feature("export", True)
        await other.reset_local()
        assert not await other.is_activated()

    asyncio.run(exercise())
    with pytest.warns(DeprecationWarning):
        assert client.local is client._local
    with pytest.warns(DeprecationWarning):
        assert client.credentials is client._credentials
    with pytest.warns(DeprecationWarning):
        assert client.transport is transport
    with pytest.warns(DeprecationWarning):
        client.transport = transport


@pytest.mark.parametrize("cls", [ConfigurationError, NetworkError, StorageError, SignatureVerificationError])
def test_exception_repr_and_request_ids_do_not_echo_input(cls):
    error = cls("DO_NOT_ECHO_SECRET", request_id="act_synthetic_secret")
    assert "DO_NOT_ECHO_SECRET" not in str(error) + repr(error) and error.request_id is None
    assert cls(request_id="req_synthetic").request_id == "req_synthetic"
