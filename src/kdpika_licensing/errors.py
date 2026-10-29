"""Stable exceptions whose string representations never include caller secrets."""

from __future__ import annotations

import re


def safe_request_id(value: object) -> str | None:
    """Accept only the server's bounded, non-credential request identifier."""
    return value if isinstance(value, str) and re.fullmatch(r"req_[A-Za-z0-9_-]{1,100}", value) else None


class LicenseSdkError(Exception):
    """Base safe SDK exception; most operational failures use LicenseResult.

    Args:
        message: Accepted for compatibility but deliberately not retained.
        request_id: Optional bounded support identifier, never a credential.

    Attributes:
        code: Stable SDK exception code.
        request_id: Sanitized support identifier or None.
        safe_message: SDK-owned static human-readable message.

    Examples:
        >>> error = StorageError(request_id="req_example")
        >>> error.code
        'STORAGE_ERROR'
        >>> error.request_id
        'req_example'
    """

    code = "SDK_ERROR"
    safe_message = "The license operation could not be completed."

    def __init__(self, message: str = "", *, request_id: str | None = None) -> None:
        # Compatibility accepts a message, but deliberately does not retain it.
        super().__init__(self.safe_message)
        self.request_id = safe_request_id(request_id)


class ConfigurationError(LicenseSdkError):
    """The application configuration is invalid or unsafe."""

    code = "CONFIGURATION_ERROR"
    safe_message = "Check the application ID, environment, HTTPS URL and SDK configuration."


class AllSeatsInUseError(LicenseSdkError):
    """An explicit checkout could not reserve a shared seat."""

    code = "ALL_SEATS_IN_USE"
    safe_message = "All shared seats are in use. Try again when someone closes the app."


class SignatureVerificationError(LicenseSdkError):
    """The response could not be authenticated with the trusted key."""

    code = "SIGNATURE_INVALID"
    safe_message = "The license response could not be authenticated. Reconnect or contact support."


class CreditOperationError(LicenseSdkError):
    """Safe credit refusal; no untrusted server message or request body is retained."""
    code = "CREDIT_OPERATION_FAILED"
    safe_message = "The credit operation could not be completed. Check the license or contact its publisher."

    def __init__(self, code: str = "CREDIT_OPERATION_FAILED", *, request_id: str | None = None) -> None:
        super().__init__(request_id=request_id)
        if code in {"CREDIT_PRICE_CHANGED", "CREDIT_CODE_UNAVAILABLE", "CREDIT_ACTION_UNAVAILABLE", "CREDIT_REVIEW_REQUIRED", "CREDIT_ACCESS_DENIED", "CREDIT_LIMIT_EXCEEDED", "INVALID_REQUEST", "NOT_ACTIVATED", "NOT_METERED_LICENSE", "IDEMPOTENCY_CONFLICT", "INVALID_CREDIT_AMOUNT", "RATE_LIMITED", "LICENSE_EXPIRED", "LICENSE_REVOKED", "LICENSE_SUSPENDED", "SESSION_NOT_FOUND", "SESSION_EXPIRED", "FINGERPRINT_MISMATCH", "HARDWARE_UNAVAILABLE"}:
            self.code = code


class InsufficientCreditsError(CreditOperationError):
    """Verified refusal. balance is the signed current balance, not a payment amount."""
    code = "INSUFFICIENT_CREDITS"
    safe_message = "There are not enough credits. Ask the software publisher to add more."

    def __init__(self, balance: int, *, request_id: str | None = None) -> None:
        super().__init__(request_id=request_id)
        self.balance = balance


class StorageError(LicenseSdkError):
    """Private installation state cannot be used safely."""

    code = "STORAGE_ERROR"
    safe_message = "Private license storage is unavailable. Check permissions or contact support."


class NetworkError(LicenseSdkError):
    """No authoritative HTTP response was received."""

    code = "NETWORK_ERROR"
    safe_message = "The licensing service could not be reached. Check your connection."


__all__ = [
    "LicenseSdkError",
    "ConfigurationError",
    "SignatureVerificationError",
    "StorageError",
    "NetworkError",
    "CreditOperationError",
    "InsufficientCreditsError",
]
