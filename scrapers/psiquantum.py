"""PsiQuantum (quantum computing) — job-boards.greenhouse.io/psiquantum.

Greenhouse-hosted; `board_token` "psiquantum" confirmed live 2026-08-26
(HTTP 200, 74 real current postings, e.g. "Cryostat Equipment Engineer" in
Milpitas, CA and "Director, Australia Finance" in Brisbane — a real,
current, geographically-spread board, not a redirect/placeholder). See
scrapers/_greenhouse.py for the shared fetch/filter logic and what the
public Greenhouse API does/doesn't expose (no salary or job_type fields).
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "psiquantum"
COMPANY_NAME = "PsiQuantum"


def search_psiquantum(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "psiquantum", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_psiquantum("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
