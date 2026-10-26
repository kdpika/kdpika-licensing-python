"""Online-only credit receipts and strict wire-value validation."""
from dataclasses import dataclass
import hashlib
import re
from typing import Any

MAX_CREDITS = 9007199254740991


def credit_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_CREDITS


def credit_policy(payload: dict[str, Any]) -> bool:
    return (isinstance(payload.get("metered"), bool)
            and credit_integer(payload.get("credit_balance"))
            and credit_integer(payload.get("total_allocated")))


def request_values(amount: int, key: str | None, reason: str | None) -> None:
    if not credit_integer(amount) or amount == 0:
        raise ValueError("Use a positive whole number of credits within the supported range.")
    if key is not None and (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,190}", key)):
        raise ValueError("Use an 8–190 character request key: letters, numbers, dot, colon, underscore or hyphen.")
    if reason is not None and (not isinstance(reason, str) or len(reason) > 190 or re.search(r"[\x00-\x1f\x7f]", reason)):
        raise ValueError("Use a short single-line credit note.")


@dataclass(frozen=True)
class CreditConsumption:
    """Authenticated receipt. On replay, balance is the ORIGINAL transaction balance.

    Call get_balance() for today's balance. This receipt is not an offline access grant.
    """
    transaction_id: str
    consumed: int
    balance: int
    replayed: bool


def consumption(payload: dict[str, Any], body: dict[str, Any], amount: int, key: str | None) -> CreditConsumption:
    receipt = payload.get("credit_transaction")
    expected = hashlib.sha256(key.encode()).hexdigest() if key is not None else None
    if (not isinstance(receipt, dict) or receipt.get("type") != "consume"
            or not isinstance(receipt.get("id"), str) or not re.fullmatch(r"ctx_[A-Za-z0-9_-]{1,36}", receipt["id"])
            or not isinstance(receipt.get("amount"), int) or isinstance(receipt["amount"], bool) or receipt["amount"] != -amount
            or not credit_integer(receipt.get("balance_after")) or not credit_integer(receipt.get("total_allocated_after"))
            or receipt.get("idempotency_hash") != expected or not isinstance(receipt.get("replayed"), bool)
            or body.get("transaction_id") != receipt["id"] or body.get("consumed") != amount
            or body.get("balance") != receipt["balance_after"] or body.get("replayed") is not receipt["replayed"]):
        raise ValueError("The credit receipt could not be authenticated.")
    return CreditConsumption(receipt["id"], amount, receipt["balance_after"], receipt["replayed"])
