"""3M — 3m.com/3M/en_US/careers-us / 3m.wd1.myworkdayjobs.com.

www.3m.com/3M/en_US/careers-us itself was not fetchable from this
environment: every `requests`/curl attempt against it (fresh TLS handshake
succeeds, then an HTTP/2 stream reset with INTERNAL_ERROR immediately after
the request is sent) failed at the transport layer before any HTTP
response body ever came back — no challenge page, no CAPTCHA, nothing to
read or interpret, just a reset connection. That's a plausible edge/WAF
behavior, but there's nothing to reverse-engineer or route around (no
headers, tokens, or encoding to fix — see general_dynamics.py/mitre.py for
what a legitimate fix on that side of the line looks like), so per this
project's rule it was left alone rather than probed further.

Instead, a plain web search turned up 3M's actual job data source
directly: **3m.wd1.myworkdayjobs.com**, site `Search`
(`https://3m.wd1.myworkdayjobs.com/Search`) — reachable fine from here, no
resets, no challenge. Confirmed live 2026-08-26 with the same public,
unauthenticated CXS JSON API used elsewhere in this project:

    POST https://3m.wd1.myworkdayjobs.com/wday/cxs/3m/Search/jobs
         {"appliedFacets": {}, "limit": ..., "offset": 0, "searchText": "..."}

    GET  https://3m.wd1.myworkdayjobs.com/wday/cxs/3m/Search{externalPath}
         (externalPath from the search response, e.g.
         "/job/US-Minnesota-Maplewood/Pilot-Plant-Technician_R01157942-1") —
         used here for a real job description to build the snippet, since
         the search response itself carries no description text.

Confirmed live (2026-08-26): "engineer" returned 264 real matches (Sr
Industrial Engineer - Optimization, Pilot Plant Technician roles, etc.);
"materials scientist" returned 8; "physicist" returned 1 (a real, verified
low count, not a broken query — 3M's postings mostly use "engineer"/
"scientist" rather than "physicist").

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

TENANT_URL = "https://3m.wd1.myworkdayjobs.com"
SITE_ID = "Search"
TENANT = "3m"
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
        "source": "three_m",
        "source_job_id": req_id,
        "title": posting.get("title", ""),
        "company": "3M",
        "location": posting.get("locationsText"),
        "salary": None,  # no structured compensation field on this tenant
        "job_type": posting.get("timeType"),
        "url": f"{JOB_PAGE_BASE}{external_path}",
        "snippet": _fetch_snippet(external_path),
        "search_keyword": keyword,
    }


_PAGE_SIZE = 20  # confirmed live: this Workday tenant 400s on any limit > 20
_MAX_RESULTS = 100  # safety cap so a broad keyword can't trigger unbounded paging


def search_three_m(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
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
    jobs = search_three_m("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
