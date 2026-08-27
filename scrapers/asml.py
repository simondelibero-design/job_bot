"""ASML -- asml.com/en/careers/find-your-job / asml.wd3.myworkdayjobs.com.

ASML's own careers site (asml.com/en/careers/find-your-job) is a Sitecore/
Next.js app that pre-renders each result page server-side -- fetching its
own `_next/data/.../find-your-job.json` payload (a legitimate, if
Sitecore-build-hash-fragile, path) shows only page layout, not job data.
The individual job-detail JSON payload
(`_next/data/.../find-your-job/<slug>-j<id>.json`), however, includes a
`"source": "workday"` field and an `applyUrl` pointing at
**asml.wd3.myworkdayjobs.com**, tenant `asml`, site `ASMLEXT1` -- ASML's
Sitecore site is a wrapper around a real Workday tenant. Confirmed live
2026-08-26 that tenant answers the same public, unauthenticated CXS JSON
API used elsewhere in this project (boeing.py, draper.py, intel.py):

    POST https://asml.wd3.myworkdayjobs.com/wday/cxs/asml/ASMLEXT1/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://asml.wd3.myworkdayjobs.com/wday/cxs/asml/ASMLEXT1{externalPath}
         used here for a real job description to build the snippet, since
         the search response itself carries no description text.

Confirmed live (2026-08-26): "engineer" returned 505 real matches, including
real US postings despite ASML being Dutch (IT Infrastructure Engineer --
Hillsboro OR; Senior Proto Engineer -- Wilton CT; Training and Development
Project Manager -- San Diego CA) alongside Veldhoven/Taiwan/etc.

Like the other Workday scrapers here, applying goes through Workday's own
UI, which (per ats/workday.py) gates every application behind mandatory
account creation -- irrelevant since this project only discovers/logs jobs.

No structured compensation field exists on either the list or detail
endpoint (matching every other Workday tenant in this project), so `salary`
is always None.

The `jobs` search endpoint 400s on any `limit` above 20 (same behavior as
every other Workday tenant checked in this project) -- this paginates in
pages of 20 via `offset` up to a `_MAX_RESULTS` safety cap. Unlike Boeing/
Draper/Intel's tenants, this one's "total" field is populated correctly on
every page, not just page 1 (confirmed live 2026-08-26: offset 20 still
returned "total": 505) -- but the pagination loop still only reads it once
at offset 0, since a value that's sometimes wrong elsewhere and always
right here means "trust page 1" is a safe rule either way, not a tenant-
specific special case worth branching on.
"""
import re

import requests

TENANT_URL = "https://asml.wd3.myworkdayjobs.com"
SITE_ID = "ASMLEXT1"
SEARCH_URL = f"{TENANT_URL}/wday/cxs/asml/{SITE_ID}/jobs"
DETAIL_URL_BASE = f"{TENANT_URL}/wday/cxs/asml/{SITE_ID}"
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
        "source": "asml",
        "source_job_id": req_id,
        "title": posting.get("title", ""),
        "company": "ASML",
        "location": posting.get("locationsText"),
        "salary": None,  # no structured compensation field on this tenant
        "job_type": posting.get("timeType"),
        "url": f"{JOB_PAGE_BASE}{external_path}",
        "snippet": _fetch_snippet(external_path),
        "search_keyword": keyword,
    }


_PAGE_SIZE = 20  # confirmed live: this Workday tenant 400s on any limit > 20
_MAX_RESULTS = 100  # safety cap so a broad keyword can't trigger unbounded paging


def search_asml(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused -- ASML's Workday tenant search is
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
    jobs = search_asml("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
