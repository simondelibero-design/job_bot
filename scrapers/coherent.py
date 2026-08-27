"""Coherent Corp. (formerly II-VI, merged with the former Coherent Inc.) —
coherent.com/peopleandculture/job-search (coherent.com/careers redirects
here).

The careers page itself is a marketing shell; its "Job Search" link points
at a real career site run on **Oracle Recruiting Cloud** (Oracle Fusion
HCM's "Candidate Experience" module), not one of the ATS platforms already
known to `ats/detect.py`. Found by grepping the job-search page HTML for
country-specific "Search Jobs" links, which all point at
`hcwp.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/<site>/jobs`
— the US site is `CX_1` (confirmed live 2026-08-26; other countries use
their own site codes, e.g. `Singapore-Careers`, `CX_7007` for Korea).

Oracle Recruiting Cloud exposes a real public, unauthenticated REST API —
the same endpoint its own Candidate Experience SPA calls client-side:

    GET https://hcwp.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions
        ?onlyData=true
        &expand=requisitionList.secondaryLocations,flexFieldsFacet.values
        &finder=findReqs;siteNumber=CX_1,facetsList=LOCATIONS;WORK_LOCATIONS;
         WORKPLACE_TYPES;TITLES;CATEGORIES;ORGANIZATIONS;POSTING_DATES;FLEX_FIELDS,
         limit=<n>,offset=<n>,keyword=<kw>,sortBy=POSTING_DATES_DESC

Two things confirmed live 2026-08-26 while getting this working:
  - The `expand=requisitionList.secondaryLocations,flexFieldsFacet.values`
    param is NOT cosmetic — omitting it (even with everything else
    identical) makes the API return a real `TotalJobsCount` but a *null*
    `requisitionList`, i.e. counts with no actual records. With it present,
    `requisitionList` is populated as expected. This is an ordinary query
    param the site's own frontend always sends, not an access-control gate.
  - `keyword` is a genuine server-side full-text search (unlike Greenhouse/
    Lever's public APIs, which silently ignore any search param) — e.g.
    "engineer" -> 211 total, "laser" -> 71, "optical" -> 133, "technician"
    -> 82, all confirmed live with real, different counts. It also does its
    own spell-correction ("physicist" comes back with
    `CorrectedKeyword: "physics"` and 211 hits under the corrected term) —
    left as-is here rather than second-guessed.
  - `limit`/`offset` paginate as expected (confirmed a `limit=50,offset=25`
    request returns items 25-74 with `Offset`/`Limit` echoed back
    correctly), so this scraper pages through in chunks up to a
    `_MAX_RESULTS` safety cap like the other high-volume scrapers here.

Every requisition record checked had every compensation- and employment-
type-adjacent field (`JobType`, `WorkerType`, `ContractType`, `JobSchedule`,
etc.) set to `None` — Coherent's postings apparently don't populate any of
them through this API — so `salary` and `job_type` are always None here,
same honest-gap treatment as anl.py/ornl.py.

Job detail page URL pattern
(`hcwp.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/{Id}`)
confirmed live to resolve (HTTP 200) for a real requisition Id.

Verified live 2026-08-26: "engineer" returned 211 total postings across
Coherent's US sites (e.g. "Senior/Lead Engineer" in Sherman, TX describing
an AI/ML automation role for the wafer fab); "laser" returned 71.
"""
import html
import re

import requests

SITE_NUMBER = "CX_1"  # Coherent's US Oracle Recruiting Cloud site
API_BASE = "https://hcwp.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
JOB_PAGE_BASE = f"https://hcwp.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/{SITE_NUMBER}/job"
COMPANY = "Coherent Corp."

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_FACETS = (
    "LOCATIONS;WORK_LOCATIONS;WORKPLACE_TYPES;TITLES;CATEGORIES;"
    "ORGANIZATIONS;POSTING_DATES;FLEX_FIELDS"
)

_PAGE_SIZE = 50
_MAX_RESULTS = 200  # safety cap on pagination


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _extract_job(req: dict, keyword: str) -> dict | None:
    req_id = req.get("Id")
    if not req_id:
        return None

    return {
        "source": "coherent",
        "source_job_id": str(req_id),
        "title": req.get("Title", ""),
        "company": COMPANY,
        "location": req.get("PrimaryLocation"),
        "salary": None,  # no populated compensation field on this tenant — see module docstring
        "job_type": req.get("JobType") or req.get("WorkerType"),  # always None on records checked, kept for forward-compat
        "url": f"{JOB_PAGE_BASE}/{req_id}",
        "snippet": _strip_html(req.get("ShortDescriptionStr", ""))[:1000],
        "search_keyword": keyword,
    }


def search_coherent(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Oracle Recruiting Cloud's public
    API does support a `Location`/`Radius` finder param in principle, but it
    wasn't exercised here (keyword search alone was enough to get complete,
    correct results within this project's effort budget)."""
    results = []
    offset = 0
    total = None
    while total is None or offset < min(total, _MAX_RESULTS):
        finder = (
            f"findReqs;siteNumber={SITE_NUMBER},facetsList={_FACETS},"
            f"limit={_PAGE_SIZE},offset={offset},keyword={keyword},sortBy=POSTING_DATES_DESC"
        )
        resp = requests.get(
            API_BASE,
            headers={"User-Agent": _UA, "Accept": "application/json"},
            params={
                "onlyData": "true",
                "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
                "finder": finder,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items") or []
        if not items:
            break
        item = items[0]
        if total is None:
            total = item.get("TotalJobsCount", 0)

        requisitions = item.get("requisitionList") or []
        if not requisitions:
            break
        for req in requisitions:
            extracted = _extract_job(req, keyword)
            if extracted:
                results.append(extracted)
        offset += _PAGE_SIZE

    return results


if __name__ == "__main__":
    jobs = search_coherent("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
