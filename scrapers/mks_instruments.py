"""MKS Instruments (which owns the Newport, Ophir, and ESI brands among
others) — mks.com/careers.

The careers page embeds a Workday tenant link directly in its filter
buttons (`href="https://mksinst.wd1.myworkdayjobs.com/MKSCareersAmericas..."`,
found by grepping the page HTML for `myworkdayjobs.com`): tenant `mksinst`,
site `MKSCareersAmericas`. (A separate `MKS-India-Careers` site also
appears in the page's markup for the India region specifically — not
covered here, since this project's effort budget only justified confirming
the Americas site, which is the one relevant to a US job search and where
Newport's own postings show up, e.g. several live Irvine, CA optics/optical
engineering roles — Newport's headquarters city.) Same public,
unauthenticated CXS JSON API pattern already used by boeing.py/draper.py/
lumentum.py in this project:

    POST https://mksinst.wd1.myworkdayjobs.com/wday/cxs/mksinst/MKSCareersAmericas/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://mksinst.wd1.myworkdayjobs.com/wday/cxs/mksinst/MKSCareersAmericas{externalPath}
         (externalPath from the search response, e.g.
         "/job/Irvine-CA/Principal-Optical-Engineer_R20...") — used here for
         a real job description to build the snippet, since the search
         response itself carries no description text.

Confirmed live (2026-08-26): 107 total postings on the tenant; "engineer"
returned all 107 as matches; "optics" returned 28 real matches (Optics
Fabricator, Principal Optical Engineer, Senior Optical Engineer — several
in Irvine, CA and Rochester, NY).

Like the other Workday scrapers here, applying goes through Workday's own
UI, which (per ats/workday.py) gates every application behind mandatory
account creation — irrelevant since this project only discovers/logs jobs.

No structured compensation field exists on the detail endpoint (matching
what a human sees on the page), so `salary` is always None.

This tenant's `jobs` search endpoint accepts `limit` up to 20 per page in
testing (matching the behavior already documented in boeing.py/draper.py/
lumentum.py for other Workday tenants) — this paginates in pages of 20 via
`offset` up to a `_MAX_RESULTS` safety cap, capturing `total` only from the
first page like those other scrapers (later pages are not re-trusted for
that value on other tenants in this project, and the same conservative
approach is used here even though it wasn't specifically re-verified for
this tenant, to stay consistent and avoid an early stop on a stale zero).
"""
import re

import requests

TENANT_URL = "https://mksinst.wd1.myworkdayjobs.com"
SITE_ID = "MKSCareersAmericas"
SEARCH_URL = f"{TENANT_URL}/wday/cxs/mksinst/{SITE_ID}/jobs"
DETAIL_URL_BASE = f"{TENANT_URL}/wday/cxs/mksinst/{SITE_ID}"
JOB_PAGE_BASE = f"{TENANT_URL}/{SITE_ID}"
COMPANY = "MKS Instruments"

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


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
        "source": "mks_instruments",
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


_PAGE_SIZE = 20  # confirmed live: matches the cap seen on other Workday tenants in this project
_MAX_RESULTS = 200  # safety cap so a broad keyword can't trigger unbounded paging


def search_mks_instruments(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — MKS's Workday tenant search is
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
    jobs = search_mks_instruments("optics")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
