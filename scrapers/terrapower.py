"""TerraPower (advanced nuclear) — terrapower.com/careers ->
job-boards.greenhouse.io/terrapowerllc.

The bare guess "terrapower" isn't the real `board_token` — the real one,
"terrapowerllc", was found by fetching terrapower.com/careers and
extracting the embedded Greenhouse job-board script
(`boards.greenhouse.io/embed/job_board/js?for=terrapowerllc`), then
confirmed live 2026-08-26: boards-api.greenhouse.io/v1/boards/terrapowerllc/jobs
returns HTTP 200 with real current postings (e.g. requisition "2026-329"
in Everett, WA). See scrapers/_greenhouse.py for the shared fetch/filter
logic and what the public Greenhouse API does/doesn't expose (no salary or
job_type fields).
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "terrapowerllc"
COMPANY_NAME = "TerraPower"


def search_terrapower(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "terrapower", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_terrapower("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
