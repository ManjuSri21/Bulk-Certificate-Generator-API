import logging
import sqlite3
from pathlib import Path
from typing import Callable
from uuid import UUID

from app.database import (
    get_recipients,
    update_job_status,
    update_recipient_status,
)
from app.generator import generate_certificate

logger = logging.getLogger(__name__)
CertificateGenerator = Callable[[Path, UUID, UUID, str, str, str], Path]


def process_job(
    database_path: Path,
    output_dir: Path,
    job_id: UUID,
    event_name: str,
    completion_date: str,
    generator: CertificateGenerator = generate_certificate,
) -> None:
    update_job_status(database_path, job_id, "running")
    for recipient in get_recipients(database_path, job_id):
        try:
            certificate_path = generator(
                output_dir,
                job_id,
                UUID(recipient["id"]),
                recipient["name"],
                event_name,
                completion_date,
            )
            expected_path = output_dir / f"{job_id}_{recipient['id']}.pdf"
            if certificate_path != expected_path or not certificate_path.is_file():
                raise RuntimeError("Certificate renderer did not create the expected file")
        except Exception as error:
            logger.exception(
                "Certificate generation failed for recipient %s in job %s",
                recipient["id"],
                job_id,
            )
            partial_certificate = output_dir / f"{job_id}_{recipient['id']}.pdf"
            try:
                partial_certificate.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Could not remove partial certificate for recipient %s in job %s",
                    recipient["id"],
                    job_id,
                )
            update_recipient_status(
                database_path,
                recipient["id"],
                "failed",
                f"Certificate generation failed ({type(error).__name__})",
            )
        else:
            update_recipient_status(database_path, recipient["id"], "generated")

    recipients = get_recipients(database_path, job_id)
    generated = sum(recipient["status"] == "generated" for recipient in recipients)
    failed = sum(recipient["status"] == "failed" for recipient in recipients)
    if failed == 0:
        status = "completed"
    elif generated == 0:
        status = "failed"
    else:
        status = "partial"
    update_job_status(database_path, job_id, status)
