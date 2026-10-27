"""Shared application code. Real licensing calls; never a developer management key."""
import csv
import os
from pathlib import Path

from kdpika_licensing import LicenseClient


class AccessDenied(Exception):
    pass


def application_folder(product=None, environment=None) -> Path:
    # Use one private, persistent folder for each app + machine + environment.
    product = (product if product is not None else os.environ.get("KDP_APP_ID", "")).strip()
    if not product.startswith("app_") or not product.replace("_", "").isalnum():
        raise ValueError("Copy the App ID from Products and paste it into the App ID field.")
    environment = (environment if environment is not None else os.environ.get("KDP_ENVIRONMENT", "SANDBOX")).strip().upper()
    if environment not in {"SANDBOX", "LIVE"}:
        raise ValueError("KDP_ENVIRONMENT must be SANDBOX or LIVE.")
    folder = Path.home() / ".kdpika-python-tutorial" / product / environment.lower()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return folder


def make_client(product=None, environment=None) -> LicenseClient:
    product = product if product is not None else os.environ.get("KDP_APP_ID", "")
    environment = environment if environment is not None else os.environ.get("KDP_ENVIRONMENT", "SANDBOX")
    folder = application_folder(product, environment)
    return LicenseClient(
        product=product.strip(),
        environment=environment.strip().upper(),
        base_url="https://licensing.kdpika.com",
        application_name="Python Licensing Tutorial",
        application_version="1.1.0",
        storage_dir=folder / "license-state",
    )


def require_csv_access(client: LicenseClient):
    result = client.check()
    if not result.valid or not result.signature_valid:
        raise AccessDenied("Check your license or reconnect, then try again.")
    if result.payload.get("metered"):
        # A normal feature check does NOT charge a credit. Never offer free work by mistake.
        raise AccessDenied("This license uses credits. Run credit_export.py for paid exports.")
    if not result.feature("csv_export"):
        raise AccessDenied("CSV export is not included in this license.")
    return result


def export_csv(client: LicenseClient, text: str, folder=None) -> Path:
    require_csv_access(client)  # Check again at the protected action, not only at startup.
    path = (Path(folder) if folder is not None else application_folder()) / "export.csv"
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["Message"])
        # Keep spreadsheet applications from interpreting user text as a formula.
        writer.writerow(["'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text])
    return path
