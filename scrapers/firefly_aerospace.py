"""Firefly Aerospace — fireflyspace.com/careers.

firefly.com (the URL originally guessed from the company name) is an
unrelated parked domain for sale — the real company site is
**fireflyspace.com**. Its `/careers/` page is a WordPress page whose
"View Job Openings" section renders via
`<script src="https://careers-content.clearcompany.com/js/v1/career-site.js
?siteId=00ed92c3-5bfb-7bfb-456d-4d9d77fef9a5">` — identifying the ATS as
**ClearCompany**, a platform not previously in this codebase and not one of
the ones `ats/detect.py` knows.

Fetched that widget's own JS bundle
(`careers-content.clearcompany.com/js/v1/career-site-no-polyfill.js`) and
read its `ClearCompanyDataService` class directly (plain static JS, no
build tooling needed) to find the real API it calls — a public,
unauthenticated JSON endpoint, same tier as Greenhouse/Lever:

    GET https://careers-api.clearcompany.com/v1/{siteId}
        ?keywords=<kw>&pageIndex=<n>&pageSize=<size>

Confirmed live 2026-08-26: `pageSize=25` (this tenant's own configured
default, read from `GET .../v1/settings/{siteId}`) works cleanly;
`pageSize=500` in one test broke the connection mid-response
(`ChunkedEncodingError`) so pagination here sticks to the tenant's own
default page size rather than requesting an oversized page. `keywords` is a
real server-side full-text search (matches title *and* description, not
just title — confirmed: `keywords=software` returned "Flight Dynamics
Engineer III (Orbit Determination), Elytra", which has no literal "software"
in its title) against `totalCount` 176 total open postings; `keywords=
physicist` legitimately returned 0 (a real zero, not a broken query) while
`keywords=engineer` returned 102.

Each list-page job record already carries the full HTML `description`
inline (no separate detail-page fetch needed, unlike the Workday scrapers
here) plus a structured `locations` array (city/subdivision/country) used
for `location`. No salary or employment-type field exists anywhere in the
schema (keys present on every record: id, positionTitle, description,
openDate, postedDate, departmentId, departmentName, officeId, officeName,
location, locations, brandName, applyLink, canSelfSchedule) — confirmed by
inspecting every key on a live response — so both `salary` and `job_type`
are always None here, same honest-gap situation as scrapers/_greenhouse.py.
"""
import html
import re

import requests

SITE_ID = "00ed92c3-5bfb-7bfb-456d-4d9d77fef9a5"
API_BASE = f"https://careers-api.clearcompany.com/v1/{SITE_ID}"
COMPANY = "Firefly Aerospace"

PAGE_SIZE = 25  # this tenant's own configured default (from the /settings endpoint); 500 broke the connection
MAX_RESULTS = 200  # safety cap on pagination

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _extract_job(job: dict, keyword: str) -> dict | None:
    job_id = job.get("id")
    if not job_id:
        return None

    return {
        "source": "firefly_aerospace",
        "source_job_id": job_id,
        "title": job.get("positionTitle", ""),
        "company": job.get("brandName") or COMPANY,
        "location": job.get("location"),
        "salary": None,  # no salary field anywhere in this API's schema
        "job_type": None,  # ...nor an employment-type field
        "url": job.get("applyLink"),
        "snippet": _strip_html(job.get("description", ""))[:1000],
        "search_keyword": keyword,
    }


def search_firefly_aerospace(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location`, if given, is a client-side
    case-insensitive substring match against the record's `location` string
    — the API's own location filter is a facet (exact
    "CITY|STATE|COUNTRY" value from /settings), not a free-text search, so
    matching client-side against the human-readable string is simpler and
    matches this project's convention for facet-only sources."""
    location_lower = location.lower() if location else None

    all_results = []
    page_index = 0
    total_count = None
    while total_count is None or page_index * PAGE_SIZE < min(total_count, MAX_RESULTS):
        resp = requests.get(
            API_BASE,
            headers=_HEADERS,
            params={"keywords": keyword, "pageIndex": page_index, "pageSize": PAGE_SIZE},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if total_count is None:
            total_count = data.get("totalCount", 0)

        jobs = data.get("results", [])
        if not jobs:
            break

        for job in jobs:
            extracted = _extract_job(job, keyword)
            if not extracted:
                continue
            if location_lower and location_lower not in (extracted["location"] or "").lower():
                continue
            all_results.append(extracted)

        page_index += 1

    return all_results


if __name__ == "__main__":
    jobs = search_firefly_aerospace("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
