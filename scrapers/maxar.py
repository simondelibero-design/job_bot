"""Maxar Technologies — now rebranded **Vantor** (maxar.com/careers 301s to
vantor.com/careers; the news/press coverage of this rebrand is from
mid-2026). Kept as scrapers/maxar.py per the task's original company name,
since that's still the widely-known/searched identity, but `company` in
returned results reflects the current legal name.

vantor.com/careers is a marketing landing page; the actual job board it
links to is a Workday tenant, `maxar.wd1.myworkdayjobs.com`, site `Vantor`
(found by grepping the careers page HTML for `myworkdayjobs.com`, then
confirmed live with curl — note the tenant slug is still "maxar" even
though the site id itself was renamed to "Vantor" post-rebrand). Same
platform/pattern as scrapers/boeing.py, scrapers/draper.py, and
scrapers/sierra_space.py — this scraper only uses the public,
unauthenticated CXS JSON API Workday's own search UI calls client-side, no
login required:

    POST https://maxar.wd1.myworkdayjobs.com/wday/cxs/maxar/Vantor/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://maxar.wd1.myworkdayjobs.com/wday/cxs/maxar/Vantor{externalPath}
         (externalPath from the search response, e.g.
         "/job/McLean-VA/Geospatial-Analyst_R24392") — used here for a real
         job description to build the snippet, since the search response
         itself carries no description text.

Confirmed live (2026-08-26): 148 total postings on the tenant; "engineer"
returned real matches including "Geospatial Analyst" (McLean, VA) and
"Sr. Mission Analysis Engineer – Aerospace Systems (TS/SCI)".

Like the other Workday scrapers here, applying goes through Workday's own
UI, which (per ats/workday.py) gates every application behind mandatory
account creation — irrelevant since this project only discovers/logs jobs.

No structured compensation field exists on either the list or detail
endpoint, so `salary` is always None.

The `jobs` search endpoint 400s on any `limit` above 20 (same behavior
confirmed on every other Workday tenant in this project) — this paginates
in pages of 20 via `offset` up to a `_MAX_RESULTS` safety cap. This tenant
also only populates the response's "total" field on the very first page —
every later page comes back with "total": 0 despite still returning real
jobPostings (same quirk documented in boeing.py/draper.py) — so the
pagination loop captures `total` once and ignores it on subsequent pages.
"""
import re

import requests

TENANT_URL = "https://maxar.wd1.myworkdayjobs.com"
TENANT = "maxar"
SITE_ID = "Vantor"
SEARCH_URL = f"{TENANT_URL}/wday/cxs/{TENANT}/{SITE_ID}/jobs"
DETAIL_URL_BASE = f"{TENANT_URL}/wday/cxs/{TENANT}/{SITE_ID}"
JOB_PAGE_BASE = f"{TENANT_URL}/{SITE_ID}"
COMPANY = "Vantor (formerly Maxar Technologies)"

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
        "source": "maxar",
        "source_job_id": req_id,
        "title": posting.get("title", ""),
        "company": COMPANY,
        "location": posting.get("locationsText"),
        "salary": None,  # no structured compensation field on this tenant
        "job_type": posting.get("timeType"),
        "url": f"{JOB_PAGE_BASE}{external_path}",
        "snippet": _fetch_snippet(external_path),
        "search_keyword": keyword,
    }


_PAGE_SIZE = 20  # confirmed live: this Workday tenant 400s on any limit > 20
_MAX_RESULTS = 100  # safety cap so a broad keyword can't trigger unbounded paging


def search_maxar(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — this Workday tenant's search is
    keyword + facet based, not a geographic radius search."""
    results = []
    offset = 0
    total = None
    while total is None or offset < min(total, _MAX_RESULTS):
        payload = {"appliedFacets": {}, "limit": _PAGE_SIZE, "offset": offset, "searchText": keyword}
        resp = requests.post(SEARCH_URL, headers=_HEADERS, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # This tenant only populates "total" on the very first page — see
        # module docstring for why subsequent pages ignore it.
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
    jobs = search_maxar("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
