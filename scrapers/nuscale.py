"""NuScale Power (small modular nuclear reactors) —
nuscalepower.com/about/careers -> jobs.jobvite.com/nuscale-power.

nuscalepower.com/about/careers links directly to
jobs.jobvite.com/nuscale-power — NuScale runs on **Jobvite**, an ATS not
previously used by any scraper in this codebase. Confirmed live 2026-08-26
by driving the real site once with Playwright (this project's own script,
not the shared browser tool) to check whether the job list needed JS: it
didn't — a bare `requests.get` on the same URL returns byte-for-byte the
same server-rendered job listing (33 postings across 11 categories,
matching what a full browser render shows), no XHR/JSON API involved at
all. So this is a plain HTML scrape, same tier as scrapers/ornl.py, not a
JS SPA needing a browser.

The page has no search form/query param in its static HTML — a guessed
`?q=engineer` param returned zero results rather than filtering (silently
broke the render), so — like Greenhouse/Lever/Ashby's public APIs — this
returns the board's full current listing and filters client-side against
the job title. There's no pagination either (all 33 postings render on
one page, grouped under `<h3 class="h2">` category headers like
"Engineering", "Plant Services").

Each job's own detail page
(`jobs.jobvite.com/nuscale-power/job/<id>`) has the full description in a
`class="jv-job-detail-description"` div, fetched here for the snippet, and
a `class="jv-job-detail-meta"` paragraph with "<category><separator><location>"
text, used here only for location — category isn't a real employment-type
field, so `job_type` is left as None rather than mislabeling it. No
structured salary field exists anywhere in this pipeline (postings seen
don't publish pay ranges), so `salary` is always None.
"""
import html
import re

import requests

BASE_URL = "https://jobs.jobvite.com"
BOARD_PATH = "/nuscale-power"
LIST_URL = f"{BASE_URL}{BOARD_PATH}"
COMPANY = "NuScale Power"
MAX_RESULTS = 100  # safety cap on detail-page fetches

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

JOB_ROW_RE = re.compile(
    r'<a href="(/nuscale-power/job/[a-zA-Z0-9]+)">([^<]+)</a>\s*</td>\s*'
    r'<td class="jv-job-list-location">\s*(.*?)\s*</td>',
    re.S,
)
META_RE = re.compile(
    r'class="jv-job-detail-meta">\s*(.*?)<span class=\'jv-inline-separator\'></span>\s*(.*?)\s*</p>',
    re.S,
)
DESC_RE = re.compile(r'class="jv-job-detail-description"[^>]*>(.*?)</div>\s*</div>', re.S)


def _strip_html(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    # Jobvite's location markup has real newlines/indentation between
    # multiple location entries (e.g. "Remote" + a specific city both
    # listed for one posting) — collapse all whitespace to single spaces
    # so the field reads as one clean string rather than embedded newlines.
    return html.unescape(re.sub(r"\s+", " ", no_tags)).strip()


def _fetch_detail(url: str) -> dict:
    """Returns {"location": ..., "snippet": ...}; blank values on any
    failure so one bad detail page doesn't sink the search."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return {"location": None, "snippet": ""}

    location = None
    meta_match = META_RE.search(resp.text)
    if meta_match:
        location = _strip_html(meta_match.group(2)) or None

    snippet = ""
    desc_match = DESC_RE.search(resp.text)
    if desc_match:
        snippet = _strip_html(desc_match.group(1))[:1000]

    return {"location": location, "snippet": snippet}


def _parse_listing(page_html: str, keyword: str) -> list[dict]:
    keyword_lower = keyword.lower()
    results = []
    for href, title, list_location in JOB_ROW_RE.findall(page_html):
        title = html.unescape(title.strip())
        if keyword_lower not in title.lower():
            continue
        job_id = href.rsplit("/", 1)[-1]
        results.append({
            "source": "nuscale",
            "source_job_id": job_id,
            "title": title,
            "company": COMPANY,
            "location": html.unescape(_strip_html(list_location)) or None,
            "salary": None,  # not published anywhere in this pipeline
            "job_type": None,  # no real employment-type field, only a department category
            "url": BASE_URL + href,
            "snippet": "",  # filled in by search_nuscale after listing parse
            "search_keyword": keyword,
        })
    return results


def search_nuscale(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location`, if given, is a client-side
    case-insensitive substring match against the listing's location text —
    Jobvite's public board here has no server-side geographic search."""
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    results = _parse_listing(resp.text, keyword)

    if location:
        location_lower = location.lower()
        results = [r for r in results if r["location"] and location_lower in r["location"].lower()]

    results = results[:MAX_RESULTS]
    for job in results:
        detail = _fetch_detail(job["url"])
        job["snippet"] = detail["snippet"]
        if detail["location"]:
            job["location"] = detail["location"]

    return results


if __name__ == "__main__":
    jobs = search_nuscale("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
