"""Analog Devices (ADI) -- analog.com/en/careers.html /
analogdevices.wd1.myworkdayjobs.com.

Both www.analog.com and its careers.analog.com alias (which just 307s to
www.analog.com/en/careers.html) run behind bot-mitigation that a plain
`requests`/curl call -- even matching a normal Chrome desktop User-Agent --
can't get past: the TLS connection itself hangs/times out rather than
returning any HTTP response (confirmed live 2026-08-26, repeatedly, on both
the careers page and the bare domain root). This looks like TLS/JA3
fingerprinting, not a full interactive challenge: a real headless Chromium
browser (Playwright, this project's own script, used here only once to
look at the page -- not to drive the scraper) loads the exact same URL fine
and returns 200. That one-time page load showed the page's own "Search
Jobs" links point at a separate, public Workday tenant --
**analogdevices.wd1.myworkdayjobs.com**, site `External` -- which is NOT
behind that same front door and answers plain `requests` calls normally
(confirmed live 2026-08-26, no browser automation needed for the actual
scraper). Same public, unauthenticated CXS JSON API used elsewhere in this
project (boeing.py, draper.py, intel.py):

    POST https://analogdevices.wd1.myworkdayjobs.com/wday/cxs/analogdevices/External/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://analogdevices.wd1.myworkdayjobs.com/wday/cxs/analogdevices/External{externalPath}
         used here for a real job description to build the snippet, since
         the search response itself carries no description text.

Confirmed live (2026-08-26): "engineer" returned 834 real matches (Engineer/
Quality Engineering -- Wilmington MA; Staff Engineer, Facilities Engineering
-- San Jose CA; Reliability/DFT/Equipment Engineering roles across Ireland,
the Philippines, India).

Like the other Workday scrapers here, applying goes through Workday's own
UI, which (per ats/workday.py) gates every application behind mandatory
account creation -- irrelevant since this project only discovers/logs jobs.

No structured compensation field exists on either the list or detail
endpoint, so `salary` is always None.

The `jobs` search endpoint 400s on any `limit` above 20 (same behavior as
every other Workday tenant checked in this project) -- this paginates in
pages of 20 via `offset` up to a `_MAX_RESULTS` safety cap. This tenant
also only populates the response's "total" field on the very first page --
every later page comes back with "total": 0 despite still returning real
jobPostings (confirmed live 2026-08-26) -- so the pagination loop captures
`total` once and ignores it on subsequent pages.
"""
import re

import requests

TENANT_URL = "https://analogdevices.wd1.myworkdayjobs.com"
SITE_ID = "External"
SEARCH_URL = f"{TENANT_URL}/wday/cxs/analogdevices/{SITE_ID}/jobs"
DETAIL_URL_BASE = f"{TENANT_URL}/wday/cxs/analogdevices/{SITE_ID}"
JOB_PAGE_BASE = f"{TENANT_URL}/{SITE_ID}"

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _fetch_snippet(external_path: str) -> str:
    try:
        resp = requests.get(f"{DETAIL_URL_BASE}{external_path}", headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        desc = resp.json().get("jobPostingInfo", {}).get("jobDescription", "")
        return _strip_html(desc)[:1000]
    except requests.RequestException:
        return ""


def _extract_job(posting: dict, keyword: str) -> dict | None:
    external_path = posting.get("externalPath")
    if not external_path:
        return None

    bullet_fields = posting.get("bulletFields") or []
    req_id = bullet_fields[0] if bullet_fields else external_path

    return {
        "source": "analog_devices",
        "source_job_id": req_id,
        "title": posting.get("title", ""),
        "company": "Analog Devices",
        "location": posting.get("locationsText"),
        "salary": None,  # no structured compensation field on this tenant
        "job_type": posting.get("timeType"),
        "url": f"{JOB_PAGE_BASE}{external_path}",
        "snippet": _fetch_snippet(external_path),
        "search_keyword": keyword,
    }


_PAGE_SIZE = 20  # confirmed live: this Workday tenant 400s on any limit > 20
_MAX_RESULTS = 100  # safety cap so a broad keyword can't trigger unbounded paging


def search_analog_devices(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused -- ADI's Workday tenant search is
    keyword + facet based, not a geographic radius search."""
    results = []
    offset = 0
    total = None
    while total is None or offset < min(total, _MAX_RESULTS):
        payload = {"appliedFacets": {}, "limit": _PAGE_SIZE, "offset": offset, "searchText": keyword}
        resp = requests.post(SEARCH_URL, headers=_HEADERS, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if total is None:
            total = data.get("total", 0)

        postings = data.get("jobPostings", [])
        if not postings:
            break
        for posting in postings:
            extracted = _extract_job(posting, keyword)
            if extracted:
                results.append(extracted)
        offset += _PAGE_SIZE
    return results


if __name__ == "__main__":
    jobs = search_analog_devices("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
