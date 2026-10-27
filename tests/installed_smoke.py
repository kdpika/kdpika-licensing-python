"""Run directly with a fresh wheel/sdist install. Base dependencies only."""

import base64
import hashlib
import sys
import tempfile
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import kdpika_licensing
from kdpika_licensing import AsyncLicenseClient, LicenseClient, NetworkError
from kdpika_licensing._json import canonical
from kdpika_licensing._fingerprint import hash_components
import kdpika_licensing.client as client_module

# Synthetic hardware is confined to installed-package tests, never SDK runtime.
client_module.collect_fingerprint = lambda product: hash_components(product, {"baseboard": "installed-fixture", "cpu": "installed-fixture-cpu"})
from kdpika_licensing.models import HttpResponse


class Transport:
    def __init__(self):
        self.private = Ed25519PrivateKey.generate()
        raw = self.private.public_key().public_bytes_raw()
        self.key = {
            "algorithm": "Ed25519",
            "encoding": "base64url",
            "public_key": self.encode(raw),
            "key_id": "ed25519_" + hashlib.sha256(raw).hexdigest()[:16],
        }
        self.device = None
        self.offline = False

    @staticmethod
    def encode(raw):
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def request(self, method, path, body=None, headers=None):
        if self.offline:
            raise NetworkError()
        if path.endswith("public-key"):
            return HttpResponse(200, {}, {"success": True, "key": self.key})
        if path.endswith("deactivate"):
            return HttpResponse(200, {}, {"success": True, "deactivated": True})
        if path.endswith("activate"):
            self.device = body["device_id"]
        now = datetime.now(UTC)
        payload = {
            "product_id": "app_synthetic",
            "application_access": "both",
            "application_type": headers["X-Application-Type"],
            "environment": "sandbox",
            "license_id": "lic_synthetic",
            "status": "active",
            "device": {"installation_hash": hashlib.sha256(self.device.encode()).hexdigest(), "fingerprint": client_module.collect_fingerprint("app_synthetic") | {"policy": {"mode": "strict"}}},
            "floating": None, "metered": False, "credit_balance": 0, "total_allocated": 0, "credit_transaction": None,
            "server_time": now.isoformat(),
            "expires_at": (now + timedelta(days=3)).isoformat(),
            "next_validation_at": (now + timedelta(hours=1)).isoformat(),
            "offline_grace_until": (now + timedelta(days=1)).isoformat(),
            "features": {"export": True, "limit": 19.0, "unicode": "a\u2028b"},
        }
        envelope = {
            "payload": payload,
            "signature": self.encode(self.private.sign(canonical(payload))),
            "algorithm": "Ed25519",
            "key_id": self.key["key_id"],
        }
        return HttpResponse.from_bytes(
            200,
            {},
            canonical(
                {
                    "success": True,
                    "activation_token": "act_synthetic_not_real",
                    "license": envelope,
                    "request_id": "req_synthetic",
                }
            ),
        )


def main():
    location = Path(kdpika_licensing.__file__).resolve()
    assert location.is_relative_to(Path(sys.prefix).resolve()), "Not an installed package"
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        import license_sdk

        assert license_sdk.LicenseClient is LicenseClient and recorded
    assert AsyncLicenseClient
    with tempfile.TemporaryDirectory(prefix="kdpika-installed-state-") as folder:
        transport = Transport()
        client = LicenseClient(
            "app_synthetic",
            "sandbox",
            "https://example.invalid",
            storage_dir=Path(folder),
            prefer_keyring=False,
            transport=transport,
        )
        result = client.activate("SYNTHETIC-NOT-A-REAL-LICENSE", "tester@example.invalid")
        assert (
            result.valid
            and result.signature_valid
            and result.feature("export")
            and result.feature_value("limit") == 19.0
        ), f"{result.error_code}: {result.message}"
        refreshed = client.validate()
        assert refreshed.valid and refreshed.signature_valid
        cached = client.check()
        assert cached.valid and cached.signature_valid and cached.source == "cache"
        restarted = LicenseClient(
            "app_synthetic",
            "sandbox",
            "https://example.invalid",
            storage_dir=Path(folder),
            prefer_keyring=False,
            transport=transport,
        )
        assert restarted.installation_id == client.installation_id
        transport.offline = True
        offline = restarted.validate()
        assert offline.valid and offline.signature_valid and offline.source == "offline"
        transport.offline = False
        released = client.deactivate()
        assert released.valid and not released.feature("export", True) and not client.activated
        assert not client.check().valid
    assert "PyQt6" not in sys.modules and "keyring" not in sys.modules
    print(
        "PASS installed package "
        + kdpika_licensing.__version__
        + "; signed activation/cache/offline/deactivation; compatibility warning; no GUI/keyring imports"
    )


if __name__ == "__main__":
    main()
