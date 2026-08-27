"""Stratasys (3D printing / additive manufacturing) — stratasys.com/en/careers.

The literal URL in this project's task description, stratasys.com/en/careers,
404s (confirmed live 2026-08-26). The real careers link, found on
stratasys.com's own homepage, is careers.stratasys.com — a separate domain
running the same SAP SuccessFactors "Jobs2Web" platform as Oxford
Instruments (identified from `successfactors.com` asset hosts in the page
source), just wearing an older table-layout template skin rather than
Oxford Instruments' card/tile skin. See scrapers/_successfactors.py, which
handles both skins with one extraction pass, and whose docstring explains
why the site's own `?q=` search parameter is deliberately NOT used here
(confirmed live: it silently ignores the query on this platform).

Verified live 2026-08-26: 54 total open postings across the full board
(Eden Prairie MN, Minnetonka MN, Belton TX, Rehovot/Kiryat Gat IL,
Aylesbury UK, etc.); "additive" and "manufacturing" both matched real,
relevant postings (Manufacturing Operations Project Manager, Production
Lead, Manufacturing Planning & Scheduling Manager, etc.).
"""
from scrapers._successfactors import fetch_successfactors_jobs

BASE_URL = "https://careers.stratasys.com"
COMPANY = "Stratasys"


def search_stratasys(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_successfactors_jobs(BASE_URL, "stratasys", COMPANY, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_stratasys("manufacturing")
    print(f"Found {len(jobs)} jobs for 'manufacturing'")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])

    print()
    jobs = search_stratasys("engineer")
    print(f"Found {len(jobs)} jobs for 'engineer'")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"])
