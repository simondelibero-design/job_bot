"""Thomas Jefferson National Accelerator Facility (Jefferson Lab / TJNAF) —
jobs.jlab.org.

Jefferson Lab is a DOE Office of Science national lab, contractor-operated
(Jefferson Science Associates, LLC), so USAJobs.gov doesn't cover its
postings the way it covers direct federal positions — this needs its own
source, same situation as PNNL/ORNL. Verified live (2026-08-24), not
assumed: jlab.org/careers points at a separate front end, jobs.jlab.org,
which — unlike PNNL — is *not* backed by a JSON API. It runs on SAP
SuccessFactors Recruiting Marketing (formerly "Jobs2Web" — the JS assets are
literally named `j2w.*.js`), the exact same platform ORNL runs (see
scrapers/ornl.py). This module is structurally that one, retargeted:
`GET /search/?q=<keyword>` on jobs.jlab.org returns the full result table
server-rendered in the initial HTML — no JS execution, login, or
bot-detection wall required, confirmed with a bare `requests.get`.

Two differences from ORNL's version worth noting for future maintainers:

1. Jefferson Lab's listing table has no location column at all — its second
   column is "Work Arrangement Type" (e.g. "On-Site - No remote work"),
   which this module captures directly off the listing page as `job_type`
   (ORNL never publishes this field; Jefferson Lab does, right there in the
   table, no detail-page fetch needed).
2. Location isn't in the listing HTML either — it's only on each posting's
   detail page, inside a schema.org JobPosting block's `jobLocation` (city/
   region as separate `<meta>` tags, not one string). Fetching the detail
   page is already required for the description snippet, so location is
   read from the same request. Note Jefferson Lab's own data truncates the
   state name in that field (observed live: "Virg" for Virginia on every
   Newport News posting checked) — reproduced as-is rather than "fixed",
   since guessing a full state name back out of a truncated abbreviation
   risks being wrong for a state this module hasn't seen truncated yet.

Jefferson Lab is a small tenant — a "no keyword" search returned only 21
total open postings tenant-wide (verified live), so pagination rarely
matters here, but `startrow` paging (25/page, identical mechanism to ORNL)
is still implemented for correctness. Salary and structured employment type
(full-time/part-time) are never published on Jefferson Lab postings, listing
or detail page — left as None, not a parsing gap, same honesty convention as
ORNL.

There's no location/radius search — like ORNL, this is a single employer's
career site, not a general job board with geographic search — so
`location`/`radius_miles` are accepted for interface parity only.

Verified against live responses on 2026-08-24.
"""
import html
import re
import time

import requests

BASE_URL = "https://jobs.jlab.org"
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
FACILITY_RE = re.compile(
    r'class="colFacility hidden-phone"[^>]*>\s*<span class="jobFacility">\s*([^<]+?)\s*</span>',
    re.DOTALL,
)
DESCRIPTION_START_RE = re.compile(r'itemprop="description"[^>]*>')
LOCALITY_RE = re.compile(r'itemprop="addressLocality" content="([^"]*)"')
REGION_RE = re.compile(r'itemprop="addressRegion" content="([^"]*)"')


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _job_id_from_href(href: str) -> str | None:
    # /job/Newport-News-Lead-Mechanical-Engineer-EIC-Cryogenics-Virg-23606/1394524900/
    parts = [p for p in href.split("/") if p]
    return parts[-1] if parts and parts[-1].isdigit() else None


def _fetch_detail(url: str) -> dict:
    """Returns {"snippet": ..., "location": ...}; blank values on any
    failure so a single bad detail page doesn't sink the whole search."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return {"snippet": "", "location": None}

    text = resp.text
    locality_match = LOCALITY_RE.search(text)
    region_match = REGION_RE.search(text)
    locality = html.unescape(locality_match.group(1)) if locality_match else ""
    region = html.unescape(region_match.group(1)) if region_match else ""
    location = ", ".join(p for p in (locality, region) if p) or None

    snippet = ""
    desc_match = DESCRIPTION_START_RE.search(text)
    if desc_match:
        # No simple closing marker to regex against reliably (deeply nested
        # spans/p/ul), so grab a generous raw chunk after the opening tag
        # and strip/truncate — same approach as ornl.py's `_fetch_snippet`.
        raw_chunk = text[desc_match.end():desc_match.end() + 6000]
        snippet = html.unescape(_strip_html(raw_chunk))[:1000]

    return {"snippet": snippet, "location": location}


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
        facility_match = FACILITY_RE.search(row)
        job_type = html.unescape(facility_match.group(1).strip()) if facility_match else None

        results.append({
            "source": "jlab",
            "source_job_id": job_id,
            "title": title,
            "company": "Thomas Jefferson National Accelerator Facility",
            "location": None,  # filled in by search_jlab from the detail page
            "salary": None,  # not published on Jefferson Lab postings, listing or detail page
            "job_type": job_type,  # "Work Arrangement Type" column, e.g. "On-Site - No remote work"
            "url": BASE_URL + href,
            "snippet": "",  # filled in by search_jlab from the detail page
            "search_keyword": keyword,
        })
    return results


def search_jlab(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Jefferson Lab's career site isn't
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
        detail = _fetch_detail(job["url"])
        job["snippet"] = detail["snippet"]
        job["location"] = detail["location"]
        time.sleep(0.2)  # be polite between detail-page fetches

    return all_results


if __name__ == "__main__":
    jobs = search_jlab("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["job_type"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
