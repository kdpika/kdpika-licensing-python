"""Async adapter over the same synchronized, fail-closed core."""

from __future__ import annotations

import asyncio
from typing import Any

from .client import LicenseClient
from .models import LicenseResult
from ._credits import CreditConsumption


class AsyncLicenseClient:
    """Wrap a configured LicenseClient without duplicating cryptographic policy.

    Calls use asyncio.to_thread. Cancelling the await does not cancel an in-flight
    HTTP mutation; its outcome may be uncertain. Reuse the same identity, inspect
    status, and never blindly retry activation/deactivation after cancellation.

    Args:
        client: Already-configured synchronous client; no second installation is created.

    Examples:
        See examples/async_usage.py for a runnable environment-configured lifecycle.
        Require result.valid and result.signature_valid after every awaited check.

        >>> import asyncio
        >>> from pathlib import Path
        >>> from tempfile import TemporaryDirectory
        >>> with TemporaryDirectory() as directory:
        ...     core = LicenseClient("app_synthetic", environment="SANDBOX",
        ...         storage_dir=Path(directory), prefer_keyring=False)
        ...     client = AsyncLicenseClient(core)
        ...     print(asyncio.run(client.check()).error_code)
        NOT_ACTIVATED
    """

    def __init__(self, client: LicenseClient) -> None:
        self._client = client

    @property
    def storage_security(self) -> str:
        """Report the synchronous core's selected storage backend."""
        return self._client.storage_security

    async def is_activated(self) -> bool:
        """Check token presence without blocking the event loop; not an access grant."""
        return await asyncio.to_thread(lambda: self._client.activated)

    async def activate(self, license_key: str, email: str | None = None) -> LicenseResult:
        """Activate using the synchronized core.

        Args:
            license_key: Customer key obtained privately, never logged.
            email: Optional email required by the server's product policy.

        Returns:
            The core's signed access decision or safe refusal.
        """
        return await asyncio.to_thread(self._client.activate, license_key, email)

    async def check(self, force_online: bool = False) -> LicenseResult:
        """Check current access without blocking the event loop.

        Args:
            force_online: Request validation; network failure may still use signed grace.

        Returns:
            The same fail-closed decision as LicenseClient.check.
        """
        return await asyncio.to_thread(self._client.check, force_online)

    async def validate(self) -> LicenseResult:
        """Request fresh validation with the same signed-grace rules."""
        return await asyncio.to_thread(self._client.validate)

    async def deactivate(self) -> LicenseResult:
        """Release the seat; a successful acknowledgement grants no features."""
        return await asyncio.to_thread(self._client.deactivate)

    async def credit_packs(self) -> dict:
        return await asyncio.to_thread(self._client.credit_packs)

    async def credit_history(self) -> dict:
        return await asyncio.to_thread(self._client.credit_history)

    async def create_credit_checkout(self, pack_id: str) -> dict:
        return await asyncio.to_thread(self._client.create_credit_checkout, pack_id)

    async def redeem_credits(self, code: str, idempotency_key: str) -> dict:
        return await asyncio.to_thread(self._client.redeem_credits, code, idempotency_key)

    async def consume_action(self, action: str, idempotency_key: str, expected_units: int = 1) -> CreditConsumption:
        return await asyncio.to_thread(self._client.consume_action, action, idempotency_key, expected_units)

    async def get_balance(self) -> int:
        return await asyncio.to_thread(self._client.get_balance)

    async def consume(self, amount: int, idempotency_key: str | None = None, reason: str | None = None) -> CreditConsumption:
        return await asyncio.to_thread(self._client.consume, amount, idempotency_key, reason)

    async def checkout(self) -> LicenseResult:
        return await asyncio.to_thread(self._client.checkout)

    async def heartbeat(self) -> LicenseResult:
        return await asyncio.to_thread(self._client.heartbeat)

    async def checkin(self) -> LicenseResult:
        return await asyncio.to_thread(self._client.checkin)

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)

    async def __aenter__(self) -> AsyncLicenseClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def feature(self, name: str, default: bool = False) -> bool:
        """Re-check access and safely evaluate a flag.

        Args:
            name: Configured entitlement key.
            default: Missing-key fallback only on a valid verified decision.

        Returns:
            False on failure regardless of the default.
        """
        return await asyncio.to_thread(self._client.feature, name, default)

    async def feature_value(self, name: str, default: Any = None) -> Any:
        """Re-check access and safely read an entitlement.

        Args:
            name: Configured entitlement key.
            default: Missing-key fallback only on a valid verified decision.

        Returns:
            A detached entitlement, or None on failure.
        """
        return await asyncio.to_thread(self._client.feature_value, name, default)

    async def reset_local(self) -> None:
        """Erase local token/cache, not the installation identity or server seat.

        Raises:
            StorageError: State locking or credential cleanup failed.
        """
        await asyncio.to_thread(self._client.reset_local)
