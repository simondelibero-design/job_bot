"""Iridium Communications — iridium.com/company/careers, actual board at
careers-iridium.icims.com.

iridium.com/company/careers is a marketing landing page; the actual job
board it links to is an **iCIMS** tenant, `careers-iridium.icims.com` (found
by grepping the careers page HTML for `icims.com`, then confirmed live with
curl) — same ATS platform this project already knows from scrapers/pppl.py
and ats/icims.py (built against different tenants: Princeton and General
Dynamics Mission Systems, respectively).

Same discovery approach as pppl.py: no JSON API, but the search page is
fully server-rendered, no JS execution or login required:

    GET https://careers-iridium.icims.com/jobs/search?in_iframe=1&searchKeyword=<kw>&pr=<page>

Confirmed live 2026-08-26: `searchKeyword=engineer` returned real postings
(e.g. "Senior Deputy Program Manager, Engineering", multi-site: Reston VA /
Chandler AZ / Grand Forks AFB ND / Huntsville AL) across 2 pages (25 total).
Unlike PPPL (small enough to never paginate), this tenant needed real
pagination verification: `pr=0` is page 1 (20 results), `pr=1` is page 2 (5
results, zero overlap with page 1, confirmed by diffing job IDs) — the
`iCIMS_Paging` markup on page 1 reports "of 2" as the total page count, used
here to drive the pagination loop. `pr` is a 0-based page index, not a
result offset (i.e. NOT `pr=20` for page 2 — iCIMS pages, unlike Workday's
offset-based paging in boeing.py/draper.py).

Each job's own detail page carries a `<script type="application/ld+json">`
schema.org JobPosting block (location, employment type, full description) —
read directly instead of regex-scraping visible HTML, same as pppl.py.
No structured salary field exists in the JSON-LD or anywhere else observed
on this tenant's postings, so `salary` is always None (unlike PPPL, whose
descriptions sometimes embed a "Salary Range" line — Iridium's did not on
any posting checked).
"""
import html
import json
import re

import requests

BASE_URL = "https://careers-iridium.icims.com"
SEARCH_URL = f"{BASE_URL}/jobs/search"
COMPANY = "Iridium Satellite, LLC"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

ANCHOR_RE = re.compile(r'<a href="([^"]+)" class="iCIMS_Anchor"')
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(\{.*?\})</script>', re.DOTALL)
JOB_ID_RE = re.compile(r"/jobs/(\d+)/")
TOTAL_PAGES_RE = re.compile(r"of\s*(\d+)\s*\n?<")

MAX_PAGES = 10  # safety cap on pagination


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _job_id_from_url(url: str) -> str | None:
    match = JOB_ID_RE.search(url or "")
    return match.group(1) if match else None


def _format_location(job_location: list) -> str | None:
    if not job_location:
        return None
    locations = []
    for loc in job_location:
        addr = loc.get("address", {})
        city, state = addr.get("addressLocality"), addr.get("addressRegion")
        if city and state and city != "UNAVAILABLE":
            locations.append(f"{city}, {state}")
        elif city and city != "UNAVAILABLE":
            locations.append(city)
    return "; ".join(locations) if locations else None


def _format_job_type(employment_type: str) -> str | None:
    if not employment_type:
        return None
    return employment_type.replace("_", "-").title()  # "FULL_TIME" -> "Full-Time"


def _fetch_detail(url: str, keyword: str) -> dict | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    match = JSON_LD_RE.search(resp.text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    job_url = data.get("url") or url
    job_id = _job_id_from_url(job_url) or _job_id_from_url(url)
    if not job_id:
        return None

    description = data.get("description", "")
    return {
        "source": "iridium",
        "source_job_id": job_id,
        "title": data.get("title", ""),
        "company": COMPANY,
        "location": _format_location(data.get("jobLocation")),
        "salary": None,  # no salary field observed anywhere on this tenant
        "job_type": _format_job_type(data.get("employmentType")),
        "url": job_url,
        "snippet": html.unescape(_strip_html(description))[:1000],
        "search_keyword": keyword,
    }


def _fetch_page_urls(keyword: str, page: int) -> tuple[list[str], int]:
    """Returns (job detail URLs on this page, total page count)."""
    resp = requests.get(
        SEARCH_URL,
        headers=HEADERS,
        params={"in_iframe": 1, "searchKeyword": keyword, "pr": page},
        timeout=20,
    )
    resp.raise_for_status()
    text = resp.text

    urls = []
    for block in text.split('<li class="iCIMS_JobCardItem">')[1:]:
        anchor = ANCHOR_RE.search(block)
        if anchor:
            urls.append(html.unescape(anchor.group(1)))

    total_pages_match = TOTAL_PAGES_RE.search(text)
    total_pages = int(total_pages_match.group(1)) if total_pages_match else 1
    return urls, total_pages


def search_iridium(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Iridium's iCIMS tenant is a
    single employer's postings, not a general geographic job board."""
    all_urls = []
    page = 0
    total_pages = 1
    while page < total_pages and page < MAX_PAGES:
        urls, total_pages = _fetch_page_urls(keyword, page)
        if not urls:
            break
        all_urls.extend(urls)
        page += 1

    results = []
    for url in all_urls:
        job = _fetch_detail(url, keyword)
        if job:
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_iridium("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
