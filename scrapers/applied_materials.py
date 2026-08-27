"""Applied Materials -- careers.appliedmaterials.com.

careers.appliedmaterials.com is an Eightfold.ai-hosted site, same platform
as Northrop Grumman / Micron / GlobalFoundries in this project (see
scrapers/_eightfold.py's docstring for how the underlying `/api/pcsx/...`
endpoints were found and confirmed shared across companies).

Confirmed live 2026-08-26: `domain=appliedmaterials.com` is the correct
Eightfold tenant key. "engineer" returned a real TotalJobsCount of 1,348,
including Santa Clara, CA (Lithography Process Engineer IV) and other
US-based roles (field service, mechanical engineering).

Like the other Eightfold scrapers here, applying goes through Eightfold's
own UI -- irrelevant since this project only discovers/logs jobs. No
structured salary field exists on this tenant (see scrapers/_eightfold.py's
docstring), so `salary` is always None; `job_type` uses `workLocationOption`
(onsite/hybrid/remote) since no full/part-time field exists either.
"""
from scrapers._eightfold import fetch_eightfold_jobs

CAREERS_PAGE = "https://careers.appliedmaterials.com/careers"
API_BASE = "https://careers.appliedmaterials.com/api/pcsx"
DOMAIN = "appliedmaterials.com"
SOURCE = "applied_materials"
COMPANY = "Applied Materials"


def search_applied_materials(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location` IS honored -- Eightfold's
    search API takes a free-text location string."""
    return fetch_eightfold_jobs(CAREERS_PAGE, API_BASE, DOMAIN, SOURCE, COMPANY, keyword,
                                 location=location)


if __name__ == "__main__":
    jobs = search_applied_materials("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
