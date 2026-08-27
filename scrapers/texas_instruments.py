"""Texas Instruments -- careers.ti.com.

careers.ti.com 302-redirects to careers.ti.com/en/sites/CX, whose HTML
carries a `data-apibaseurl="https://edbz.fa.us2.oraclecloud.com:443"` and
`data-sitenumber="CX"` -- **Oracle Recruiting Cloud** (Oracle Fusion HCM's
candidate-experience module), a platform not present in `ats/detect.py`'s
`PLATFORM_PATTERNS`. Oracle Recruiting Cloud exposes a real public,
unauthenticated REST API that the site's own frontend calls client-side:

    GET https://edbz.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions
        ?onlyData=true
        &expand=requisitionList.secondaryLocations,flexFieldsFacet.values
        &finder=findReqs;siteNumber=CX,facetsList=LOCATIONS,limit=<n>,offset=<n>,
                sortBy=POSTING_DATES_DESC,keyword=<kw>

Two real quirks found and confirmed live (2026-08-26), neither of them
bot-detection:
  1. Omitting the `expand=requisitionList.secondaryLocations,...` param
     doesn't error -- it just silently returns an empty `requisitionList`
     on every page while still reporting a nonzero `TotalJobsCount`. Not
     obvious from the finder syntax itself; found by comparing a bare
     curl call (which the site's own frontend never makes) against what
     the frontend's actual XHR sends.
  2. The keyword parameter is `keyword=`, not the more REST-conventional
     `searchKeyword=` (which 400s with an explicit "not valid" error
     naming the finder value) -- found by trial against the finder
     grammar's own error message.

Pagination via `offset`/`limit` (capped at `_PAGE_SIZE` per the frontend's
own usual page size) returns a stable `TotalJobsCount` and non-overlapping
result sets across pages (confirmed live: 50 unique `Id`s across two pages
of 25 each, no duplicates) -- unlike the Workday tenants elsewhere in this
project, this API needs no "only trust page 1" workaround.

Confirmed live (2026-08-26): "engineer" returned TotalJobsCount 540 across
TI's global fabs and design centers (Supplier Quality Engineer, Field
Applications Engineer - MCU, Manufacturing Technician Supervisor, Equipment
Engineering Technician, etc. -- Malaysia, Germany, and elsewhere; TI posts
plenty of US-based roles too, e.g. Dallas/Sherman TX, under other keywords).

A separate `recruitingCEJobRequisitionDetails` endpoint
(`finder=ById;Id="<id>",siteNumber=CX`) carries the full HTML description
(`ExternalDescriptionStr`) used here for the snippet -- the list endpoint's
own `ShortDescriptionStr` is empty on every requisition checked.

No structured salary field exists anywhere in this API's schema (not just
unpopulated), so `salary` is always None, same honest-gap situation as
ORNL/LANL/MITRE. `job_type` uses the detail endpoint's `JobSchedule`, which
is often None in practice (TI mostly doesn't populate it) but is the only
plausible full/part-time-shaped field this API exposes.

Applying goes through Oracle Recruiting Cloud's own candidate-experience UI
(account creation, per the usual pattern for major-vendor ATS platforms in
this project) -- irrelevant since this project only discovers/logs jobs;
no ats/*.py handler exists for this platform.
"""
import html
import re

import requests

API_BASE = "https://edbz.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
DETAIL_BASE = "https://edbz.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
JOB_PAGE_BASE = "https://careers.ti.com/en/sites/CX/job"
SITE_NUMBER = "CX"
COMPANY = "Texas Instruments"

_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

_PAGE_SIZE = 25
_MAX_RESULTS = 100  # safety cap on pagination + detail-page fetches


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_detail(req_id: str) -> dict:
    """Returns {"snippet": ..., "job_type": ...}; blank values on any
    failure so one bad detail page doesn't sink the search."""
    try:
        finder = f'ById;Id="{req_id}",siteNumber={SITE_NUMBER}'
        resp = requests.get(DETAIL_BASE, headers=_HEADERS,
                             params={"expand": "all", "finder": finder}, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return {"snippet": "", "job_type": None}
        item = items[0]
        return {
            "snippet": _strip_html(item.get("ExternalDescriptionStr", ""))[:1000],
            "job_type": item.get("JobSchedule"),
        }
    except (requests.RequestException, ValueError, IndexError):
        return {"snippet": "", "job_type": None}


def _extract_job(req: dict, keyword: str) -> dict | None:
    req_id = req.get("Id")
    if not req_id:
        return None

    detail = _fetch_detail(req_id)

    return {
        "source": "texas_instruments",
        "source_job_id": req_id,
        "title": req.get("Title", ""),
        "company": COMPANY,
        "location": req.get("PrimaryLocation"),
        "salary": None,  # no salary field anywhere in this API's schema
        "job_type": detail["job_type"],
        "url": f"{JOB_PAGE_BASE}/{req_id}",
        "snippet": detail["snippet"],
        "search_keyword": keyword,
    }


def search_texas_instruments(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused -- this API's location filtering
    needs a pre-resolved `locationId` (a facet value from a separate
    lookup), not a free-text string or radius, so it isn't wired up here."""
    all_results = []
    offset = 0
    total = None
    while total is None or offset < min(total, _MAX_RESULTS):
        finder = (f"findReqs;siteNumber={SITE_NUMBER},facetsList=LOCATIONS,"
                  f"limit={_PAGE_SIZE},offset={offset},sortBy=POSTING_DATES_DESC,"
                  f"keyword={keyword}")
        resp = requests.get(API_BASE, headers=_HEADERS, params={
            "onlyData": "true",
            "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
            "finder": finder,
        }, timeout=20)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            break
        item = items[0]
        if total is None:
            total = item.get("TotalJobsCount", 0)

        reqs = item.get("requisitionList", [])
        if not reqs:
            break
        for req in reqs:
            extracted = _extract_job(req, keyword)
            if extracted:
                all_results.append(extracted)
        offset += _PAGE_SIZE

    return all_results


if __name__ == "__main__":
    jobs = search_texas_instruments("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
