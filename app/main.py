import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.database import (
    create_job,
    get_job,
    get_recipient,
    get_recipients,
    initialize_database,
)
from app.generator import generate_certificate
from app.schemas import CreateJobRequest, JobResult
from app.service import CertificateGenerator, process_job

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(
    database_path: Path | None = None,
    output_dir: Path | None = None,
    certificate_generator: CertificateGenerator = generate_certificate,
) -> FastAPI:
    db_path = database_path or Path(
        os.getenv("CERTIFICATE_DATABASE_PATH", PROJECT_ROOT / "data" / "certificates.sqlite3")
    )
    certificates_dir = output_dir or Path(
        os.getenv("CERTIFICATE_OUTPUT_DIR", PROJECT_ROOT / "generated_certificates")
    )
    initialize_database(db_path)
    app = FastAPI(
        title="Bulk Certificate Generator",
        description="Submit bulk certificate jobs, track their progress, and download generated PDFs.",
        version="1.0.0",
    )

    @app.post("/api/v1/jobs", response_model=JobResult, status_code=202)
    def create_generation_job(
        request: CreateJobRequest, background_tasks: BackgroundTasks
    ) -> JobResult:
        job_id = uuid4()
        recipient_rows = [
            (uuid4(), recipient.name, recipient.email)
            for recipient in request.recipients
        ]
        create_job(
            db_path,
            job_id,
            request.event_name,
            request.completion_date.isoformat(),
            recipient_rows,
        )
        background_tasks.add_task(
            process_job,
            db_path,
            certificates_dir,
            job_id,
            request.event_name,
            request.completion_date.isoformat(),
            certificate_generator,
        )
        return build_job_result(db_path, job_id)

    @app.get("/api/v1/jobs/{job_id}", response_model=JobResult)
    def read_generation_job(job_id: UUID) -> JobResult:
        return build_job_result(db_path, job_id)

    @app.get("/api/v1/jobs/{job_id}/certificates")
    def list_job_certificates(job_id: UUID) -> dict[str, object]:
        if get_job(db_path, job_id) is None:
            raise HTTPException(status_code=404, detail="Generation job not found")
        recipients = get_recipients(db_path, job_id)
        return {
            "job_id": str(job_id),
            "certificates": [
                {
                    "recipient_id": recipient["id"],
                    "name": recipient["name"],
                    "status": recipient["status"],
                    "download_url": (
                        f"/api/v1/jobs/{job_id}/certificates/{recipient['id']}"
                        if recipient["status"] == "generated"
                        else None
                    ),
                    "error": recipient["error"],
                }
                for recipient in recipients
            ],
        }

    @app.get("/api/v1/jobs/{job_id}/certificates/{recipient_id}")
    def download_certificate(job_id: UUID, recipient_id: UUID) -> FileResponse:
        if get_job(db_path, job_id) is None:
            raise HTTPException(status_code=404, detail="Generation job not found")
        recipient = get_recipient(db_path, job_id, recipient_id)
        if recipient is None:
            raise HTTPException(status_code=404, detail="Recipient not found in this job")
        if recipient["status"] != "generated":
            raise HTTPException(status_code=409, detail="Certificate is not available")
        certificate_path = certificates_dir / f"{job_id}_{recipient_id}.pdf"
        if not certificate_path.is_file():
            raise HTTPException(status_code=404, detail="Generated certificate file not found")
        return FileResponse(
            certificate_path,
            media_type="application/pdf",
            filename=f"certificate-{recipient_id}.pdf",
        )

    return app


def build_job_result(database_path: Path, job_id: UUID) -> JobResult:
    job = get_job(database_path, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    recipients = get_recipients(database_path, job_id)
    generated = sum(recipient["status"] == "generated" for recipient in recipients)
    failed = sum(recipient["status"] == "failed" for recipient in recipients)
    total = len(recipients)
    processed = generated + failed
    return JobResult(
        id=job["id"],
        event_name=job["event_name"],
        completion_date=job["completion_date"],
        status=job["status"],
        total=total,
        processed=processed,
        generated=generated,
        failed=failed,
        progress_percent=round(processed / total * 100, 2) if total else 0,
        created_at=job["created_at"],
        recipients=[
            {
                "id": recipient["id"],
                "name": recipient["name"],
                "email": recipient["email"],
                "status": recipient["status"],
                "error": recipient["error"],
                "download_url": (
                    f"/api/v1/jobs/{job_id}/certificates/{recipient['id']}"
                    if recipient["status"] == "generated"
                    else None
                ),
            }
            for recipient in recipients
        ],
    )


app = create_app()
