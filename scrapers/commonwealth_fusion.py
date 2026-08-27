"""Commonwealth Fusion Systems (fusion energy) — cfs.energy/careers ->
jobs.lever.co/cfsenergy.

cfs.energy/careers embeds a Lever job board; the `board_token` is not a
simple lowercasing of the company name ("commonwealthfusion" 404s) — the
real token, "cfsenergy", was found by fetching cfs.energy/careers and
extracting the `jobs.lever.co/cfsenergy` link/embed from the page HTML,
then confirmed live 2026-08-26: api.lever.co/v0/postings/cfsenergy?mode=json
returns HTTP 200 with real current postings (e.g. a fusion-plant
engineering role tagged "#CFS-NE"), on Lever's default US host. See
scrapers/_lever.py for the shared fetch/filter logic.
"""
from scrapers._lever import fetch_lever_jobs

COMPANY_SLUG = "cfsenergy"
COMPANY_NAME = "Commonwealth Fusion Systems"


def search_commonwealth_fusion(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_lever_jobs(COMPANY_SLUG, "commonwealth_fusion", COMPANY_NAME, keyword, location)


if __name__ == "__main__":
    jobs = search_commonwealth_fusion("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
