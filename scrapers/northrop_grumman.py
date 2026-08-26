"""Northrop Grumman — jobs.northropgrumman.com.

careers.northropgrumman.com (the URL originally guessed) doesn't resolve at
all; the real careers site is reached by clicking "Careers" from
www.northropgrumman.com, which 308-redirects to www.northropgrumman.com/careers
(a marketing landing page) whose "Search Jobs" links point at the actual
job-search app: **jobs.northropgrumman.com/careers**.

That app is not one of the ATS platforms this codebase already knows
(Workday/iCIMS/Greenhouse/Lever/etc.) — its HTML references
`static.vscdn.net/fonts/css/eightfold-font-base.css` and internal theme keys
like `pcsx-theme-linear-gradient-start`, identifying it as **Eightfold.ai**
("pcsx" is Northrop Grumman's Eightfold tenant slug), a talent-platform
vendor not present in `ats/detect.py`'s `PLATFORM_PATTERNS`. No existing
auto-fill handler applies here — this module is discovery-only, same as the
national-lab scrapers.

The obvious guessed endpoint (`/api/apply/v2/jobs`, a path used by some
other Eightfold tenants) does not exist on this tenant — it 404s to the SPA
shell. The real endpoint was found by driving the actual site once with
Playwright (this project's own script, not the shared browser tool) and
recording the XHR traffic a real search fires:

    GET https://jobs.northropgrumman.com/api/pcsx/search
        ?domain=ngc.com&query=<kw>&location=&start=<offset>

    GET https://jobs.northropgrumman.com/api/pcsx/position_details
        ?position_id=<id>&domain=ngc.com&hl=en

Both require an `x-csrf-token` header and the session cookies set on first
load of jobs.northropgrumman.com/careers — this is ordinary CSRF handling
(the token is a plain `<meta name="_csrf">` tag on the page, no login, no
CAPTCHA, no interactive challenge), not a bot-detection wall, so it's fine
to reproduce with plain `requests`: fetch the careers page once per search
to mint a token+cookies, then hit the two JSON endpoints directly. Verified
live (2026-08-26) with a fresh session and no browser automation.

The search endpoint paginates 10 results per page (a `num=` override was
tried and had no effect) and returns a real total (`data.count`) — e.g.
2,643 total hits for "engineer" — so pagination here is capped like the
other single-employer scrapers in this project (MAX_RESULTS) rather than
walked to exhaustion.

`position_details` carries the full HTML job description but no dedicated
salary/employment-type fields; Northrop Grumman postings that publish pay
put it inline in the description text as "Primary/Full Level Salary Range:
$X - $Y" (confirmed on a live posting), so `salary` is pulled out of the
description with a regex rather than a structured field; `job_type` uses
the description's `workLocationOption` (onsite/hybrid/remote) since no
full/part-time field exists in the API response.
"""
import html
import re

import requests

CAREERS_PAGE = "https://jobs.northropgrumman.com/careers"
SEARCH_URL = "https://jobs.northropgrumman.com/api/pcsx/search"
DETAIL_URL = "https://jobs.northropgrumman.com/api/pcsx/position_details"
DOMAIN = "ngc.com"
COMPANY = "Northrop Grumman"

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
        raise RuntimeError("northrop_grumman: couldn't find CSRF token on careers page")
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
        "source": "northrop_grumman",
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


def search_northrop_grumman(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
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
    jobs = search_northrop_grumman("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["salary"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
