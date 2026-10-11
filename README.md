# Bulk Certificate Generator

A FastAPI service that accepts a batch of recipients, creates one PDF certificate
per recipient from a single predefined design, persists job progress in SQLite,
and provides individual certificate downloads.

## Requirements and setup

- Python 3.10 or newer
- Windows, macOS, or Linux

Create and activate a virtual environment, then install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS/Linux, activate with `source .venv/bin/activate` instead.

## Run the application

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive API documentation
is at `http://127.0.0.1:8000/docs`.

By default, SQLite data is stored in `data/certificates.sqlite3` and PDFs in
`generated_certificates/`. Set `CERTIFICATE_DATABASE_PATH` and
`CERTIFICATE_OUTPUT_DIR` to override these locations.

## Submit a bulk request

```http
POST /api/v1/jobs
Content-Type: application/json
```

```json
{
  "event_name": "Python Fundamentals",
  "completion_date": "2026-10-11",
  "recipients": [
    { "name": "Ada Lovelace", "email": "ada@example.com" },
    { "name": "Grace Hopper", "email": "grace@example.com" }
  ]
}
```

The API validates the full request (including a non-empty list of at most 1,000
recipients) and responds with HTTP `202 Accepted`, a job ID, and the initial
status. Invalid input receives HTTP `422` with field-level validation details.
Each recipient must have a non-blank name of at most 120 characters and a
well-formed email address.

## Track progress and retrieve certificates

- `GET /api/v1/jobs/{job_id}` returns the job status, counts, percentage, and
  per-recipient status. A recipient's `download_url` is populated when its
  certificate is ready.
- `GET /api/v1/jobs/{job_id}/certificates` lists recipient outcomes and
  download links.
- `GET /api/v1/jobs/{job_id}/certificates/{recipient_id}` downloads that
  recipient's PDF certificate.

Job states are `queued`, `running`, `completed`, `partial`, and `failed`.
Recipient states are `pending`, `generated`, and `failed`. The job is `partial`
when some certificates succeed and others fail; a failed recipient includes a
safe error summary, and does not prevent processing the rest of the batch.
Requests for an unknown job/recipient return `404`; a certificate that is not
ready returns `409`.

## Design decisions

- **Bulk, asynchronous API:** The request persists a job and all recipients and
  returns `202`; FastAPI's in-process background-task mechanism renders the
  batch after the response. This avoids holding the client's request open for
  PDF generation and needs no broker/worker service for this small application.
  The job and recipient records are stored before processing, so their status
  and outcomes can be queried from SQLite. For multi-process deployment or
  stronger crash recovery, move task execution to a durable external queue.
- **Per-recipient isolation:** Each renderer call is isolated; failures are
  logged and recorded while later recipients continue. The job status is
  calculated from the completed recipient outcomes.
- **Storage:** SQLite provides durable relational job/status data. Certificates
  are stored as files named using server-generated UUIDs; paths are never
  accepted from the request.
- **One fixed design:** ReportLab renders an A4 landscape completion certificate
  using its bundled Vera font. The participant and event names and completion
  date are included on each certificate.
- **Input bounds:** Each job is limited to 1,000 recipients to keep request
  validation, database writes, and background work bounded.

## Run tests

```powershell
python -m pytest
```

The test suite covers job creation and progress, invalid input, recipient limits,
partial failures, certificate listing, downloads, and missing resources.
