"""ClearanceJobs.com — security-clearance-specific job board (aerospace/
defense employers requiring an active/eligible clearance).

The public search page (https://www.clearancejobs.com/jobs?keywords=...) is
served by a Vue SPA bundle, but it's server-side rendered (via Vike, the
Vite-based SSR framework formerly known as vite-plugin-ssr) — a plain
`requests.get` with a normal browser User-Agent returns full HTML with real
job listings already baked in. No bot-wall, no CAPTCHA, no login wall
(confirmed live 2026-08-26: a request with no User-Agent header gets a bare
403, but a normal browser UA gets a clean 200 with real data — that's
ordinary polite-identification, not evasion).

Better still: the SSR page embeds the *exact* JSON payload its own backend
returned, verbatim, inside a `<script id="vike_pageContext"
type="application/json">` tag. So instead of regex-scraping rendered markup
(the indeed.py/ziprecruiter.py/ornl.py pattern), this module pulls a clean,
fully structured JSON object straight out of that script tag with one
regex + json.loads. Same single HTTP GET either way — this is just a far
more reliable extraction path once you know the tag is there, and it means
no Playwright/browser automation is needed at all, unlike indeed.py.

That backend payload includes: job id, title, company (+ profile URL),
a per-location list with a workplace-arrangement tag ("On-Site/Office",
"Remote", "Hybrid", "On/Off-Site"), clearance level, polygraph requirement,
salary min/max (published on roughly 1 in 4 postings, the rest are None),
a preview/snippet of the description, and `meta.pagination`
(total/currentPage/nextPage/totalPages) for paging.

This was reached by first doing exactly what was asked: loading the search
page with Playwright and capturing all XHR/fetch network traffic. No
dedicated jobs-search JSON API call showed up there at all (the only
XHR/fetch hits were analytics/ads noise — Sentry, GA, HubSpot, Clarity,
DoubleClick, etc.) — the job data only ever appears already-embedded in the
SSR HTML, which is why this module fetches and parses that HTML directly
with `requests` instead of calling a separate endpoint.

*** IMPORTANT CAVEAT — robots.txt ***
https://www.clearancejobs.com/robots.txt has, under `User-agent: *` (i.e.
every crawler, not a named-bot-only rule):
    Disallow: /jobs?
which is exactly the search-results endpoint this module has to call with a
query string (`?keywords=...`). This is NOT a technical access-control —
the page returns a normal 200 with full data regardless, there's no
bot-wall or CAPTCHA enforcing it server-side — it's the site's stated
crawling policy, discovered only after building and testing this module (a
robots.txt check wasn't part of the original investigation steps). That's a
materially different situation from indeed.py/ziprecruiter.py: their
robots.txt files don't disallow their respective search paths for a generic
user agent, so this project hasn't previously had to weigh this. This
module is fully working and was smoke-tested live, but running it in any
automated or repeated way (e.g. wiring it into a scheduled sweep) conflicts
with ClearanceJobs' own explicit robots.txt directive for this exact path —
that's a judgment call for a human to make deliberately, not something to
route around silently by building it in as just another source. Flag this
before wiring it into main.py.

Location search: ClearanceJobs' search isn't geocoded/radius-based like
Indeed or USAJobs — it's facet-based. The only location filters available
are an exact "City, State" string facet (`city=`, matched verbatim against
ClearanceJobs' own city list) and a numeric per-state facet id (`loc=<id>`,
e.g. Washington is id 49 — would need its own 50-state id lookup table not
built here). `radius_miles` is accepted for interface parity with the other
search_* functions but has no effect server-side (confirmed live:
identical result counts with/without a `radius` param passed alongside
`city`) — same "accepted but unused" pattern as ornl.py/pnnl.py.
`location` is passed through the `city` facet on a best-effort exact-string
basis: if it doesn't match one of ClearanceJobs' own city facet values
verbatim, that filter silently returns 0 rows rather than falling back to
a wider search — pass `location=None` (or "", or "remote"/"united states")
to search nationwide instead of guessing.

Verified against live responses on 2026-08-26: Playwright network capture
confirmed no separate API call exists, then a plain `requests` smoke test
against real keywords ("physicist", "engineer") returned real job titles,
companies, clearance levels, and salaries — not empty or garbage results.
"""
import json
import re
import time

