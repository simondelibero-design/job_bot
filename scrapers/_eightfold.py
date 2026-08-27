"""Shared helper for companies whose careers site runs on Eightfold.ai,
hosted on the company's own `careers.{company}.com` domain rather than
`{tenant}.eightfold.ai` directly.

scrapers/northrop_grumman.py (which predates this helper) reverse-engineered
the pattern first: the page's HTML references `static.vscdn.net` and
`pcsx-theme-*` CSS keys, identifying Eightfold even though its URL doesn't
match any pattern in `ats/detect.py`. The real search/detail API isn't in
the page's static HTML (an SPA shell) — it was found by driving the real
site once with Playwright (this project's own script, not the shared
browser tool) and recording the XHR a real keyword search fires. Confirmed
live 2026-08-26 that at least four companies share this exact same
`/api/pcsx/...` path structure on their own domain, differing only in
`domain=` (the company's own corporate domain, used by Eightfold as the
tenant key) and the CSRF-minting careers page URL:
  - Northrop Grumman: jobs.northropgrumman.com/careers, domain=ngc.com
  - Micron: careers.micron.com/careers, domain=micron.com
  - Applied Materials: careers.appliedmaterials.com/careers,
    domain=appliedmaterials.com
  - GlobalFoundries: careers.gf.com/careers, domain=globalfoundries.com
    (note: domain=gf.com 404s on this tenant — confirmed live, only the
    full "globalfoundries.com" works, so don't assume the vanity domain
    always matches the Eightfold tenant key)

    GET https://careers.{co}.com/api/pcsx/search
        ?domain=<tenant-domain>&query=<kw>&location=&start=<offset>

    GET https://careers.{co}.com/api/pcsx/position_details
        ?position_id=<id>&domain=<tenant-domain>&hl=en

Both require an `x-csrf-token` header and the session cookies set on first
load of the careers page — ordinary CSRF handling (a plain `<meta
name="_csrf">` tag, no login, no CAPTCHA, no interactive challenge), not a
bot-detection wall, so it's fine to reproduce with plain `requests`.

The search endpoint paginates 10 results per page and returns a real total
(`data.count`), so pagination here is capped like the other single-employer
scrapers in this project (max_results) rather than walked to exhaustion.

`position_details` carries the full HTML job description, a `publicUrl`
(absolute link to the posting) and a `workLocationOption` (onsite/hybrid/
remote) but, on the three boards checked here, no dedicated salary field
and no consistently-present employment-type field (GlobalFoundries has a
tenant-specific `efcustomTextTimeType` custom field; Micron and Applied
Materials don't have anything equivalent) — so, matching
northrop_grumman.py's convention, `salary` is always None and `job_type`
uses `workLocationOption` rather than a real full/part-time field.
"""
import html
import re

import requests

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

PAGE_SIZE = 10
DEFAULT_MAX_RESULTS = 100  # safety cap on pagination + detail-page fetches


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _new_session(careers_page: str) -> tuple[requests.Session, str]:
    """Loads the careers page once to establish cookies + a CSRF token,
    exactly what a real page load does before its own JS calls the API."""
    session = requests.Session()
    session.headers.update({"User-Agent": _UA, "Referer": careers_page})
    resp = session.get(careers_page, timeout=20)
    resp.raise_for_status()
    match = re.search(r'name="_csrf" content="([^"]+)"', resp.text)
    if not match:
        raise RuntimeError(f"_eightfold: couldn't find CSRF token on {careers_page}")
    return session, match.group(1)


def _fetch_detail(session: requests.Session, csrf: str, api_base: str, domain: str,
                   position_id: int) -> dict:
    """Returns {"snippet": ..., "url": ..., "job_type": ...}; blank/None
    values on any failure so one bad detail page doesn't sink the search."""
    try:
        resp = session.get(
            f"{api_base}/position_details",
            params={"position_id": position_id, "domain": domain, "hl": "en"},
            headers={"x-csrf-token": csrf, "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {
            "snippet": _strip_html(data.get("jobDescription", ""))[:1000],
            "url": data.get("publicUrl"),
            "job_type": data.get("workLocationOption") or None,
        }
    except (requests.RequestException, ValueError):
        return {"snippet": "", "url": None, "job_type": None}


def _extract_job(session: requests.Session, csrf: str, api_base: str, domain: str,
                  position: dict, source: str, company_name: str, keyword: str,
                  careers_page: str) -> dict | None:
    position_id = position.get("id")
    if not position_id:
        return None

    detail = _fetch_detail(session, csrf, api_base, domain, position_id)
    locations = position.get("locations") or position.get("standardizedLocations") or []

    return {
        "source": source,
        "source_job_id": position.get("displayJobId") or str(position_id),
        "title": position.get("name", ""),
        "company": company_name,
        "location": "; ".join(locations) if locations else None,
        "salary": None,  # no salary field on any Eightfold tenant checked (see module docstring)
        "job_type": detail["job_type"],
        "url": detail["url"] or f"{careers_page}/job/{position_id}",
        "snippet": detail["snippet"],
        "search_keyword": keyword,
    }


def fetch_eightfold_jobs(careers_page: str, api_base: str, domain: str, source: str,
                          company_name: str, keyword: str, location: str = None,
                          max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
    """Fetch and page through a single company's Eightfold-hosted board.

    `careers_page` -- e.g. "https://careers.micron.com/careers" -- used both
    to mint the CSRF token/session and as the URL fallback if a detail fetch
    fails.
    `api_base` -- e.g. "https://careers.micron.com/api/pcsx".
    `domain` -- the Eightfold tenant key, e.g. "micron.com" (see module
    docstring: not always the company's plain domain -- GlobalFoundries
    needs the full "globalfoundries.com", not "gf.com").
    `location` IS honored -- Eightfold's search API takes a free-text
    location string, same as northrop_grumman.py.
    `radius_miles` is not accepted here -- no company checked exposes a
    radius parameter on this API.
    """
    session, csrf = _new_session(careers_page)

    all_results = []
    start = 0
    while start < max_results:
        resp = session.get(
            f"{api_base}/search",
            params={"domain": domain, "query": keyword, "location": location or "", "start": start},
            headers={"x-csrf-token": csrf, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        positions = data.get("positions", [])
        if not positions:
            break

        for position in positions:
            extracted = _extract_job(session, csrf, api_base, domain, position, source,
                                      company_name, keyword, careers_page)
            if extracted:
                all_results.append(extracted)

        if len(positions) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    return all_results
