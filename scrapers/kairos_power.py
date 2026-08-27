"""Kairos Power (advanced nuclear, molten-salt reactors) — kairospower.com/careers
-> job-boards.greenhouse.io/kairospower.

kairospower.com/careers embeds a Greenhouse job-board script
(`boards.greenhouse.io/embed/job_board/js?for=kairospower`), giving the
`board_token` directly — confirmed live 2026-08-26:
boards-api.greenhouse.io/v1/boards/kairospower/jobs returns HTTP 200 with
real current postings (e.g. a role listed across "Alameda, CA,
Albuquerque, NM or Oak Ridge, TN"). See scrapers/_greenhouse.py for the
shared fetch/filter logic and what the public Greenhouse API does/doesn't
expose (no salary or job_type fields).
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "kairospower"
COMPANY_NAME = "Kairos Power"


def search_kairos_power(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "kairos_power", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_kairos_power("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
