"""GE HealthCare — careers.gehealthcare.com / gehc.wd5.myworkdayjobs.com.

careers.gehealthcare.com is a Phenom People ("CareerConnect") career-site
skin, same product as Siemens Healthineers' careers site (see
scrapers/siemens_healthineers.py for the general pattern) — its HTML pulls
branding/CSS/JS from `phenompeople.com/CareerConnectResources/GEVGHLGLOBAL/
...`. Rather than reverse-engineer Phenom's own search widget, this scraper
goes straight at the underlying Workday tenant Phenom is skinning: a plain
web search turned up **gehc.wd5.myworkdayjobs.com**, site
`GEHC_ExternalSite` (og:title "GE HealthCare Careers"). Confirmed live
2026-08-26 by hitting that tenant directly with the same public,
unauthenticated CXS JSON API used elsewhere in this project:

    POST https://gehc.wd5.myworkdayjobs.com/wday/cxs/gehc/GEHC_ExternalSite/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://gehc.wd5.myworkdayjobs.com/wday/cxs/gehc/GEHC_ExternalSite{externalPath}
         (externalPath from the search response, e.g.
         "/job/Remote/Biomedical-Technician-I_R4042830-1") — used here for a
         real job description to build the snippet, since the search
         response itself carries no description text.

Confirmed live (2026-08-26): "engineer" returned 554 real matches (Director
Marketing - Radiology CT & Xray, Lead Engineer Supplier Quality, Computerized
Systems Validation & Data Integrity Lead, etc.); "physicist" returned 6;
"materials scientist" returned 2.

Like the other Workday scrapers here, applying goes through Workday's own
UI, which (per ats/workday.py) gates every application behind mandatory
account creation — irrelevant since this project only discovers/logs jobs.

No structured compensation field exists on the detail endpoint, so `salary`
is always None, same convention as boeing.py/draper.py.

The `jobs` search endpoint 400s on any `limit` above 20 (confirmed live,
same behavior as every other Workday tenant checked in this project) — this
paginates in pages of 20 via `offset` up to a `_MAX_RESULTS` safety cap.
Unlike boeing.py/draper.py's tenants, this tenant's "total" field IS
correctly populated on every page (confirmed live 2026-08-26, e.g. page 2
of "engineer" still reports total=554) — but the pagination loop still only
reads it once from the first page, since that's already correct here and
staying uniform with the other Workday scrapers costs nothing.
"""
import re

import requests

TENANT_URL = "https://gehc.wd5.myworkdayjobs.com"
SITE_ID = "GEHC_ExternalSite"
TENANT = "gehc"
SEARCH_URL = f"{TENANT_URL}/wday/cxs/{TENANT}/{SITE_ID}/jobs"
DETAIL_URL_BASE = f"{TENANT_URL}/wday/cxs/{TENANT}/{SITE_ID}"
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
        "source": "ge_healthcare",
        "source_job_id": req_id,
        "title": posting.get("title", ""),
        "company": "GE HealthCare",
        "location": posting.get("locationsText"),
        "salary": None,  # no structured compensation field on this tenant
        "job_type": posting.get("timeType"),
        "url": f"{JOB_PAGE_BASE}{external_path}",
        "snippet": _fetch_snippet(external_path),
        "search_keyword": keyword,
    }


_PAGE_SIZE = 20  # confirmed live: this Workday tenant 400s on any limit > 20
_MAX_RESULTS = 100  # safety cap so a broad keyword can't trigger unbounded paging


def search_ge_healthcare(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — this tenant's search is keyword +
    facet based, not a geographic radius search."""
    results = []
    offset = 0
    total = None
    while total is None or offset < min(total, _MAX_RESULTS):
        payload = {"appliedFacets": {}, "limit": _PAGE_SIZE, "offset": offset, "searchText": keyword}
        resp = requests.post(SEARCH_URL, headers=_HEADERS, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # Capture "total" once from the first page only — this tenant does
        # report it correctly on later pages too (unlike boeing.py/
        # draper.py's), but reading it once is still correct and keeps this
        # scraper's pagination logic identical to every other Workday
        # scraper in this project.
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
    jobs = search_ge_healthcare("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
