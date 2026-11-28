from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from resume_agent.models.application import Application, ApplicationStatus
from resume_agent.models.job import Job


class ApplicationTracker:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    job_id TEXT PRIMARY KEY,
                    job_title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    job_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    applied_at TEXT,
                    notes TEXT,
                    cover_letter TEXT,
                    error TEXT,
                    agent TEXT,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_jobs (
                    job_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                )
                """
            )

    def has_applied(self, job_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM applications WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            return row is not None and row["status"] in {
                ApplicationStatus.APPLIED.value,
                ApplicationStatus.INTERVIEW.value,
                ApplicationStatus.OFFER.value,
            }

    def save_application(self, application: Application) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO applications (
                    job_id, job_title, company, job_url, status,
                    applied_at, notes, cover_letter, error, agent, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    applied_at=excluded.applied_at,
                    notes=excluded.notes,
                    cover_letter=excluded.cover_letter,
                    error=excluded.error,
                    agent=excluded.agent,
                    metadata=excluded.metadata
                """,
                (
                    application.job_id,
                    application.job_title,
                    application.company,
                    application.job_url,
                    application.status.value,
                    application.applied_at.isoformat() if application.applied_at else None,
                    application.notes,
                    application.cover_letter,
                    application.error,
                    application.agent,
                    json.dumps(application.metadata),
                ),
            )

    def list_applications(self, status: ApplicationStatus | None = None) -> list[Application]:
        query = "SELECT * FROM applications"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY applied_at DESC NULLS LAST"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        results: list[Application] = []
        for row in rows:
            applied_at = None
            if row["applied_at"]:
                applied_at = datetime.fromisoformat(row["applied_at"])
            results.append(
                Application(
                    job_id=row["job_id"],
                    job_title=row["job_title"],
                    company=row["company"],
                    job_url=row["job_url"],
                    status=ApplicationStatus(row["status"]),
                    applied_at=applied_at,
                    notes=row["notes"],
                    cover_letter=row["cover_letter"],
                    error=row["error"],
                    agent=row["agent"],
                    metadata=json.loads(row["metadata"] or "{}"),
                )
            )
        return results

    def save_jobs(self, jobs: list[Job]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for job in jobs:
                conn.execute(
                    """
                    INSERT INTO saved_jobs (job_id, payload, saved_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET payload=excluded.payload
                    """,
                    (job.id, job.model_dump_json(), now),
                )

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM applications GROUP BY status"
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}
