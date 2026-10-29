"""Immutable result snapshots with fail-closed feature access."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ._json import loads
from ._floating import lease_valid
from ._credits import credit_policy
from ._verification import times
from .errors import safe_request_id


@dataclass(frozen=True)
class LicenseResult:
    """One verified decision, not a permanent grant or proof of payment.

    Helpers re-evaluate time at use and deny on every invalid/unsigned result.
    payload remains readable for diagnostics, but is excluded from repr.

    Attributes:
        valid: Decision at check time; not a permanent capability.
        source: online, cache, offline or local decision origin.
        payload: Detached signed payload for private diagnostics, never logs.
        error_code: Stable safe refusal code, or None.
        message: SDK-owned display message; arbitrary constructed messages are not sanitized.
        request_id: Bounded safe support identifier, or None.
        signature_valid: Whether the SDK authenticated the payload signature.
        storage_security: os-keyring, permission-protected-file or unknown.

    Examples:
        >>> result = LicenseResult(False, "local", error_code="NOT_ACTIVATED")
        >>> result.feature("pdf_export", True)
        False
        >>> result.feature_value("seat_count", 100) is None
        True

    Constructing this dataclass is not signature verification. Obtain access
    decisions from LicenseClient, not user-provided dictionaries/booleans.
    """

    valid: bool
    source: str
    payload: dict[str, Any] = field(default_factory=dict, repr=False)
    error_code: str | None = None
    message: str = field(default="", repr=False)
    request_id: str | None = None
    signature_valid: bool = False
    storage_security: str = "unknown"
    _clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC), repr=False, compare=False)
    _snapshot: dict[str, Any] = field(default_factory=dict, init=False, repr=False, compare=False)
    _seat_guard: Callable[[dict[str, Any]], bool] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", deepcopy(self.payload))
        object.__setattr__(self, "_snapshot", deepcopy(self.payload))
        object.__setattr__(self, "request_id", safe_request_id(self.request_id))

    @property
    def status(self) -> str:
        """Return the signed status, or unknown when absent."""
        return str(self._snapshot.get("status", "unknown"))

    @property
    def license_id(self) -> str | None:
        """Return the license identifier, not a customer secret."""
        value = self._snapshot.get("license_id")
        return value if isinstance(value, str) else None

    @property
    def expires_at(self) -> str | None:
        """Return the original signed expiry string, or None for lifetime."""
        value = self._snapshot.get("expires_at")
        return value if isinstance(value, str) else None

    @property
    def offline_grace_until(self) -> str | None:
        """Return the original signed absolute grace deadline."""
        value = self._snapshot.get("offline_grace_until")
        return value if isinstance(value, str) else None

    def _allowed(self) -> bool:
        if not self.valid or not self.signature_valid or self.status != "active":
            return False
        if not credit_policy(self._snapshot) or (self._snapshot["metered"] and self.source != "online"):
            return False
        try:
            server, next_check, grace, expiry = times(self._snapshot)
            now = self._clock()
            if now.tzinfo is None:
                return False
            if self._snapshot.get("floating") is not None:
                if self._seat_guard is None or not self._seat_guard(self._snapshot):
                    return False
            elif not lease_valid(self._snapshot, None, now):
                return False
            return not (
                now.timestamp() + 300 < server.timestamp()
                or (expiry and now >= expiry)
                or (now > grace if self.source in {"cache", "offline"} else now >= next_check)
            )
        except (ValueError, TypeError, OverflowError):
            return False

    @property
    def features(self) -> dict[str, Any]:
        """Return a detached feature map only while the decision authorizes access."""
        features = self._snapshot.get("features")
        return deepcopy(features) if self._allowed() and isinstance(features, dict) else {}

    def feature(self, name: str, default: bool = False) -> bool:
        """Check a boolean/numeric flag on a currently authorized decision.

        Args:
            name: Configured feature key.
            default: Missing-key fallback for an authorized decision only.

        Returns:
            True for boolean True or a positive number. String values do not
            enable a flag. Invalid decisions ignore enabling defaults.
        """
        if not self._allowed():
            return False
        features = self._snapshot.get("features")
        value = features.get(name, default) if isinstance(features, dict) else False
        return value is True or (isinstance(value, (int, float)) and value > 0)

    def feature_value(self, name: str, default: Any = None) -> Any:
        """Read a detached value only while the decision authorizes access.

        Args:
            name: Configured feature/limit key.
            default: Missing-key fallback for an authorized decision only.

        Returns:
            A copied entitlement, or None on failure regardless of default.
            This does not validate whether a value is a usable numeric limit.
        """
        if not self._allowed():
            return None
        features = self._snapshot.get("features")
        return deepcopy(features.get(name, default)) if isinstance(features, dict) else None


@dataclass(frozen=True)
class HttpResponse:
    """Internal transport response. Custom transports should use from_bytes()."""

    status: int
    headers: dict[str, str] = field(repr=False)
    body: dict[str, Any] = field(repr=False)

    @classmethod
    def from_bytes(cls, status: int, headers: dict[str, str], raw: bytes) -> HttpResponse:
        """Decode without losing signed server number spellings."""
        try:
            value = loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
        except (ValueError, UnicodeError, RecursionError):
            value = {"success": False, "error": {"code": "INVALID_RESPONSE"}}
        return cls(status, headers, value)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and self.body.get("success") is True
