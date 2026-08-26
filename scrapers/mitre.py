"""The MITRE Corporation — jobs.mitre.org (redirects to mitre.dejobs.org).

jobs.mitre.org 301s to mitre.dejobs.org/jobs/ — MITRE's careers site runs
on **DirectEmployers' "dejobs.org"** multi-tenant job board platform, not
one of the ATS platforms already known to `ats/detect.py`. dejobs.org is a
Nuxt SPA whose initial HTML embeds its own config
(`"api-url":"https://prod-search-api.jobsyn.org/api/"`, `source:"solr"`),
pointing at a public Solr-backed search API run by jobsyn.org (also a
DirectEmployers property).

Confirmed live (2026-08-26) by driving the real site once with Playwright
(this project's own script, not the shared browser tool) and recording the
XHR a real keyword search fires:

    GET https://prod-search-api.jobsyn.org/api/v1/solr/search?q=<kw>&page=<n>

A bare `requests` call to that URL 400s with `{"errors": {"origin": "The
origin is required."}}`, then `{"errors": "Mismatched origin."}` for a
guessed standard `Origin` header — the real browser traffic showed the
actual header the frontend sends is a nonstandard `x-origin:
mitre.dejobs.org` (not the standard `Origin` header), plus a `Referer`.
Both are plain, static, non-secret values — no session, cookie, token, or
JS challenge involved — so reproducing them with `requests` is ordinary
header-matching, not evasion of any access control.

Each job record in the response carries `title_exact`, `guid`, `title_slug`,
`city_exact`/`state_short` and a full `description`, but no direct
permalink field. The site's own job URLs were confirmed by inspecting real
rendered links to follow the pattern
`https://mitre.dejobs.org/<city-slug>/<title-slug>/<guid>/job/` where
`<city-slug>` is `f"{city_exact}-{state_short}"` lowercased with spaces
turned to hyphens (verified against several live links, e.g.
`/mclean-va/senior-position-navigation-and-timing-engineer/<guid>/job/`).

No salary or employment-type field exists anywhere in the API response (not
just unpopulated — the schema itself has no such key), so both are always
None here, same honest-gap situation as ORNL/LANL.

Verified live: "physicist" returned 10 real MITRE postings (Senior
Position Navigation and Timing Engineer, Earth Systems Scientist, Battery
Scientist, Energy Technologies Engineer/Scientist, etc.) with
`pagination.total == 10` (single page).
"""
import html
import re

import requests

SEARCH_URL = "https://prod-search-api.jobsyn.org/api/v1/solr/search"
JOB_BASE = "https://mitre.dejobs.org"
COMPANY = "The MITRE Corporation"

PAGE_SIZE = 10  # fixed by the API, not overridable via a param we found
MAX_RESULTS = 100  # safety cap on pagination

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "x-origin": "mitre.dejobs.org",
    "Referer": "https://mitre.dejobs.org/",
}


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _city_slug(job: dict) -> str:
    city = (job.get("city_exact") or "").strip().lower().replace(" ", "-")
    state = (job.get("state_short") or "").strip().lower()
    if city and state:
        return f"{city}-{state}"
    return city or "location"


def _extract_job(job: dict, keyword: str) -> dict | None:
    guid = job.get("guid")
    title_slug = job.get("title_slug")
    if not guid or not title_slug:
        return None

    title = job.get("title_exact", "")
    location = job.get("location_exact") or None
    url = f"{JOB_BASE}/{_city_slug(job)}/{title_slug}/{guid}/job/"

    return {
        "source": "mitre",
        "source_job_id": job.get("reqid") or guid,
        "title": title,
        "company": COMPANY,
        "location": location,
        "salary": None,  # no salary field anywhere in this API's schema
        "job_type": None,  # same — no employment-type field exists
        "url": url,
        "snippet": _strip_html(job.get("description", ""))[:1000],
        "search_keyword": keyword,
    }


def search_mitre(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — this endpoint's location filters
    are facet-based (city/state slugs from the result set), not a free-text
    or radius geographic search."""
    all_results = []
    page = 1
    while len(all_results) < MAX_RESULTS:
        resp = requests.get(
            SEARCH_URL,
            headers=_HEADERS,
            params={"q": keyword, "page": page},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        jobs = data.get("jobs", [])
        if not jobs:
            break

        for job in jobs:
            extracted = _extract_job(job, keyword)
            if extracted:
                all_results.append(extracted)

        pagination = data.get("pagination", {})
        if not pagination.get("has_more_pages"):
            break
        page += 1

    return all_results


if __name__ == "__main__":
    jobs = search_mitre("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