import requests

BASE_URL = "https://www.clearancejobs.com/jobs"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
PAGE_CONTEXT_RE = re.compile(
    r'<script id="vike_pageContext"[^>]*>(.*?)</script>', re.DOTALL
)
MAX_RESULTS = 200  # safety cap on pagination


def _format_salary(item: dict) -> str | None:
    lo, hi = item.get("salaryMin"), item.get("salaryMax")
    if not lo and not hi:
        return None
    if lo and hi:
        return f"${lo:,.0f} - ${hi:,.0f} a year"
    return f"${(lo or hi):,.0f} a year"


def _format_location(locations: list[dict]) -> str | None:
    names = [loc.get("location") for loc in (locations or []) if loc.get("location")]
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    return f"{names[0]} (+{len(names) - 1} more)"


def _to_city_state(location: str) -> str:
    """ClearanceJobs' `city` facet wants an exact "City, ST" string, not a
    full mailing address — same normalization usajobs.py applies, and for
    the same reason (a street-address-shaped value just won't match)."""
    parts = [p.strip() for p in location.split(",")]
    if len(parts) < 3:
        return location
    city, state_zip = parts[-2], parts[-1]
    state = re.sub(r"\s*\d{5}(-\d{4})?$", "", state_zip).strip()
    return f"{city}, {state}"


def _extract_job(item: dict, keyword: str) -> dict | None:
    job_id = item.get("id")
    if not job_id:
        return None

    locations = item.get("locations") or []
    workplace_type = locations[0].get("type") if locations else None

    clearance = item.get("clearance")
    polygraph = item.get("polygraph")
    tags = [
        t for t in (clearance, polygraph)
        if t and t not in ("Not Specified", "Unspecified")
    ]
    preview = item.get("previewText") or ""
    snippet = f"[{', '.join(tags)}] {preview}" if tags else preview

    return {
        "source": "clearancejobs",
        "source_job_id": str(job_id),
        "title": item.get("jobName", ""),
        "company": item.get("companyName"),
        "location": _format_location(locations),
        "salary": _format_salary(item),
        # ClearanceJobs doesn't publish an employee/contractor field on the
        # search-results payload — job_type is repurposed here as the
        # posting's workplace arrangement ("On-Site/Office", "Remote",
        # "Hybrid", "On/Off-Site"), the only categorical attribute actually
        # available per-listing. See module docstring.
        "job_type": workplace_type,
        "url": item.get("jobUrl"),
        "snippet": snippet,
        "search_keyword": keyword,
    }


def search_clearancejobs(keyword: str, location: str = None, radius_miles: int = None,
                          results_per_page: int = 50) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but has no effect — ClearanceJobs has no geocoded
    radius search, see module docstring. `location`, if given, is matched
    as an exact "City, State" facet value (best-effort; silently returns 0
    rows if it doesn't match ClearanceJobs' own city list verbatim)."""
    results = []
    page = 1
    params = {"keywords": keyword, "limit": min(results_per_page, 100)}
    if location and location.strip().lower() not in ("remote", "united states"):
        params["city"] = _to_city_state(location)

    while len(results) < MAX_RESULTS:
        params["page"] = page
        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=20)
        resp.raise_for_status()

        match = PAGE_CONTEXT_RE.search(resp.text)
        if not match:
            break
        payload = json.loads(match.group(1))
        search_data = payload.get("data", {}).get("data", {})
        items = search_data.get("data", [])
        if not items:
            break

        for item in items:
            job = _extract_job(item, keyword)
            if job:
                results.append(job)

        pagination = search_data.get("meta", {}).get("pagination", {})
        next_page = pagination.get("nextPage")
        if not next_page:
            break
        page = next_page
        time.sleep(0.5)  # be polite between pages

    return results[:MAX_RESULTS]


if __name__ == "__main__":
    for kw in ("physicist", "engineer"):
        jobs = search_clearancejobs(kw, results_per_page=20)
        print(f"\n=== {kw!r}: found {len(jobs)} jobs ===")
        for j in jobs[:5]:
            print(j["title"], "-", j["company"], "-", j["location"], "-", j["salary"], "-", j["job_type"])
            print("  ", j["url"])
            print("  ", j["snippet"][:150])
