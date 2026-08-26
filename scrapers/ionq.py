"""IonQ (quantum computing) — job-boards.greenhouse.io/ionq.

Greenhouse-hosted; `board_token` "ionq" confirmed live 2026-08-26 (HTTP 200,
105 real current postings returned, e.g. "Associate Firmware Engineer" in
Pleasanton, CA — clearly IonQ's actual board, not a placeholder). See
scrapers/_greenhouse.py for the shared fetch/filter logic and what the
public Greenhouse API does/doesn't expose (no salary or job_type fields).
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "ionq"
COMPANY_NAME = "IonQ"


def search_ionq(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "ionq", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_ionq("quantum")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
