from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator
from uuid import UUID


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                event_name TEXT NOT NULL,
                completion_date TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recipients (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS recipients_job_id_idx
                ON recipients(job_id);
            """
        )


def create_job(
    database_path: Path,
    job_id: UUID,
    event_name: str,
    completion_date: str,
    recipients: list[tuple[UUID, str, str]],
) -> None:
    created_at = datetime.now(UTC).isoformat()
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (id, event_name, completion_date, status, created_at)
            VALUES (?, ?, ?, 'queued', ?)
            """,
            (str(job_id), event_name, completion_date, created_at),
        )
        connection.executemany(
            """
            INSERT INTO recipients
                (id, job_id, name, email, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            [
                (str(recipient_id), str(job_id), name, email, created_at)
                for recipient_id, name, email in recipients
            ],
        )


def get_job(database_path: Path, job_id: UUID) -> sqlite3.Row | None:
    with connect(database_path) as connection:
        return connection.execute(
            "SELECT * FROM jobs WHERE id = ?", (str(job_id),)
        ).fetchone()


def get_recipients(database_path: Path, job_id: UUID) -> list[sqlite3.Row]:
    with connect(database_path) as connection:
        return connection.execute(
            "SELECT * FROM recipients WHERE job_id = ? ORDER BY rowid",
            (str(job_id),),
        ).fetchall()


def get_recipient(
    database_path: Path, job_id: UUID, recipient_id: UUID
) -> sqlite3.Row | None:
    with connect(database_path) as connection:
        return connection.execute(
            "SELECT * FROM recipients WHERE job_id = ? AND id = ?",
            (str(job_id), str(recipient_id)),
        ).fetchone()


def update_job_status(database_path: Path, job_id: UUID, status: str) -> None:
    with connect(database_path) as connection:
        connection.execute(
            "UPDATE jobs SET status = ? WHERE id = ?", (status, str(job_id))
        )


def update_recipient_status(
    database_path: Path,
    recipient_id: str,
    status: str,
    error: str | None = None,
) -> None:
    with connect(database_path) as connection:
        connection.execute(
            "UPDATE recipients SET status = ?, error = ? WHERE id = ?",
            (status, error, recipient_id),
        )
