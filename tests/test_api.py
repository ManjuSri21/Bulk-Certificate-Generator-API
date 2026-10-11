from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    application = create_app(
        database_path=tmp_path / "test.sqlite3",
        output_dir=tmp_path / "certificates",
    )
    return TestClient(application)


def payload(names: list[str] | None = None) -> dict[str, object]:
    return {
        "event_name": "Python Fundamentals",
        "completion_date": date(2026, 10, 11).isoformat(),
        "recipients": [
            {"name": name, "email": f"person{index}@example.com"}
            for index, name in enumerate(names or ["Ada Lovelace", "Grace Hopper"])
        ],
    }


def test_creates_bulk_job_and_tracks_completed_progress(client: TestClient) -> None:
    response = client.post("/api/v1/jobs", json=payload())

    assert response.status_code == 202
    created = response.json()
    assert created["total"] == 2
    assert created["status"] == "queued"
    job = client.get(f"/api/v1/jobs/{created['id']}").json()
    assert job["status"] == "completed"
    assert job["processed"] == 2
    assert job["generated"] == 2
    assert job["failed"] == 0
    assert job["progress_percent"] == 100
    assert all(recipient["status"] == "generated" for recipient in job["recipients"])


@pytest.mark.parametrize(
    ("recipient", "field"),
    [
        ({"name": "Ada", "email": "not-an-email"}, "email"),
        ({"name": "   ", "email": "ada@example.com"}, "name"),
    ],
)
def test_rejects_invalid_recipient_data(
    client: TestClient, recipient: dict[str, str], field: str
) -> None:
    response = client.post(
        "/api/v1/jobs",
        json={
            "event_name": "Python Fundamentals",
            "completion_date": "2026-10-11",
            "recipients": [recipient],
        },
    )
    assert response.status_code == 422
    assert any(error["loc"][-1] == field for error in response.json()["detail"])


def test_rejects_empty_and_over_limit_recipient_lists(client: TestClient) -> None:
    empty = payload()
    empty["recipients"] = []
    too_many = payload(["Ada"] * 1001)

    assert client.post("/api/v1/jobs", json=empty).status_code == 422
    assert client.post("/api/v1/jobs", json=too_many).status_code == 422


def test_individual_generation_failure_does_not_stop_other_recipients(
    tmp_path: Path,
) -> None:
    def fail_for_grace(
        output_dir: Path,
        job_id: UUID,
        recipient_id: UUID,
        recipient_name: str,
        event_name: str,
        completion_date: str,
    ) -> Path:
        if recipient_name == "Grace Hopper":
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"{job_id}_{recipient_id}.pdf").write_bytes(b"partial")
            raise RuntimeError("simulated renderer failure")
        output_dir.mkdir(parents=True, exist_ok=True)
        certificate = output_dir / f"{job_id}_{recipient_id}.pdf"
        certificate.write_bytes(b"%PDF-test")
        return certificate

    client = TestClient(
        create_app(
            database_path=tmp_path / "failure.sqlite3",
            output_dir=tmp_path / "certificates",
            certificate_generator=fail_for_grace,
        )
    )
    created = client.post("/api/v1/jobs", json=payload()).json()
    job = client.get(f"/api/v1/jobs/{created['id']}").json()

    assert job["status"] == "partial"
    assert job["generated"] == 1
    assert job["failed"] == 1
    assert {recipient["status"] for recipient in job["recipients"]} == {
        "generated",
        "failed",
    }
    failed = next(r for r in job["recipients"] if r["status"] == "failed")
    assert "RuntimeError" in failed["error"]
    assert failed["download_url"] is None
    assert len(list((tmp_path / "certificates").glob("*.pdf"))) == 1


def test_lists_and_downloads_generated_certificates(client: TestClient) -> None:
    created = client.post("/api/v1/jobs", json=payload(["Ada Lovelace"])).json()
    recipient_id = created["recipients"][0]["id"]
    listing = client.get(f"/api/v1/jobs/{created['id']}/certificates").json()

    assert listing["certificates"][0]["recipient_id"] == recipient_id
    response = client.get(
        f"/api/v1/jobs/{created['id']}/certificates/{recipient_id}"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_missing_job_or_certificate_returns_not_found(client: TestClient) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/v1/jobs/{missing_id}").status_code == 404
    assert client.get(f"/api/v1/jobs/{missing_id}/certificates").status_code == 404
