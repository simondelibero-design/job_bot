"""QuantumScape (solid-state lithium-metal battery technology) —
quantumscape.com/careers -> careers.quantumscape.com.

quantumscape.com/careers links to a separate career site,
careers.quantumscape.com, which runs on the same SAP SuccessFactors
Recruiting Marketing platform ("Jobs2Web"/CSB) that scrapers/ornl.py
already handles for Oak Ridge National Laboratory — confirmed by matching
HTML structure byte-for-byte: same `<tr class="data-row">` result rows,
same `jobTitle`/`jobLocation` span classes, same `/job/<slug>/<req-id>/`
detail-page URL scheme, and an `itemprop="description"` span on the detail
page (though with different surrounding attributes than ORNL's — see the
detail-page regex below), and QuantumScape's own asset paths still
reference `j2w` (`options-search.min.js`
lives under `/platform/js/j2w/min/`). Confirmed live 2026-08-26: a plain
`GET https://careers.quantumscape.com/search/?q=<keyword>` returns fully
server-rendered HTML with no JS execution, login, or bot-detection wall
required — "engineer" returned 23 real matches (Senior Infrastructure
Engineer, CA, etc.) on the first page alone.

Search results carry only title/location/date — no salary, job type, or
description snippet. Those exist only on each job's own detail page, inside
`<span itemprop="description">`. This module fetches each result's detail
page for the snippet (job_type and salary are simply never published on
QuantumScape postings, even on the detail page — left as None, not a
parsing gap, same as ORNL).

Pagination is `startrow` (matching ORNL's tenant); no location/radius
search exists — single employer's career site, not a general job board —
so `location`/`radius_miles` are accepted for interface parity only.
"""
import html
import re
import time

import requests

BASE_URL = "https://careers.quantumscape.com"
SEARCH_URL = f"{BASE_URL}/search/"
COMPANY = "QuantumScape"
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
# Some QuantumScape listings post to multiple locations, which renders as
# `<span class="jobLocation">CA, US, 95110<small class="nobr">+1 more...
# </small></span>` — a nested tag inside the span that ORNL's simpler
# `[^<]+?` capture (this regex's original ancestor in scrapers/ornl.py)
# can't handle, so this captures everything up to `</td>` and strips tags
# rather than assuming plain text with no nested markup.
LOCATION_RE = re.compile(
    r'class="colLocation hidden-phone".*?<span class="jobLocation">(.*?)</td>',
    re.DOTALL,
)
_MORE_LOCATIONS_RE = re.compile(r"\+\d+ more\S*", re.IGNORECASE)
# QuantumScape's detail-page markup differs slightly from ORNL's here — the
# span carries extra attributes between itemprop and class
# (`itemprop="description" data-careersite-propertyid="description"
# class="rtltextaligneligible"`) rather than ORNL's exact
# `itemprop="description" class="jobdescription"`, so this matches on the
# itemprop alone and lets the closing `>` fall wherever it does.
DESCRIPTION_START_RE = re.compile(r'itemprop="description"[^>]*>')


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _job_id_from_href(href: str) -> str | None:
    # /job/Senior-Infrastructure-Engineer-CA-95110/1396514400/
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
        location = None
        if location_match:
            location = _strip_html(location_match.group(1))
            location = _MORE_LOCATIONS_RE.sub("", location).strip()
            location = html.unescape(location) or None

        results.append({
            "source": "quantumscape",
            "source_job_id": job_id,
            "title": title,
            "company": COMPANY,
            "location": location,
            "salary": None,  # not published on QuantumScape postings, listing or detail page
            "job_type": None,  # same — not published
            "url": BASE_URL + href,
            "snippet": "",  # filled in by search_quantumscape after pagination
            "search_keyword": keyword,
        })
    return results


def search_quantumscape(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — QuantumScape's career site isn't
    a general job board with geographic search, it's a single employer's
    postings."""
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
    jobs = search_quantumscape("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
