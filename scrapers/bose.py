"""Bose Corporation — jobs.bose.com / careers.bose.com.

Both jobs.bose.com and careers.bose.com redirect to careers.bose.com/us/en,
a Phenom People "CareerConnect" marketing/branding layer (confirmed by
`cdn.phenompeople.com/CareerConnectResources/BCRBCSUS/...` assets in the
page, tenant slug "BCRBCSUS"). Same situation found for ABB
(scrapers/abb.py): every job record in Phenom's own server-rendered
`/us/en/search-results` response carries an `applyUrl` that reveals Bose's
actual ATS underneath:

    https://boseallaboutme.wd503.myworkdayjobs.com/Bose_Careers/job/.../apply

i.e. Workday, tenant `boseallaboutme`, site `Bose_Careers`. Talking to that
tenant's own public, unauthenticated CXS JSON API directly (same pattern as
boeing.py/draper.py/abb.py) gives a real literal keyword search and skips
the extra front-end entirely:

    POST https://boseallaboutme.wd503.myworkdayjobs.com/wday/cxs/boseallaboutme/Bose_Careers/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://boseallaboutme.wd503.myworkdayjobs.com/wday/cxs/boseallaboutme/Bose_Careers{externalPath}
         — used here for a real job description to build the snippet, since
         the search response itself carries no description text.

Confirmed live (2026-08-26): "acoustic" returned 21 total matches
(Acoustical Engineer x2, Audio System Engineer, Senior Engineering Program
Manager - Audio Technology, Audio Engineer, DSP Engineer, etc.); "engineer"
returned far more across Bose's global sites (Framingham MA, Stuttgart,
Shenzhen, Shanghai).

Like the other Workday scrapers here, applying goes through Workday's own
UI, which (per ats/workday.py) gates every application behind mandatory
account creation — irrelevant since this project only discovers/logs jobs.

No structured compensation field exists on either the list or detail
endpoint, so `salary` is always None. `job_type` comes from the detail
endpoint's `timeType`.

The `jobs` search endpoint 400s on any `limit` above 20 (confirmed live,
same behavior as every other Workday tenant checked in this project) — this
paginates in pages of 20 via `offset` up to a `_MAX_RESULTS` safety cap.
This tenant also only populates the response's "total" field on the very
first page — every later page comes back with "total": 0 despite still
returning real jobPostings (confirmed live 2026-08-26, same quirk as
boeing.py/draper.py's tenants) — so the pagination loop captures `total`
once and ignores it on subsequent pages, rather than trusting each
response's value.
"""
import re

import requests

TENANT_URL = "https://boseallaboutme.wd503.myworkdayjobs.com"
SITE_ID = "Bose_Careers"
SEARCH_URL = f"{TENANT_URL}/wday/cxs/boseallaboutme/{SITE_ID}/jobs"
DETAIL_URL_BASE = f"{TENANT_URL}/wday/cxs/boseallaboutme/{SITE_ID}"
JOB_PAGE_BASE = f"{TENANT_URL}/{SITE_ID}"
COMPANY = "Bose Corporation"

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


def _fetch_detail(external_path: str) -> dict:
    """Returns {"snippet": ..., "job_type": ...}; blank values on any
    failure so one bad detail page doesn't sink the search."""
    try:
        resp = requests.get(f"{DETAIL_URL_BASE}{external_path}", headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        info = resp.json().get("jobPostingInfo", {})
        return {
            "snippet": _strip_html(info.get("jobDescription", ""))[:1000],
            "job_type": info.get("timeType"),
        }
    except requests.RequestException:
        return {"snippet": "", "job_type": None}


def _extract_job(posting: dict, keyword: str) -> dict | None:
    external_path = posting.get("externalPath")
    if not external_path:
        return None

    bullet_fields = posting.get("bulletFields") or []
    req_id = bullet_fields[0] if bullet_fields else external_path
    detail = _fetch_detail(external_path)

    return {
        "source": "bose",
        "source_job_id": req_id,
        "title": posting.get("title", ""),
        "company": COMPANY,
        "location": posting.get("locationsText"),
        "salary": None,  # no structured compensation field on this tenant
        "job_type": detail["job_type"],
        "url": f"{JOB_PAGE_BASE}{external_path}",
        "snippet": detail["snippet"],
        "search_keyword": keyword,
    }


_PAGE_SIZE = 20  # confirmed live: this Workday tenant 400s on any limit > 20
_MAX_RESULTS = 100  # safety cap so a broad keyword can't trigger unbounded paging


def search_bose(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Bose's Workday tenant search is
    keyword + facet based, not a geographic radius search."""
    results = []
    offset = 0
    total = None
    while total is None or offset < min(total, _MAX_RESULTS):
        payload = {"appliedFacets": {}, "limit": _PAGE_SIZE, "offset": offset, "searchText": keyword}
        resp = requests.post(SEARCH_URL, headers=_HEADERS, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # This tenant only populates "total" on the very first page (offset
        # 0) — confirmed live 2026-08-26: every subsequent page comes back
        # with "total": 0 even though jobPostings is still non-empty. Only
        # capture it once, or pagination stops after page 2 no matter how
        # many real results remain.
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
    jobs = search_bose("acoustic")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["job_type"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
