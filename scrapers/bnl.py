"""Brookhaven National Laboratory (BNL) — careers.bnl.gov / bnl.wd1.myworkdayjobs.com.

BNL is a DOE national lab, contractor-operated (Brookhaven Science
Associates), so USAJobs.gov doesn't cover its postings the way it covers
direct federal positions — this needs its own source, same reasoning as
scrapers/pnnl.py.

Unlike PNNL, BNL's career site (https://www.bnl.gov/careers/) is just a
landing page with a "Search open jobs" button; the actual job board is a
Workday tenant (`bnl.wd1.myworkdayjobs.com`, site ID `Externa` — found by
reading the button's onclick handler in the page's raw HTML, not by
guessing). Workday postings normally hit the account-creation wall this
project already documented in ats/workday.py — but that wall only blocks
the *application* flow. Workday's job-search results and job-detail pages
are served by a separate, public, unauthenticated JSON API (the "CXS" API
that Workday's own search UI calls client-side) that requires no login:

    POST https://bnl.wd1.myworkdayjobs.com/wday/cxs/bnl/Externa/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://bnl.wd1.myworkdayjobs.com/wday/cxs/bnl/Externa{externalPath}
         (externalPath comes from the search response, e.g.
         "/job/Upton-NY/Goldhaber-Fellow_JR102637") — used here for a real
         job description to build the snippet, since the search response
         itself carries no description text.

Confirmed live (2026-08-24): 65 total postings on the tenant, a "physicist"
search returned 4 real results (Goldhaber Fellow, Postdoc in Neutrino
Physics, etc.). No structured salary field exists anywhere in the API —
some descriptions mention a number inline (NY pay-transparency language)
but it's free text, not a field, so it isn't parsed out here.

One HTTP request per result is made to fetch its detail page for the
snippet — fine for BNL's result volumes (dozens, not thousands) but not
something to run against a huge unfiltered result set.

The `jobs` search endpoint also turned out to 400 on any `limit` above 20
(confirmed by testing 25/30/50/100 live, all rejected) — so this paginates
in pages of 20 via `offset` up to a `_MAX_RESULTS` safety cap instead of
requesting everything in one call the way PNNL's `/api/jobs` allows.
"""
import re

import requests

TENANT_URL = "https://bnl.wd1.myworkdayjobs.com"
SITE_ID = "Externa"
SEARCH_URL = f"{TENANT_URL}/wday/cxs/bnl/{SITE_ID}/jobs"
DETAIL_URL_BASE = f"{TENANT_URL}/wday/cxs/bnl/{SITE_ID}"
JOB_PAGE_BASE = f"{TENANT_URL}/en-US/{SITE_ID}"

_HEADERS = {
    "Content-Type": "application/json",
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
        "source": "bnl",
        "source_job_id": req_id,
        "title": posting.get("title", ""),
        "company": "Brookhaven National Laboratory",
        "location": posting.get("locationsText"),
        "salary": None,
        "job_type": posting.get("timeType"),
        "url": f"{JOB_PAGE_BASE}{external_path}",
        "snippet": _fetch_snippet(external_path),
        "search_keyword": keyword,
    }


_PAGE_SIZE = 20  # confirmed live: this Workday tenant 400s on any limit > 20
_MAX_RESULTS = 100  # safety cap so a broad keyword can't trigger unbounded paging


def search_bnl(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — BNL's Workday tenant is a single
    employer's postings, not a general job board with geographic search."""
    results = []
    offset = 0
    total = None
    while total is None or offset < min(total, _MAX_RESULTS):
        payload = {"appliedFacets": {}, "limit": _PAGE_SIZE, "offset": offset, "searchText": keyword}
        resp = requests.post(SEARCH_URL, headers=_HEADERS, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
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
    jobs = search_bnl("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
