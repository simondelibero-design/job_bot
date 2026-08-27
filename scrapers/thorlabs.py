"""Thorlabs — thorlabs.com/careers.cfm.

thorlabs.com/careers.cfm is a Vue single-page app shell (no server-rendered
job content at all — 39 lines of HTML, just a `<div id="app">` mount
point). Its JS bundle (`/assets/index-*.js`) references a
`Workable:JobsApiURL` config value and a `YN.Workable` job-source enum,
identifying **Workable** as the ATS — not one of the platforms already
known to `ats/detect.py`. The bundle loads the actual API URL from a
runtime config store rather than hardcoding it, so the exact endpoint
wasn't visible in the JS text; the Workable account slug was found by
guessing the obvious value against Workable's own public widget API and
confirming live 2026-08-26:

    GET https://apply.workable.com/api/v1/widget/accounts/thorlabs
        -> HTTP 200, {"name": "Thorlabs", "jobs": [...]}  (76 postings)

    GET https://apply.workable.com/api/v1/widget/accounts/thorlabs?details=true
        -> same list, each job additionally carries a full HTML
        `description` field (confirmed live).

This is Workable's own public, unauthenticated jobs-widget API (the same
one Workable-hosted career pages embed client-side everywhere) — no login,
no session, no bot-detection dance, same tier as the Greenhouse/Lever
helpers.

No structured salary field exists in the response schema; `employment_type`
IS present and populated (e.g. "Full-time") unlike the Greenhouse/Lever
boards elsewhere in this project, so `job_type` is real here. This board
covers Thorlabs' worldwide postings (US/NJ, UK, Sweden, China, Japan, etc.)
from one account — no free-text/keyword search param exists on the widget
API, so filtering happens client-side against the title, same pattern as
aps.py/anl.py for small single-employer boards.

Verified live 2026-08-26: 76 total postings; "engineer" matched several
real listings (across US, UK, and Sweden offices).
"""
import html
import re

import requests

ACCOUNT_SLUG = "thorlabs"
API_URL = f"https://apply.workable.com/api/v1/widget/accounts/{ACCOUNT_SLUG}"
COMPANY = "Thorlabs"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _format_location(job: dict) -> str | None:
    city = job.get("city")
    state = job.get("state")
    country = job.get("country")
    parts = [p for p in (city, state if state != city else None, country) if p]
    return ", ".join(parts) if parts else None


def _extract_job(job: dict, keyword: str) -> dict | None:
    shortcode = job.get("shortcode")
    if not shortcode:
        return None

    return {
        "source": "thorlabs",
        "source_job_id": job.get("code") or shortcode,
        "title": job.get("title", ""),
        "company": COMPANY,
        "location": _format_location(job),
        "salary": None,  # no structured compensation field in Workable's widget API
        "job_type": job.get("employment_type"),
        "url": job.get("url") or job.get("shortlink"),
        "snippet": _strip_html(job.get("description", ""))[:1000],
        "search_keyword": keyword,
    }


def search_thorlabs(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Workable's widget API has no
    keyword or location filter param, so both `keyword` matching and any
    location narrowing happen client-side against the full board."""
    resp = requests.get(API_URL, headers={"User-Agent": _UA, "Accept": "application/json"},
                         params={"details": "true"}, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    keyword_lower = keyword.lower()
    location_lower = location.lower() if location else None

    results = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        if keyword_lower not in title.lower():
            continue
        if location_lower:
            haystack = " ".join(str(job.get(k) or "") for k in ("city", "state", "country")).lower()
            if location_lower not in haystack:
                continue
        extracted = _extract_job(job, keyword)
        if extracted:
            results.append(extracted)
    return results


if __name__ == "__main__":
    jobs = search_thorlabs("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
