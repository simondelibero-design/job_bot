"""Helion Energy (fusion energy) — helionenergy.com/careers ->
jobs.ashbyhq.com/helion.

helionenergy.com/careers embeds Ashby job postings directly (links to
`jobs.ashbyhq.com/helion/<posting-id>`); org slug "helion" confirmed live
2026-08-26: api.ashbyhq.com/posting-api/job-board/helion returns HTTP 200
with 104 real current postings (e.g. "R&D Hardware Test & Development
Manager", Everett, WA). First Ashby-hosted company found in this project —
see scrapers/_ashby.py for the shared fetch/filter logic and what its
public API does/doesn't expose (no salary field, no server-side keyword
search).
"""
from scrapers._ashby import fetch_ashby_jobs

ORG_SLUG = "helion"
COMPANY_NAME = "Helion Energy"


def search_helion(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_ashby_jobs(ORG_SLUG, "helion", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_helion("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
