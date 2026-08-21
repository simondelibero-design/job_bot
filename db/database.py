import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        _migrate(conn)


def _migrate(conn):
    """Adds columns introduced after the original schema, for DBs created
    before them. CREATE TABLE IF NOT EXISTS doesn't alter existing tables."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    new_columns = [
        ("phd_flag", "TEXT"), ("distance_miles", "REAL"), ("tier", "TEXT"),
        ("search_mode", "TEXT DEFAULT 'local'"), ("salary_annual_est", "REAL"),
    ]
    for column, ddl_type in new_columns:
        if column not in existing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {ddl_type}")


def upsert_job(job: dict) -> int:
    """Insert a discovered job, or ignore if (source, source_job_id) already logged.
    Returns the job's row id."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (source, source_job_id, title, company, location, salary,
                               job_type, url, snippet, search_keyword, score,
                               matched_keywords, excluded, phd_flag, distance_miles,
                               tier, search_mode, salary_annual_est, discovered_at)
            VALUES (:source, :source_job_id, :title, :company, :location, :salary,
                    :job_type, :url, :snippet, :search_keyword, :score,
                    :matched_keywords, :excluded, :phd_flag, :distance_miles,
                    :tier, :search_mode, :salary_annual_est, :discovered_at)
            ON CONFLICT(source, source_job_id) DO NOTHING
            """,
            {
                "source": job["source"],
                "source_job_id": job["source_job_id"],
                "title": job["title"],
                "company": job.get("company"),
                "location": job.get("location"),
                "salary": job.get("salary"),
                "job_type": job.get("job_type"),
                "url": job.get("url"),
                "snippet": job.get("snippet"),
                "search_keyword": job.get("search_keyword"),
                "score": job.get("score", 0),
                "matched_keywords": json.dumps(job.get("matched_keywords", [])),
                "excluded": int(job.get("excluded", False)),
                "phd_flag": job.get("phd_flag"),
                "distance_miles": job.get("distance_miles"),
                "tier": job.get("tier"),
                "search_mode": job.get("search_mode", "local"),
                "salary_annual_est": job.get("salary_annual_est"),
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        row = conn.execute(
            "SELECT id FROM jobs WHERE source = ? AND source_job_id = ?",
            (job["source"], job["source_job_id"]),
        ).fetchone()
        job_id = row["id"]
        conn.execute(
            """
            INSERT INTO applications (job_id, status)
            VALUES (?, 'discovered')
            ON CONFLICT(job_id) DO NOTHING
            """,
            (job_id,),
        )
        return job_id


def top_jobs(limit: int = 50, min_score: float = 0):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT jobs.*, applications.status AS application_status
            FROM jobs
            JOIN applications ON applications.job_id = jobs.id
            WHERE jobs.excluded = 0 AND jobs.score >= ?
            ORDER BY jobs.score DESC, jobs.discovered_at DESC
            LIMIT ?
            """,
            (min_score, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def set_application_status(job_id: int, status: str, notes: str | None = None,
                            ats_platform: str | None = None):
    with get_conn() as conn:
        fields = ["status = :status"]
        params = {"status": status, "job_id": job_id}
        if notes is not None:
            fields.append("notes = :notes")
            params["notes"] = notes
        if ats_platform is not None:
            fields.append("ats_platform = :ats_platform")
            params["ats_platform"] = ats_platform
        if status == "submitted":
            fields.append("applied_at = :applied_at")
            params["applied_at"] = datetime.now(timezone.utc).isoformat()
        conn.execute(
            f"UPDATE applications SET {', '.join(fields)} WHERE job_id = :job_id",
            params,
        )


def restore_job(job_id: int):
    """Pulls a job out of any excluded bucket (hard exclude, semi_excluded,
    or likely_excluded) and back into the normal queue."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET excluded = 0, phd_flag = NULL WHERE id = ?",
            (job_id,),
        )


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {DB_PATH}")
