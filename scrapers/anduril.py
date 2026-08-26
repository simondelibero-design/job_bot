"""Anduril Industries (defense tech) — boards.greenhouse.io/andurilindustries.

The bare guess "anduril" 404s — the real `board_token` is
"andurilindustries", found by fetching anduril.com/careers/ and reading its
Content-Security-Policy header, which allowlists
`https://boards-api.greenhouse.io` (confirming the platform), then
confirming the exact token by hitting
boards-api.greenhouse.io/v1/boards/andurilindustries/jobs live 2026-08-26:
HTTP 200, 2193 real current postings (e.g. "2026 Early Career Electrical
Engineer" in Costa Mesa, CA), and the returned `content` field explicitly
reads "Anduril Industries is a defense technology company..." — confirms
this is genuinely Anduril's board. See scrapers/_greenhouse.py for the
shared fetch/filter logic and what the public Greenhouse API does/doesn't
expose (no salary or job_type fields).
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "andurilindustries"
COMPANY_NAME = "Anduril Industries"


def search_anduril(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "anduril", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_anduril("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
