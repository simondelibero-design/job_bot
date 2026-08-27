"""Planet Labs PBC (Earth-observation satellite imagery) —
planet.com/company/careers/.

planet.com/careers/ 301s to planet.com/company/careers/, a Next.js SPA with
no ATS markers anywhere in its static HTML or script-src list (its job
listings render entirely client-side). To find the real data source
without guessing blindly, this project's own Playwright (not the shared
browser tool) was driven once against the live careers page to record
actual XHR traffic, which showed two calls straight to Greenhouse's public
API:

    GET https://api.greenhouse.io/v1/boards/planetlabs/departments?render_as=tree
    GET https://api.greenhouse.io/v1/boards/planetlabs/offices?render_as=tree

— confirming `board_token` = "planetlabs" (not a guessable lowercasing of
"Planet Labs"). Confirmed live 2026-08-26: `GET https://boards-api.
greenhouse.io/v1/boards/planetlabs/jobs` (the standard boards-api host used
elsewhere in this project, same data as the `api.greenhouse.io` host seen
in the XHR capture) returns HTTP 200 with 92 real current postings (e.g.
"ABM Marketing Manager, EMEA" in London and Berlin, "Account Executive,
Defence & Intelligence" across Japan/France/Sweden remote) — a real,
geographically varied board. See scrapers/_greenhouse.py for the shared
fetch/filter logic and what the public Greenhouse API does/doesn't expose
(no salary or job_type fields).
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "planetlabs"
COMPANY_NAME = "Planet Labs PBC"


def search_planet_labs(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "planet_labs", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_planet_labs("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
