"""Royal Philips / Philips Healthcare — careers.philips.com /
philips.wd3.myworkdayjobs.com.

careers.philips.com itself is unreachable from this environment: every
attempt (multiple retries, both a direct `requests.get` and a separate
fetch through a different network path) either times out at the raw TCP
connect stage or gets an immediate connection refusal from the resolved IP
(54.154.89.69) — no HTTP response, no challenge page, no CAPTCHA, nothing
that looks like an application-layer bot-detection wall to leave alone; it
reads as the host simply not being reachable from here (plausibly an
Akamai/CDN edge that only accepts traffic routed a particular way). Per
this project's rule, an unreachable host isn't something to route around
with proxies/VPNs — so careers.philips.com itself was left alone and this
scraper never touches it.

Instead, a plain web search turned up Philips' actual job data source
directly: **philips.wd3.myworkdayjobs.com**, site `jobs-and-careers`
(`https://philips.wd3.myworkdayjobs.com/en-US/jobs-and-careers`) — a
different host entirely, and one that IS reachable from here. Confirmed
live 2026-08-26 by hitting it with the same public, unauthenticated CXS
JSON API used elsewhere in this project:

    POST https://philips.wd3.myworkdayjobs.com/wday/cxs/philips/jobs-and-careers/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://philips.wd3.myworkdayjobs.com/wday/cxs/philips/jobs-and-careers{externalPath}
         (externalPath from the search response, e.g.
         "/job/Latham-New-York-United-States/Manufacturing-Engineer_573544-1") —
         used here for a real job description to build the snippet, since
         the search response itself carries no description text.

Confirmed live (2026-08-26): "engineer" returned 354 real matches
(Manufacturing Engineer, Systems Engineer, Packaging Engineer, spanning
Latham NY, Cambridge MA, Shenzhen, Suzhou, etc.); "physicist" returned 7;
"materials scientist" returned 3.

Like the other Workday scrapers here, applying goes through Workday's own
UI, which (per ats/workday.py) gates every application behind mandatory
account creation — irrelevant since this project only discovers/logs jobs.

No structured compensation field exists on the detail endpoint, so `salary`
is always None, same convention as boeing.py/draper.py.

The `jobs` search endpoint 400s on any `limit` above 20 (confirmed live,
same behavior as every other Workday tenant checked in this project) — this
paginates in pages of 20 via `offset` up to a `_MAX_RESULTS` safety cap.
This tenant also only populates the response's "total" field on the very
first page — every later page comes back with "total": 0 despite still
returning real jobPostings (confirmed live 2026-08-26, same quirk as
boeing.py/draper.py's tenants) — so the pagination loop captures `total`
once and ignores it on subsequent pages.
"""
import re

import requests

TENANT_URL = "https://philips.wd3.myworkdayjobs.com"
SITE_ID = "jobs-and-careers"
TENANT = "philips"
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
        "source": "philips",
        "source_job_id": req_id,
        "title": posting.get("title", ""),
        "company": "Royal Philips",
        "location": posting.get("locationsText"),
        "salary": None,  # no structured compensation field on this tenant
        "job_type": posting.get("timeType"),
        "url": f"{JOB_PAGE_BASE}{external_path}",
        "snippet": _fetch_snippet(external_path),
        "search_keyword": keyword,
    }


_PAGE_SIZE = 20  # confirmed live: this Workday tenant 400s on any limit > 20
_MAX_RESULTS = 100  # safety cap so a broad keyword can't trigger unbounded paging


def search_philips(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
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
    jobs = search_philips("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
