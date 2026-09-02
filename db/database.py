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
        ("priority_score", "REAL DEFAULT 0"),
    ]
    for column, ddl_type in new_columns:
        if column not in existing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {ddl_type}")
    if "priority_score" not in existing:
        # Backfill: rows from before this column existed default to 0 above,
        # which would sort last — seed with the existing relevance score
        # instead (equivalent to a 0%-weight blend) until the next rescore.
        conn.execute("UPDATE jobs SET priority_score = score")
    # Created here rather than schema.sql: on an existing (pre-priority_score)
    # database, schema.sql's executescript runs before this migration adds
    # the column, so an index on it there would fail with "no such column".
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_priority_score ON jobs(priority_score DESC)")

    existing_app_columns = {row["name"] for row in conn.execute("PRAGMA table_info(applications)")}
    if "needs_review_json" not in existing_app_columns:
        # Structured sibling to the free-text `notes` column: a JSON list of
        # the exact prompt strings an ats/*.py handler's needs_review list
        # returned, so /struggles_to_answer can parse real prompts back out
        # without splitting `notes`'s "; "-joined display string (fragile —
        # a prompt's own text can contain "; ").
        conn.execute("ALTER TABLE applications ADD COLUMN needs_review_json TEXT")


def upsert_job(job: dict) -> int:
    """Insert a discovered job, or ignore if (source, source_job_id) already logged.
    Returns the job's row id."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (source, source_job_id, title, company, location, salary,
                               job_type, url, snippet, search_keyword, score, priority_score,
                               matched_keywords, excluded, phd_flag, distance_miles,
                               tier, search_mode, salary_annual_est, discovered_at)
            VALUES (:source, :source_job_id, :title, :company, :location, :salary,
                    :job_type, :url, :snippet, :search_keyword, :score, :priority_score,
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
                "priority_score": job.get("priority_score", job.get("score", 0)),
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
            ORDER BY jobs.priority_score DESC, jobs.discovered_at DESC
            LIMIT ?
            """,
            (min_score, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def set_application_status(job_id: int, status: str, notes: str | None = None,
                            ats_platform: str | None = None,
                            needs_review: list[str] | None = None):
    with get_conn() as conn:
        fields = ["status = :status"]
        params = {"status": status, "job_id": job_id}
        if notes is not None:
            fields.append("notes = :notes")
            params["notes"] = notes
        if ats_platform is not None:
            fields.append("ats_platform = :ats_platform")
            params["ats_platform"] = ats_platform
        if needs_review is not None:
            fields.append("needs_review_json = :needs_review_json")
            params["needs_review_json"] = json.dumps(needs_review)
        if status == "submitted":
            fields.append("applied_at = :applied_at")
            params["applied_at"] = datetime.now(timezone.utc).isoformat()
        conn.execute(
            f"UPDATE applications SET {', '.join(fields)} WHERE job_id = :job_id",
            params,
        )


def update_job_url(job_id: int, url: str):
    """Overwrites a job's stored URL — used when ats/apply.py's real
    navigation resolves a discovery-time tracking link (Indeed's
    /rc/clk?jk=..., which detect_platform() can never identify anything
    from) to the actual application page it redirects to, so future views
    (e.g. the dashboard's "Easy Apply Only" filter) see the real
    destination instead of the tracking link forever."""
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET url = ? WHERE id = ?", (url, job_id))


def restore_job(job_id: int):
    """Pulls a job out of any excluded bucket (hard exclude, semi_excluded,
    or likely_excluded) and back into the normal queue."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET excluded = 0, phd_flag = NULL WHERE id = ?",
            (job_id,),
        )


def list_profile_answers() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM profile_answers ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_profile_answer(prompt: str, answer: str) -> int:
    """Adds a new prompt/answer pair, or overwrites the answer if that exact
    prompt text already has one (re-answering is deliberate, not a
    duplicate)."""
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO profile_answers (prompt, answer, created_at, updated_at)
            VALUES (:prompt, :answer, :now, :now)
            ON CONFLICT(prompt) DO UPDATE SET answer = :answer, updated_at = :now
            """,
            {"prompt": prompt, "answer": answer, "now": now},
        )
        row = conn.execute(
            "SELECT id FROM profile_answers WHERE prompt = ?", (prompt,)
        ).fetchone()
        return row["id"]


def delete_profile_answer(answer_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM profile_answers WHERE id = ?", (answer_id,))


def _normalize_prompt(prompt: str) -> str:
    """Strips whitespace and a trailing required-field asterisk before
    comparing two prompt strings. Confirmed live 2026-08-27: the identical
    question ("Are you legally authorized to work in the United States?")
    was saved once without a trailing "*" but showed up on a later SpaceX
    posting with one (Greenhouse sometimes bakes the required-marker "*"
    into the extracted label text and sometimes doesn't, depending on the
    posting's own markup) — an exact-text match missed it even though it's
    obviously the same question. Stored prompt text itself is left
    untouched (profile_answers.prompt is still the real UNIQUE key); this
    normalization only applies where two prompts get compared."""
    return prompt.strip().rstrip("*").strip()


def lookup_profile_answer(prompt: str) -> str | None:
    """Match against a previously saved profile_answers.prompt, ignoring a
    trailing required-field "*" and surrounding whitespace (see
    _normalize_prompt) — same matching semantics as
    list_unanswered_prompts()'s `answered` set, so a question answered once
    (via /profile or /struggles-to-answer) gets silently reused by
    ats/*.py handlers on every future application that asks the same
    prompt text, instead of being re-flagged forever."""
    if not prompt:
        return None
    target = _normalize_prompt(prompt)
    if not target:
        return None
    with get_conn() as conn:
        rows = conn.execute("SELECT prompt, answer FROM profile_answers").fetchall()
    for row in rows:
        if _normalize_prompt(row["prompt"]) == target:
            return row["answer"]
    return None


def list_unanswered_prompts() -> list[dict]:
    """Every distinct prompt string surfaced in some job's
    applications.needs_review_json that doesn't already have a matching
    row in profile_answers (see _normalize_prompt for what "matching"
    tolerates — a trailing required-field "*" and surrounding whitespace).
    Returns one entry per distinct prompt, with a count of how many jobs
    hit it and one example job for context — not one row per job, since
    the same custom question (e.g. "Are you eligible to work in the
    U.S.?") shows up on many postings on the same ATS platform."""
    with get_conn() as conn:
        answered = {
            _normalize_prompt(row["prompt"])
            for row in conn.execute("SELECT prompt FROM profile_answers")
        }
        rows = conn.execute(
            """
            SELECT applications.needs_review_json, jobs.id AS job_id, jobs.title, jobs.company
            FROM applications
            JOIN jobs ON jobs.id = applications.job_id
            WHERE applications.needs_review_json IS NOT NULL
            ORDER BY applications.id DESC
            """
        ).fetchall()

        by_prompt: dict[str, dict] = {}
        for row in rows:
            try:
                prompts = json.loads(row["needs_review_json"])
            except (TypeError, ValueError):
                continue
            for prompt in prompts:
                prompt = prompt.strip()
                if not prompt or _normalize_prompt(prompt) in answered:
                    continue
                entry = by_prompt.setdefault(prompt, {
                    "prompt": prompt, "count": 0,
                    "example_job_id": row["job_id"],
                    "example_title": row["title"],
                    "example_company": row["company"],
                })
                entry["count"] += 1

        return sorted(by_prompt.values(), key=lambda e: e["count"], reverse=True)


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {DB_PATH}")
