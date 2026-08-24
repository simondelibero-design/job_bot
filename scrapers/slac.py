"""SLAC National Accelerator Laboratory — careers.slac.stanford.edu.

SLAC is a DOE Office of Science national lab but, unlike the contractor-run
labs (PNNL/Battelle, BNL/Brookhaven Science Associates), it's operated
directly by Stanford University — so its HR system runs on Stanford's own
infrastructure rather than a typical national-lab careers vendor. Verified
live (2026-08-24) rather than assumed: careers.slac.stanford.edu turned out
to be a themed front-end for Oracle Fusion Cloud Recruiting ("Oracle
Recruiting Cloud" / the "oj-hcm-ce" Candidate Experience UI, visible in the
page's own script tags), hosted at a separate Stanford-wide host,
careersearch.stanford.edu, under site number CX_1001 (both the tenant host
and site number were read out of the page's `<base>` tag, not guessed).

That Oracle Candidate Experience UI calls a public, unauthenticated REST API
to do its own job search and detail rendering — found by recognizing the
`hcmRestApi` path already present in the page markup and testing the
standard Oracle Recruiting Cloud endpoint shapes against it directly:

    GET https://careersearch.stanford.edu/hcmRestApi/resources/latest/
        recruitingCEJobRequisitions
        ?onlyData=true&expand=requisitionList.secondaryLocations,flexFieldsFacet.values
        &finder=findReqs;siteNumber=CX_1001,keyword=<kw>,limit=<n>,offset=0,
                sortBy=POSTING_DATES_DESC

    GET https://careersearch.stanford.edu/hcmRestApi/resources/latest/
        recruitingCEJobRequisitionDetails
        ?onlyData=true&finder=ById;Id="<id>",siteNumber=CX_1001

The list endpoint gives title/location/workplace-type but only a mostly-
empty `ShortDescriptionStr`; the detail endpoint (one extra request per
result — fine at SLAC's result volumes, dozens per keyword) has the real
`ExternalDescriptionStr` used here for the snippet. No structured salary
field exists in either response, so `salary` is always None.

Confirmed live: a "physicist" search returned 12 real results (LCLS Duty
Technician, Accelerator Technologist II, Beam Delivery Systems Engineering
Department Head, etc.) out of 77 total open postings on the tenant.

Job posting URLs use the Candidate Experience site's own path, confirmed by
a live HEAD request:
    https://careersearch.stanford.edu/hcmUI/CandidateExperience/en/sites/SLAC/job/<id>
"""
import html
import re

import requests

API_HOST = "https://careersearch.stanford.edu"
SEARCH_URL = f"{API_HOST}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
DETAIL_URL = f"{API_HOST}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
JOB_PAGE_BASE = f"{API_HOST}/hcmUI/CandidateExperience/en/sites/SLAC/job"
SITE_NUMBER = "CX_1001"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _clean_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_snippet(job_id: str) -> str:
    try:
        params = {"onlyData": "true", "finder": f'ById;Id="{job_id}",siteNumber={SITE_NUMBER}'}
        resp = requests.get(DETAIL_URL, headers=_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return ""
        desc = items[0].get("ExternalDescriptionStr", "")
        return _clean_html(desc)[:1000]
    except requests.RequestException:
        return ""


def _extract_job(job: dict, keyword: str) -> dict | None:
    job_id = job.get("Id")
    if not job_id:
        return None

    return {
        "source": "slac",
        "source_job_id": job_id,
        "title": job.get("Title", ""),
        "company": "SLAC National Accelerator Laboratory",
        "location": job.get("PrimaryLocation"),
        "salary": None,
        "job_type": job.get("WorkplaceType"),
        "url": f"{JOB_PAGE_BASE}/{job_id}",
        "snippet": _fetch_snippet(job_id),
        "search_keyword": keyword,
    }


def search_slac(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — SLAC's career site is a single
    employer's postings, not a general job board with geographic search."""
    params = {
        "onlyData": "true",
        "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
        "finder": (
            f"findReqs;siteNumber={SITE_NUMBER},keyword={keyword},"
            "limit=100,offset=0,sortBy=POSTING_DATES_DESC"
        ),
    }
    resp = requests.get(SEARCH_URL, headers=_HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("items", [])
    if not items:
        return []

    results = []
    for job in items[0].get("requisitionList", []):
        extracted = _extract_job(job, keyword)
        if extracted:
            results.append(extracted)
    return results


if __name__ == "__main__":
    jobs = search_slac("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
