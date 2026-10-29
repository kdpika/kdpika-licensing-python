"""Phase D only: signed synthetic transport, no real network or persistent keys."""
import asyncio
import hashlib

import pytest

from kdpika_licensing import (AsyncLicenseClient, CreditOperationError, InsufficientCreditsError,
                             LicenseClient, NetworkError, SignatureVerificationError)
from kdpika_licensing._json import canonical
from kdpika_licensing.models import HttpResponse
from test_security import MockTransport, NOW


class CreditTransport(MockTransport):
    def __init__(self, now):
        super().__init__(now)
        self.balance = 5
        self.ledger = {}
        self.drop_after_consume = False
        self.tamper_receipt = False
        self.changes.update(metered=True, credit_balance=5, total_allocated=5, credit_transaction=None)

    def answer(self, body, status=200):
        return HttpResponse.from_bytes(status, {}, canonical(body))

    def request(self, method, path, body=None, headers=None):
        if self.network:
            raise NetworkError()
        if path.endswith(("/consume", "/validate")):
            self.calls.append((method, path))
            self.changes.update(credit_balance=self.balance, credit_transaction=None)
            if path.endswith("/validate"):
                return self.answer({"success": True, "license": self.signed(self.last_device)})
            amount, key = body["amount"], body.get("idempotency_key")
            previous = self.ledger.get(key) if key else None
            if previous and previous["amount"] != -amount:
                return self.answer({"success": False, "error": {"code": "IDEMPOTENCY_CONFLICT"}}, 409)
            if not previous and self.balance < amount:
                return self.answer({"success": False, "error": {"code": "INSUFFICIENT_CREDITS"}, "balance": self.balance, "license": self.signed(self.last_device)}, 402)
            if previous:
                receipt = dict(previous, replayed=True)
            else:
                self.balance -= amount
                receipt = {"id": "ctx_fixture_" + str(len(self.ledger)), "type": "consume", "amount": -amount,
                           "balance_after": self.balance, "total_allocated_after": 5,
                           "idempotency_hash": hashlib.sha256(key.encode()).hexdigest() if key else None,
                           "replayed": False}
                if key:
                    self.ledger[key] = receipt
            self.changes.update(credit_balance=self.balance, credit_transaction=receipt)
            if self.drop_after_consume:
                self.drop_after_consume = False
                raise NetworkError()
            return self.answer({"success": True, "license": self.signed(self.last_device),
                                "balance": receipt["balance_after"] + int(self.tamper_receipt), "consumed": amount,
                                "transaction_id": receipt["id"], "replayed": receipt["replayed"]})
        self.changes.update(credit_balance=self.balance, credit_transaction=None)
        return super().request(method, path, body, headers)


@pytest.fixture
def app(tmp_path):
    transport = CreditTransport([NOW])
    client = LicenseClient("app_synthetic", "sandbox", "https://licenses.example.invalid", storage_dir=tmp_path,
                           prefer_keyring=False, transport=transport, clock=lambda: NOW)
    return client, transport


def test_consume_replay_historical_receipt_and_current_balance(app):
    client, transport = app
    assert client.activate("SYNTHETIC-CREDIT-LICENSE").valid
    receipt = client.consume(2, "operation-fixture-1")
    assert receipt.balance == 3 and receipt.consumed == 2 and not receipt.replayed
    assert client.consume(3, "operation-fixture-2").balance == 0
    replay = client.consume(2, "operation-fixture-1")
    assert replay.transaction_id == receipt.transaction_id and replay.replayed and replay.balance == 3
    assert client.get_balance() == 0 and len(transport.ledger) == 2
    result = client.validate()
    assert result.valid and result.signature_valid
    assert result.feature("export", True)


def test_zero_activation_keeps_identity_for_topup_without_reactivation(app):
    client, transport = app
    transport.balance = 0
    result = client.activate("SYNTHETIC-CREDIT-LICENSE")
    assert result.valid and client.activated
    assert client.get_balance() == 0
    transport.balance = 4
    assert client.get_balance() == 4 and client.check().valid


def test_insufficient_typed_error_is_verified_and_does_not_charge(app):
    client, transport = app
    client.activate("SYNTHETIC-CREDIT-LICENSE")
    with pytest.raises(InsufficientCreditsError) as caught:
        client.consume(6, "overdraw-fixture")
    assert caught.value.code == "INSUFFICIENT_CREDITS" and caught.value.balance == 5
    assert transport.balance == 5 and not transport.ledger


def test_conflicting_key_is_not_retried_or_charged(app):
    client, transport = app
    client.activate("SYNTHETIC-CREDIT-LICENSE")
    client.consume(1, "conflict-fixture")
    with pytest.raises(CreditOperationError) as caught:
        client.consume(2, "conflict-fixture")
    assert caught.value.code == "IDEMPOTENCY_CONFLICT" and transport.balance == 4


def test_no_cached_or_offline_metered_grants(app):
    client, transport = app
    client.activate("SYNTHETIC-CREDIT-LICENSE")
    before = len(transport.calls)
    assert client.check().source == "online" and len(transport.calls) == before + 1
    transport.network = True
    result = client.check()
    assert not result.valid and result.error_code == "METERED_ONLINE_REQUIRED"
    assert not result.feature("export", True)
    with pytest.raises(NetworkError):
        client.consume(1, "offline-fixture")
    with pytest.raises(CreditOperationError):
        client.get_balance()


def test_network_outcome_requires_explicit_retry_with_same_key(app):
    client, transport = app
    client.activate("SYNTHETIC-CREDIT-LICENSE")
    transport.drop_after_consume = True
    with pytest.raises(NetworkError):
        client.consume(2, "durable-job-fixture")
    assert transport.balance == 3 and len(transport.ledger) == 1
    assert client.consume(2, "durable-job-fixture").replayed and transport.balance == 3


@pytest.mark.parametrize("amount", [0, -1, 1.5, True, "1", 9007199254740992])
def test_invalid_amount_never_reaches_network(app, amount):
    client, transport = app
    with pytest.raises(ValueError):
        client.consume(amount, "invalid-fixture")
    assert not transport.calls


def test_tampered_signature_or_unsigned_receipt_is_rejected(app):
    client, transport = app
    client.activate("SYNTHETIC-CREDIT-LICENSE")
    transport.tamper_receipt = True
    with pytest.raises(SignatureVerificationError):
        client.consume(1, "tampered-fixture")
    transport.tamper_receipt = False
    transport.bad_signature = True
    with pytest.raises(SignatureVerificationError):
        client.consume(1, "signature-fixture")


def test_signed_zero_denial_and_wrong_tenant_binding_fail_closed(app):
    client, transport = app
    client.activate("SYNTHETIC-CREDIT-LICENSE")
    transport.balance = 0
    transport.changes["product_id"] = "another_tenant_app"
    assert client.validate().error_code == "SIGNATURE_INVALID"
    with pytest.raises(SignatureVerificationError):
        client.consume(1, "wrong-tenant-fixture")


def test_regular_license_and_async_wrappers(app):
    client, transport = app
    assert client.activate("SYNTHETIC-CREDIT-LICENSE").valid
    async_client = AsyncLicenseClient(client)
    assert asyncio.run(async_client.consume(1, "async-job-fixture")).balance == 4
    assert asyncio.run(async_client.get_balance()) == 4
    transport.changes["metered"] = False
    with pytest.raises(CreditOperationError) as caught:
        client.get_balance()
    assert caught.value.code == "NOT_METERED_LICENSE"
