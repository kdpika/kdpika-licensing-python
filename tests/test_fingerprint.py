"""Phase B only: synthetic OS data/keys; no live network or hardware collection."""
import hashlib
import json

import pytest

import kdpika_licensing._fingerprint as hardware
import kdpika_licensing.client as client_module
from kdpika_licensing import LicenseClient
from kdpika_licensing._json import canonical, loads
from test_security import NOW, MockTransport


RAW = {"baseboard": "TEST-BOARD-PRIVATE", "cpu": "TEST-CPU-PRIVATE", "disk": "TEST-DISK-PRIVATE"}


def binding(fingerprint, mode="strict", minimum=2):
    return fingerprint | {"policy": {"mode": mode, "min_matches": minimum}}


class FingerprintTransport(MockTransport):
    def __init__(self, now):
        super().__init__(now)
        self.received = []
        self.binding = None

    def request(self, method, path, body=None, headers=None):
        if path.endswith(("/activate", "/validate")):
            self.received.append(body)
            identity = body["device_id"] if path.endswith("/activate") else headers["X-Installation-ID"]
            self.changes["device"] = {"installation_hash": hashlib.sha256(identity.encode()).hexdigest(),
                                      "fingerprint": self.binding}
        return super().request(method, path, body, headers)


@pytest.fixture
def app(tmp_path, monkeypatch):
    current = [hardware.hash_components("app_synthetic", RAW, True)]
    monkeypatch.setattr(client_module, "collect_fingerprint", lambda product: current[0])
    transport = FingerprintTransport([NOW])
    transport.binding = binding(current[0])
    client = LicenseClient("app_synthetic", "sandbox", "https://licenses.example.invalid",
                           storage_dir=tmp_path, prefer_keyring=False, transport=transport,
                           clock=lambda: NOW)
    return client, transport, current


def test_product_salt_hashing_and_no_cpu_only_fallback():
    one = hardware.hash_components("app_one", RAW)
    two = hardware.hash_components("app_two", RAW)
    assert one["hardware_id"] != two["hardware_id"]
    assert all(len(value) == 64 for value in one["components"].values())
    assert not any(value in json.dumps(one) for value in RAW.values())
    assert hardware.hash_components("app_one", {key: " " + value.lower() + " " for key, value in RAW.items()}) == one
    for raw in ({}, {"baseboard": "To be filled by O.E.M.", "cpu": "model"}, {"machine": "0000-0000"}):
        with pytest.raises(hardware.HardwareUnavailable):
            hardware.hash_components("app_one", raw)


def test_strict_fuzzy_critical_missing_and_minimum():
    original = hardware.hash_components("app_one", RAW)
    disk = hardware.hash_components("app_one", RAW | {"disk": "CHANGED"})
    assert hardware.matches_binding(binding(original), original)
    assert not hardware.matches_binding(binding(original), disk)
    assert hardware.matches_binding(binding(original, "fuzzy"), disk)
    assert not hardware.matches_binding(binding(original, "fuzzy", 3), disk)
    assert not hardware.matches_binding(binding(original, "fuzzy", 1), hardware.hash_components("app_one", RAW | {"baseboard": "CHANGED"}))
    assert not hardware.matches_binding(binding(original, "fuzzy", 1), hardware.hash_components("app_one", {"baseboard": RAW["baseboard"], "disk": RAW["disk"]}))
    assert not hardware.matches_binding(None, original)
    assert not hardware.matches_binding(binding(original) | {"hardware_id": "0" * 64}, original)
    # Preserve the SDK's lossless signed JSON integer subclasses (but never bool).
    assert hardware.matches_binding(loads(canonical(binding(original))), original)
    assert hardware.matches_binding(loads(canonical(binding(original, "fuzzy"))), disk)
    assert not hardware.matches_binding(binding(original) | {"version": True}, original)


def test_activate_validate_and_private_storage(app, tmp_path):
    client, transport, current = app
    assert client.activate("TEST-KEY-FOR-FIXTURE").valid
    assert transport.received[-1]["fingerprint"] == current[0]
    assert client.validate().valid
    assert transport.received[-1] == {"fingerprint": current[0], "session_token": None}
    for file in tmp_path.rglob("*"):
        if file.is_file():
            contents = file.read_bytes()
            assert all(value.encode() not in contents for value in RAW.values())


def test_cloned_cache_and_offline_are_rejected(app):
    client, transport, current = app
    assert client.activate("TEST-KEY-FOR-FIXTURE").valid
    current[0] = hardware.hash_components("app_synthetic", RAW | {"baseboard": "ANOTHER-BOARD"})
    transport.network = True
    result = client.check()
    assert not result.valid and result.error_code == "FINGERPRINT_MISMATCH"
    assert result.feature("export") is False


def test_fuzzy_cached_hardware_change_and_vm_hint(app):
    client, transport, current = app
    transport.binding = binding(current[0], "fuzzy")
    assert client.activate("TEST-KEY-FOR-FIXTURE").valid  # VM hint true is not a denial.
    current[0] = hardware.hash_components("app_synthetic", RAW | {"disk": "NEW-DISK"}, True)
    assert client.check().valid


def test_authoritative_rejection_clears_grant(app):
    client, transport, _ = app
    assert client.activate("TEST-KEY-FOR-FIXTURE").valid
    transport.status = "FINGERPRINT_MISMATCH"
    result = client.validate()
    assert not result.valid and result.error_code == "FINGERPRINT_MISMATCH"
    assert not client.activated
    assert not client._local.load_state()


def test_missing_signed_binding_is_rejected(app):
    client, transport, _ = app
    transport.binding = None
    result = client.activate("TEST-KEY-FOR-FIXTURE")
    assert not result.valid and result.error_code == "FINGERPRINT_MISMATCH"
    assert not client.activated


def test_unavailable_hardware_fails_locally_without_sending(app, monkeypatch):
    client, transport, _ = app
    def unavailable(product):
        raise hardware.HardwareUnavailable("Device information is unavailable.")
    monkeypatch.setattr(client_module, "collect_fingerprint", unavailable)
    result = client.activate("TEST-KEY-FOR-FIXTURE")
    assert not result.valid and result.error_code == "HARDWARE_UNAVAILABLE"
    assert not transport.calls


@pytest.mark.parametrize("system", ["Windows", "Darwin", "Linux"])
def test_os_collectors_hash_before_returning(system, monkeypatch):
    monkeypatch.setattr(hardware.platform, "system", lambda: system)
    monkeypatch.setattr(hardware.Path, "iterdir", lambda self: iter([]))
    monkeypatch.setattr(hardware, "_read", lambda file: {
        "/sys/class/dmi/id/board_serial": RAW["baseboard"],
        "/proc/cpuinfo": "model name : " + RAW["cpu"],
        "/sys/class/dmi/id/product_name": "Virtual Machine",
    }.get(file, ""))
    def command(file, *args):
        if file == "powershell.exe":
            return json.dumps(RAW | {"model": "Virtual Machine"})
        if file.endswith("ioreg"):
            return '"IOPlatformUUID" = "' + RAW["baseboard"] + '" Virtual Machine'
        if file.endswith("sysctl"):
            return RAW["cpu"]
        return ""
    monkeypatch.setattr(hardware, "_run", command)
    result = hardware.collect_fingerprint("app_synthetic")
    assert result["is_virtual"] is True
    assert result["components"]["baseboard"] == hardware.hash_components("app_synthetic", RAW)["components"]["baseboard"]
    assert all(value not in json.dumps(result) for value in RAW.values())
