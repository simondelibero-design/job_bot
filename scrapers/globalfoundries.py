"""GlobalFoundries -- gf.com/careers -> careers.gf.com.

gf.com/careers is a marketing landing page whose "Search Jobs" link points
at the real job board, careers.gf.com/careers -- an Eightfold.ai-hosted
site, same platform as Northrop Grumman / Micron / Applied Materials in
this project (see scrapers/_eightfold.py's docstring for how the underlying
`/api/pcsx/...` endpoints were found and confirmed shared across companies).

One real quirk confirmed live 2026-08-26: `domain=gf.com` (the obvious
guess, matching the vanity domain) 404s on this tenant -- the Eightfold
tenant key here is actually the full legal name, `domain=globalfoundries.com`,
which works and returned a real TotalJobsCount of 383 ("engineer": Senior
Engineer Design Enablement, Supplier Quality Engineer, etc., across
Singapore, Malaysia, India, and GF's US/German fabs).

Like the other Eightfold scrapers here, applying goes through Eightfold's
own UI -- irrelevant since this project only discovers/logs jobs. No
consistently-present salary or employment-type field exists on this tenant
(see scrapers/_eightfold.py's docstring -- GF does have a tenant-specific
`efcustomTextTimeType` custom field, e.g. "Full time", but it isn't part of
the shared helper's contract so isn't relied on here), so `salary` is
always None; `job_type` uses `workLocationOption` (onsite/hybrid/remote).
"""
from scrapers._eightfold import fetch_eightfold_jobs

CAREERS_PAGE = "https://careers.gf.com/careers"
API_BASE = "https://careers.gf.com/api/pcsx"
DOMAIN = "globalfoundries.com"
SOURCE = "globalfoundries"
COMPANY = "GlobalFoundries"


def search_globalfoundries(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location` IS honored -- Eightfold's
    search API takes a free-text location string."""
    return fetch_eightfold_jobs(CAREERS_PAGE, API_BASE, DOMAIN, SOURCE, COMPANY, keyword,
                                 location=location)


if __name__ == "__main__":
    jobs = search_globalfoundries("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
