"""Re-scores every job already in the database against the current
SECTOR_WEIGHTS / EXCLUDE_KEYWORDS in config.py. Needed because upsert_job()
does ON CONFLICT DO NOTHING — jobs discovered before a scoring-rule change
(like the PhD filter) never get re-evaluated on their own.
"""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from db.database import get_conn
from matcher.scorer import score_job


def rescore_all() -> dict:
    updated = 0
    newly_excluded = 0
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, snippet, location, salary, search_mode FROM jobs"
        ).fetchall()
        for row in rows:
            result = score_job(
                row["title"], row["snippet"] or "", row["location"],
                mode=row["search_mode"] or "local", salary=row["salary"],
            )
            conn.execute(
                """
                UPDATE jobs SET score = ?, priority_score = ?, matched_keywords = ?,
                                 excluded = ?, phd_flag = ?, distance_miles = ?, tier = ?,
                                 salary_annual_est = ?
                WHERE id = ?
                """,
                (
                    result["score"], result["priority_score"], json.dumps(result["matched"]),
                    int(result["excluded"]), result["phd_flag"], result["distance_miles"],
                    result["tier"], result["salary_annual_est"], row["id"],
                ),
            )
            updated += 1
            if result["excluded"]:
                newly_excluded += 1
    return {"rescored": updated, "excluded": newly_excluded}


if __name__ == "__main__":
    result = rescore_all()
    print(f"Rescored {result['rescored']} jobs — {result['excluded']} now excluded.")
