"""KDPika Licensing's deliberately small public Python API."""

from ._version import __version__
from ._credits import CreditConsumption
from .async_client import AsyncLicenseClient
from .client import LicenseClient
from .errors import (
    AllSeatsInUseError,
    CreditOperationError,
    InsufficientCreditsError,
    ConfigurationError,
    LicenseSdkError,
    NetworkError,
    SignatureVerificationError,
    StorageError,
)
from .models import LicenseResult

__all__ = [
    "CreditConsumption",
    "CreditOperationError",
    "InsufficientCreditsError",
    "AllSeatsInUseError",
    "AsyncLicenseClient",
    "LicenseClient",
    "LicenseResult",
    "LicenseSdkError",
    "ConfigurationError",
    "NetworkError",
    "SignatureVerificationError",
    "StorageError",
    "__version__",
]
