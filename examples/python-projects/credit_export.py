"""One credit per CSV job. SQLite retains each request key across retries/restarts."""
import argparse
import csv
import getpass
import hashlib
import os
import re
import sqlite3
import tempfile
from pathlib import Path

from common import AccessDenied, application_folder, make_client
from kdpika_licensing import CreditOperationError, InsufficientCreditsError


def run_job(client, job_id: str, text: str, folder: Path) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", job_id) or not text or len(text) > 1000:
        raise ValueError("Use an 8–80 character job name and a message of 1–1000 characters.")
    # A zero balance may be the result of an already-charged pending job. It must
    # still be recoverable with that job's original key, never a new charge key.
    result = client.check(force_online=True)
    if not result.signature_valid or (not result.valid and result.error_code != "INSUFFICIENT_CREDITS"):
        raise AccessDenied("Reconnect and check this license before exporting.")
    if not result.payload.get("metered"):
        raise AccessDenied("Choose a usage-credit license for this example.")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = hashlib.sha256(job_id.encode()).hexdigest()
    target = folder / (name + ".csv")
    db = sqlite3.connect(folder / "jobs.sqlite3", timeout=30)
    db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, license_id TEXT NOT NULL, text TEXT NOT NULL, state TEXT NOT NULL)")
    temporary = None
    try:
        db.execute("BEGIN IMMEDIATE")  # One local worker owns this job until its result is saved.
        row = db.execute("SELECT license_id, text, state FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row and (row[0] != result.license_id or row[1] != text):
            raise AccessDenied("Keep this job's original license and message when retrying.")
        if row and row[2] == "DONE" and target.is_file():
            db.commit()
            return target  # Reopening a completed output does not charge or execute a new job.
        if row is None:
            db.execute("INSERT INTO jobs VALUES (?, ?, ?, 'PENDING')", (job_id, result.license_id, text))
            db.commit()  # The key must exist durably BEFORE the first network request.
            db.execute("BEGIN IMMEDIATE")
            # Another process may have finished after the durable insert.
            row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row and row[0] == "DONE" and target.is_file():
                db.commit()
                return target
        client.consume(1, idempotency_key="python_export:" + job_id, reason="One CSV export")
        # Reaching here means a signed receipt authorized THIS job, even if it left zero credits.
        # Do not ask result.feature() again after the final paid credit was consumed.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=folder,
                                         prefix="export-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            writer = csv.writer(output)
            writer.writerow(["Message"])
            writer.writerow(["'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text])
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)  # Deterministic output; retry cannot create a second CSV job.
        db.execute("UPDATE jobs SET state='DONE' WHERE id=?", (job_id,))
        db.commit()
        return target
    except Exception:
        db.rollback()  # The earlier committed PENDING row survives an uncertain charge reply.
        raise
    finally:
        db.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Export one CSV for one usage credit.")
    parser.add_argument("--job", required=True, help="Persist and reuse this logical job name on retry.")
    parser.add_argument("--text", required=True)
    args = parser.parse_args()
    client = make_client()
    try:
        if not client.activated:
            result = client.activate(getpass.getpass("License key: "),
                                     input("Matching customer email: ").strip() or None)
            if not result.valid or not result.signature_valid:
                raise AccessDenied("This license could not be activated. Check it in KDPika.")
        print("Saved:", run_job(client, args.job, args.text, application_folder() / "credit-jobs"))
        print("Run the identical job and message again to reuse its output without another charge.")
    except InsufficientCreditsError:
        raise SystemExit("Not enough credits. Ask the publisher to add credits, then retry this same job.")
    except (CreditOperationError, AccessDenied, ValueError):
        raise SystemExit("The job was not completed. Check access or reconnect; retry the same job and message.")
    except Exception:
        raise SystemExit("The result is uncertain. Do not choose a new job name; retry the same job and message.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
