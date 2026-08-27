"""Halliburton — careers.halliburton.com / jobs.halliburton.com.

careers.halliburton.com redirects to jobs.halliburton.com, which — despite
that page also linking out to a `career4.successfactors.com/career?...`
login/registration URL (SuccessFactors is only used there for the candidate
*account* system, per the site's own "Login" / "Register" links) — actually
serves its job *search* itself, running on SAP SuccessFactors Recruiting
Marketing (formerly "Jobs2Web" — its JS assets are literally under
`/platform/js/j2w/`), the exact same platform this project already scraped
for Oak Ridge National Lab (scrapers/ornl.py). Confirmed live 2026-08-26 by
diffing the HTML: `jobs.halliburton.com/search/?q=<keyword>` returns the
identical `<tr class="data-row">` / `<span class="jobTitle hidden-phone">`
markup as ORNL's Jobs2Web tenant, just under Halliburton's own branding — no
JS execution, login, or bot-detection wall required, a bare `requests.get`
returns the same HTML a browser would.

Confirmed live: "engineer" returned a full first page of 25 real postings
(Engineering Manager - Oslo, etc.); pagination via `startrow` (25 results
per page) matches ORNL's tenant exactly.

Search results carry only title/location/date — no salary, job type, or
description snippet. Those exist only on each job's own detail page
(`/job/<slug>/<req-id>/`), inside a nested `<span class="jobdescription">`
(note: this tenant's detail markup has a slightly different attribute order
around the outer `itemprop="description"` element than ORNL's — confirmed
live — so the snippet extraction here matches on the inner `<span
class="jobdescription">` directly rather than reusing ORNL's exact regex).
job_type and salary are simply never published on Halliburton postings,
even on the detail page — left as None, not a parsing gap, same as ORNL.

There's no location/radius search — like ORNL, this is a single employer's
career site, not a general job board with geographic search — so
`location`/`radius_miles` are accepted for interface parity only.
"""
import html
import re
import time

import requests

BASE_URL = "https://jobs.halliburton.com"
SEARCH_URL = f"{BASE_URL}/search/"
COMPANY = "Halliburton"
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
DESCRIPTION_START_RE = re.compile(r'<span class="jobdescription">')


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _job_id_from_href(href: str) -> str | None:
    # /job/Oslo-Engineering-Manager-03-0167/1399694700/
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
    # Deeply nested tags with no simple closing marker to regex against
    # reliably (same situation as ornl.py) — grab a generous raw chunk after
    # the opening tag and strip/truncate.
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
            "source": "halliburton",
            "source_job_id": job_id,
            "title": title,
            "company": COMPANY,
            "location": location,
            "salary": None,  # not published on Halliburton postings, listing or detail page
            "job_type": None,  # same — not published
            "url": BASE_URL + href,
            "snippet": "",  # filled in by search_halliburton after pagination
            "search_keyword": keyword,
        })
    return results


def search_halliburton(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Halliburton's career site isn't a
    general job board with geographic search, it's a single employer's
    postings (same as ornl.py)."""
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
    jobs = search_halliburton("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
