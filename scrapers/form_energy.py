"""Form Energy (long-duration iron-air battery storage) —
formenergy.com/careers -> jobs.ashbyhq.com/formenergy.

formenergy.com/careers/open-jobs embeds an Ashby widget
(`jobs.ashbyhq.com/formenergy/embed?version=2`); org slug "formenergy"
confirmed live 2026-08-26: api.ashbyhq.com/posting-api/job-board/formenergy
returns HTTP 200 with 184 real current postings (e.g. "Staff Mechanical
Engineer, Dimensional Management", Berkeley, CA; multiple roles at the
Weirton, WV factory). See scrapers/_ashby.py for the shared fetch/filter
logic and what its public API does/doesn't expose (no salary field, no
server-side keyword search).
"""
from scrapers._ashby import fetch_ashby_jobs

ORG_SLUG = "formenergy"
COMPANY_NAME = "Form Energy"


def search_form_energy(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_ashby_jobs(ORG_SLUG, "form_energy", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_form_energy("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
