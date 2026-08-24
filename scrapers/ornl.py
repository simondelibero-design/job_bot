"""Oak Ridge National Laboratory (ORNL) — jobs.ornl.gov.

ORNL is a DOE national lab, contractor-operated (UT-Battelle), so USAJobs.gov
doesn't cover its postings the way it covers direct federal positions — this
needs its own source, same situation as PNNL (see scrapers/pnnl.py).

Unlike PNNL, ORNL's career site is *not* backed by a JSON API. It runs on
SAP SuccessFactors Recruiting Marketing (formerly "Jobs2Web" — the JS assets
are literally named `j2w.*.js`), which server-renders full HTML search
results. Confirmed by inspecting live network traffic while browsing
jobs.ornl.gov/search/ (2026-08-24): the only XHR/fetch call is a POST to
`/services/jobs/options/facetValues/` for the sidebar facet counts — the
actual job listings arrive already rendered in the initial page HTML from a
plain `GET /search/?q=<keyword>`. No JS execution, login, or bot-detection
wall required — a bare `requests.get` returns the same HTML a browser would.

This is good news structurally but means no bs4/lxml-quality DOM to work
with (this project has no HTML-parsing dependency beyond stdlib), so listing
rows are pulled out with regex, same approach as `_strip_html` in pnnl.py.

Search results carry only title/location/date — no salary, job type, or
description snippet. Those exist only on each job's own detail page
(`/job/<slug>/<req-id>/`), inside `<span itemprop="description">`. This
module fetches each result's detail page for the snippet (job_type and
salary are simply never published on ORNL postings, even on the detail
page — left as None, not a parsing gap).

Pagination is `startrow` (25 results per page), found via the numbered
pagination links on a multi-page search (e.g. `?q=engineer`, 111 results).

There's no location/radius search — like PNNL, this is a single employer's
career site, not a general job board with geographic search — so
`location`/`radius_miles` are accepted for interface parity only.

Verified against live responses on 2026-08-24.
"""
import html
import re
import time

import requests

BASE_URL = "https://jobs.ornl.gov"
SEARCH_URL = f"{BASE_URL}/search/"
PAGE_SIZE = 25
MAX_RESULTS = 100  # safety cap on pagination + detail-page fetches

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

ROW_RE = re.compile(
    r'<span class="jobTitle hidden-phone">\s*<a href="([^"]+)" class="jobTitle-link">([^<]+)</a>'
)
LOCATION_RE = re.compile(
    r'class="colLocation hidden-phone".*?<span class="jobLocation">\s*([^<]+?)\s*</span>',
    re.DOTALL,
)
DESCRIPTION_START_RE = re.compile(r'<span itemprop="description" class="jobdescription">')


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _job_id_from_href(href: str) -> str | None:
    # /job/Oak-Ridge-Associate-Nuclear-Engineer-TN-37830/1421759900/
    parts = [p for p in href.split("/") if p]
    return parts[-1] if parts and parts[-1].isdigit() else None


def _fetch_snippet(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return ""
    match = DESCRIPTION_START_RE.search(resp.text)
    if not match:
        return ""
    # The description span has deeply nested <span>/<p>/<ul> tags with no
    # simple closing marker to regex against reliably, so just grab a
    # generous raw chunk after the opening tag and strip/truncate — we only
    # need the first ~1000 chars of plain text anyway.
    raw_chunk = resp.text[match.end():match.end() + 6000]
    return html.unescape(_strip_html(raw_chunk))[:1000]


def _parse_page(page_html: str, keyword: str) -> list[dict]:
    results = []
    rows = page_html.split('<tr class="data-row">')[1:]
    for row in rows:
        title_match = ROW_RE.search(row)
        if not title_match:
            continue
        href = html.unescape(title_match.group(1))
        title = html.unescape(title_match.group(2).strip())
        job_id = _job_id_from_href(href)
        if not job_id:
            continue
        location_match = LOCATION_RE.search(row)
        location = html.unescape(location_match.group(1).strip()) if location_match else None

        results.append({
            "source": "ornl",
            "source_job_id": job_id,
            "title": title,
            "company": "Oak Ridge National Laboratory",
            "location": location,
            "salary": None,  # not published on ORNL postings, listing or detail page
            "job_type": None,  # same — not published
            "url": BASE_URL + href,
            "snippet": "",  # filled in by search_ornl after pagination
            "search_keyword": keyword,
        })
    return results


def search_ornl(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — ORNL's career site isn't a general
    job board with geographic search, it's a single employer's postings."""
    all_results = []
    startrow = 0
    while startrow < MAX_RESULTS:
        resp = requests.get(
            SEARCH_URL,
            headers=HEADERS,
            params={"q": keyword, "startrow": startrow} if startrow else {"q": keyword},
            timeout=20,
        )
        resp.raise_for_status()
        page_results = _parse_page(resp.text, keyword)
        if not page_results:
            break
        all_results.extend(page_results)
        if len(page_results) < PAGE_SIZE:
            break
        startrow += PAGE_SIZE
        time.sleep(0.5)  # be polite between pages

    for job in all_results:
        job["snippet"] = _fetch_snippet(job["url"])
        time.sleep(0.2)  # be polite between detail-page fetches

    return all_results


if __name__ == "__main__":
    jobs = search_ornl("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
