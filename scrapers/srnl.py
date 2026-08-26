"""Savannah River National Laboratory (SRNL) — www.srnl.gov/careers/.

SRNL is a DOE national lab, contractor-operated (Battelle Savannah River
Alliance), so USAJobs.gov doesn't cover its postings the way it covers
direct federal positions — this needs its own source, same situation as
PNNL (see scrapers/pnnl.py).

Battelle also operates PNNL, so the working assumption going in was that
SRNL's career site might reuse PNNL's same career-site vendor/API shape.
That turned out to be wrong, verified live (2026-08-24): www.srnl.gov/careers/
is just a WordPress marketing page (its only API surface is WordPress's own
`wp-json/` REST API, nothing job-related) whose "Open Positions" button links
out to a completely different system:

    https://ewvl.fa.us8.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1

That's Oracle Fusion Cloud Recruiting ("Oracle Recruiting Cloud" / the
"oj-hcm-ce" Candidate Experience UI) — the exact same underlying platform
Stanford runs for SLAC (see scrapers/slac.py), just a different tenant host
(`ewvl.fa.us8.oraclecloud.com` instead of `careersearch.stanford.edu`) and
site number (`CX_1`, read directly out of the page's `<base data-sitenumber=
"CX_1">` tag, not guessed). Since Oracle Recruiting Cloud's REST API shape is
identical across tenants, this module is effectively scrapers/slac.py
retargeted at SRNL's tenant/site number — same two endpoints, same field
names, confirmed working with live requests:

    GET https://ewvl.fa.us8.oraclecloud.com/hcmRestApi/resources/latest/
        recruitingCEJobRequisitions
        ?onlyData=true&expand=requisitionList.secondaryLocations,flexFieldsFacet.values
        &finder=findReqs;siteNumber=CX_1,keyword=<kw>,limit=<n>,offset=0,
                sortBy=POSTING_DATES_DESC

    GET https://ewvl.fa.us8.oraclecloud.com/hcmRestApi/resources/latest/
        recruitingCEJobRequisitionDetails
        ?onlyData=true&finder=ById;Id="<id>",siteNumber=CX_1

No login, no bot-detection wall, unauthenticated like SLAC's tenant. The
list endpoint's `ShortDescriptionStr` is empty on every posting inspected;
the detail endpoint's `ExternalDescriptionStr` has the real HTML description
used here for the snippet (one extra request per result, same tradeoff as
SLAC). No structured salary field exists in either response, so `salary` is
always None.

Confirmed live: an "engineer" search returned real postings (e.g. "Cyber
Security Analyst- Engineer", Aiken, SC) with working detail pages.

Job posting URLs use the Candidate Experience site's own path, confirmed by
a live HEAD request:
    https://ewvl.fa.us8.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/<id>
"""
import html
import re

import requests

API_HOST = "https://ewvl.fa.us8.oraclecloud.com"
SEARCH_URL = f"{API_HOST}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
DETAIL_URL = f"{API_HOST}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
JOB_PAGE_BASE = f"{API_HOST}/hcmUI/CandidateExperience/en/sites/CX_1/job"
SITE_NUMBER = "CX_1"

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
        "source": "srnl",
        "source_job_id": job_id,
        "title": job.get("Title", ""),
        "company": "Savannah River National Laboratory",
        "location": job.get("PrimaryLocation"),
        "salary": None,
        "job_type": job.get("WorkplaceType") or None,
        "url": f"{JOB_PAGE_BASE}/{job_id}",
        "snippet": _fetch_snippet(job_id),
        "search_keyword": keyword,
    }


def search_srnl(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — SRNL's career site is a single
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
    jobs = search_srnl("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
