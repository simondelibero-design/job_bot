"""Lockheed Martin — lockheedmartin.com/en-us/careers.html.

The corporate careers page is a static marketing page whose own "Search
Jobs" form (`method="get" action="https://lockheedmartin.eightfold.ai/careers"`)
hands off to a separate **Eightfold.ai** tenant — the same talent-platform
vendor already reverse-engineered for Northrop Grumman
(`scrapers/northrop_grumman.py` — see that module's docstring for the full
investigation). Eightfold isn't one of the ATS platforms `ats/detect.py`
already knows, so this is discovery-only, no auto-fill handler involved.

Confirmed live (2026-08-26) that Lockheed's tenant works exactly the same
way as Northrop Grumman's, just a different tenant host and `domain` value
(found the same way — driving the real site once with this project's own
Playwright, not the shared browser tool, and reading the XHR a live search
fires):

    GET https://lockheedmartin.eightfold.ai/api/pcsx/search
        ?domain=lockheedmartin.com&query=<kw>&location=&start=<offset>

    GET https://lockheedmartin.eightfold.ai/api/pcsx/position_details
        ?position_id=<id>&domain=lockheedmartin.com&hl=en

Same as the NG module: both need an `x-csrf-token` header (a plain
`<meta name="_csrf">` value on the page) and the cookies set on first page
load — ordinary CSRF handling, no login, no CAPTCHA, no JS challenge — so
plain `requests` reproduces it fine. Note "pcsx" in the API path is a
generic Eightfold internal theme/route name, not a per-tenant slug — it
appears identically on Lockheed's tenant even though this is a completely
separate company from Northrop Grumman.

Same honest gaps as the NG module: no structured salary field in the API,
so `salary` is pulled from a "Salary Range: $X - $Y" pattern in the
description text when present (regex, same as NG); `job_type` uses
`workLocationOption` (onsite/hybrid/remote) since there's no full/part-time
field.

Verified live: "physics" returned 77 total matches (Component Engineer,
Materials Engineer, Low Observable (RF) Engineer Sr, Staff Software
Engineer (Image Processing), etc.); "physicist" itself currently has zero
open reqs at Lockheed (a real result, not a bug — confirmed "engineer"
returns 1,135 total on the same pipeline).
"""
import html
import re

import requests

CAREERS_PAGE = "https://lockheedmartin.eightfold.ai/careers"
SEARCH_URL = "https://lockheedmartin.eightfold.ai/api/pcsx/search"
DETAIL_URL = "https://lockheedmartin.eightfold.ai/api/pcsx/position_details"
DOMAIN = "lockheedmartin.com"
COMPANY = "Lockheed Martin"

PAGE_SIZE = 10
MAX_RESULTS = 100  # safety cap on pagination + detail-page fetches

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_SALARY_RE = re.compile(
    r"Salary Range:\s*(\$[\d,]+(?:\.\d{2})?\s*-\s*\$[\d,]+(?:\.\d{2})?)", re.I
)


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _new_session() -> tuple[requests.Session, str]:
    """Loads the careers page once to establish cookies + a CSRF token,
    exactly what a real page load does before its own JS calls the API."""
    session = requests.Session()
    session.headers.update({"User-Agent": _UA, "Referer": CAREERS_PAGE})
    resp = session.get(CAREERS_PAGE, timeout=20)
    resp.raise_for_status()
    match = re.search(r'name="_csrf" content="([^"]+)"', resp.text)
    if not match:
        raise RuntimeError("lockheed_martin: couldn't find CSRF token on careers page")
    return session, match.group(1)


def _fetch_detail(session: requests.Session, csrf: str, position_id: int) -> dict:
    """Returns {"snippet": ..., "salary": ..., "job_type": ...}; blank
    values on any failure so one bad detail page doesn't sink the search."""
    try:
        resp = session.get(
            DETAIL_URL,
            params={"position_id": position_id, "domain": DOMAIN, "hl": "en"},
            headers={"x-csrf-token": csrf, "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        raw_desc = data.get("jobDescription", "")
        salary_match = _SALARY_RE.search(raw_desc)
        return {
            "snippet": _strip_html(raw_desc)[:1000],
            "salary": salary_match.group(1) if salary_match else None,
            "job_type": data.get("workLocationOption"),
        }
    except (requests.RequestException, ValueError):
        return {"snippet": "", "salary": None, "job_type": None}


def _extract_job(session: requests.Session, csrf: str, position: dict, keyword: str) -> dict | None:
    position_id = position.get("id")
    if not position_id:
        return None

    detail = _fetch_detail(session, csrf, position_id)
    locations = position.get("standardizedLocations") or position.get("locations") or []

    return {
        "source": "lockheed_martin",
        "source_job_id": position.get("displayJobId") or str(position_id),
        "title": position.get("name", ""),
        "company": COMPANY,
        "location": "; ".join(locations) if locations else None,
        "salary": detail["salary"],
        "job_type": detail["job_type"],
        "url": f"{CAREERS_PAGE}/job/{position_id}",
        "snippet": detail["snippet"],
        "search_keyword": keyword,
    }


def search_lockheed_martin(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location` IS honored — Eightfold's
    search API takes a free-text location string."""
    session, csrf = _new_session()

    all_results = []
    start = 0
    while start < MAX_RESULTS:
        resp = session.get(
            SEARCH_URL,
            params={"domain": DOMAIN, "query": keyword, "location": location or "", "start": start},
            headers={"x-csrf-token": csrf, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        positions = data.get("positions", [])
        if not positions:
            break

        for position in positions:
            extracted = _extract_job(session, csrf, position, keyword)
            if extracted:
                all_results.append(extracted)

        if len(positions) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    return all_results


if __name__ == "__main__":
    jobs = search_lockheed_martin("physics")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["salary"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
