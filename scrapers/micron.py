"""Micron Technology -- micron.com/about/careers -> careers.micron.com.

www.micron.com/about/careers is a marketing landing page whose "See Career
Opportunities" link points at the real job board, careers.micron.com/careers
-- an Eightfold.ai-hosted site (same platform northrop_grumman.py identified
first; see scrapers/_eightfold.py's docstring for how the underlying
`/api/pcsx/...` endpoints were found and confirmed shared across companies).

Confirmed live 2026-08-26: `domain=micron.com` is the correct Eightfold
tenant key (the page's own "Apply" links point at
micron.eightfold.ai/careers/join?domain=micron.com, matching). "engineer"
returned a real TotalJobsCount of 2,321 across Micron's global fabs
(Singapore, Boise ID, Manassas VA, Hyderabad, Taiwan, etc.).

Like the other Eightfold scrapers here, applying goes through Eightfold's
own UI -- irrelevant since this project only discovers/logs jobs. No
structured salary field exists on this tenant (see scrapers/_eightfold.py's
docstring), so `salary` is always None; `job_type` uses `workLocationOption`
(onsite/hybrid/remote) since no full/part-time field exists either.
"""
from scrapers._eightfold import fetch_eightfold_jobs

CAREERS_PAGE = "https://careers.micron.com/careers"
API_BASE = "https://careers.micron.com/api/pcsx"
DOMAIN = "micron.com"
SOURCE = "micron"
COMPANY = "Micron Technology"


def search_micron(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location` IS honored -- Eightfold's
    search API takes a free-text location string."""
    return fetch_eightfold_jobs(CAREERS_PAGE, API_BASE, DOMAIN, SOURCE, COMPANY, keyword,
                                 location=location)


if __name__ == "__main__":
    jobs = search_micron("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
