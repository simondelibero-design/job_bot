"""Princeton Plasma Physics Laboratory (PPPL) — pppl.gov / pppl-princeton.icims.com.

PPPL is a DOE national lab, but unlike most contractor-run DOE labs (Battelle
at PNNL, UT-Battelle at ORNL, etc.) it's operated directly by Princeton
University — so, like SLAC (Stanford-operated), it doesn't run a typical
DOE-contractor ATS. Its "Work With Us" page (pppl.gov/apply-pppl-position,
which 403s to a plain fetch — Princeton's Drupal front end blocks non-browser
UAs) embeds an iCIMS-hosted career portal at `pppl-princeton.icims.com`, the
same ATS platform this project already has an application-flow handler for
(ats/icims.py, built against a different tenant — General Dynamics Mission
Systems).

No JSON API was found — confirmed by inspecting the live HTML (2026-08-24)
while browsing the search page — but the search-results page is fully
server-rendered (`GET /jobs/search?in_iframe=1&searchKeyword=<kw>`), no JS
execution or login required, same tier as ORNL's SuccessFactors site
(scrapers/ornl.py). Search results list only title + requisition ID/URL;
each job's own detail page additionally carries a
`<script type="application/ld+json">` schema.org JobPosting block with
location, employment type, and the full description — much cleaner to parse
than regex-scraping visible HTML, so this module reads that JSON-LD directly
off each detail page instead of following ORNL's raw-HTML-chunk approach.

Salary isn't a first-class JSON-LD field here — Princeton publishes it as
the last line of the HTML description ("...<h2>Salary Range</h2>$X to $Y"),
so it's pulled out with a small regex over the description text. Not every
posting is guaranteed to include one.

PPPL is a small lab: at verification time it had 9 total open positions
(https://pppl-princeton.icims.com/jobs/search?in_iframe=1, unfiltered), so
this module has never observed a paginated result set live — the iCIMS
paginator markup is present in the page but empty below the single-page
threshold. If PPPL's headcount ever grows past a page's worth of results,
pagination will need to be added and verified against real multi-page
output, unlike ORNL's pagination (scrapers/ornl.py) which was confirmed
against 111 real results across multiple pages.

Like PNNL/ORNL, there's no location/radius search — single employer's
career site, not a general job board — so `location`/`radius_miles` are
accepted for interface parity only.

Verified against live responses on 2026-08-24.
"""
import html
import json
import re

import requests

BASE_URL = "https://pppl-princeton.icims.com"
SEARCH_URL = f"{BASE_URL}/jobs/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

ANCHOR_RE = re.compile(r'<a href="([^"]+)" class="iCIMS_Anchor"')
JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(\{.*?\})</script>', re.DOTALL)
SALARY_RE = re.compile(r"Salary Range</h2>\$([\d,]+)(?:\s*to\s*\$([\d,]+))?", re.IGNORECASE)
JOB_ID_RE = re.compile(r"/jobs/(\d+)/")


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _job_id_from_url(url: str) -> str | None:
    # https://pppl-princeton.icims.com/jobs/22032/cooling-water%2c-liquids-and-gas-engineer/job
    match = JOB_ID_RE.search(url or "")
    return match.group(1) if match else None


def _format_location(job_location: list) -> str | None:
    if not job_location:
        return None
    addr = job_location[0].get("address", {})
    city, state = addr.get("addressLocality"), addr.get("addressRegion")
    if city and state:
        return f"{city}, {state}"
    return city or state


def _format_job_type(employment_type: str) -> str | None:
    if not employment_type:
        return None
    return employment_type.replace("_", "-").title()  # "FULL_TIME" -> "Full-Time"


def _extract_salary(description: str) -> str | None:
    match = SALARY_RE.search(description or "")
    if not match:
        return None
    lo, hi = match.group(1), match.group(2)
    return f"${lo} - ${hi}" if hi else f"${lo}"


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
    job_id = _job_id_from_url(job_url)
    if not job_id:
        return None

    description = data.get("description", "")
    return {
        "source": "pppl",
        "source_job_id": job_id,
        "title": data.get("title", ""),
        "company": "Princeton Plasma Physics Laboratory",
        "location": _format_location(data.get("jobLocation")),
        "salary": _extract_salary(description),
        "job_type": _format_job_type(data.get("employmentType")),
        "url": job_url,
        "snippet": html.unescape(_strip_html(description))[:1000],
        "search_keyword": keyword,
    }


def search_pppl(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — PPPL's career site isn't a general
    job board with geographic search, it's a single employer's postings."""
    resp = requests.get(
        SEARCH_URL,
        headers=HEADERS,
        params={"in_iframe": 1, "searchKeyword": keyword},
        timeout=20,
    )
    resp.raise_for_status()

    urls = []
    for block in resp.text.split('<li class="iCIMS_JobCardItem">')[1:]:
        anchor = ANCHOR_RE.search(block)
        if anchor:
            urls.append(html.unescape(anchor.group(1)))

    results = []
    for url in urls:
        job = _fetch_detail(url, keyword)
        if job:
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_pppl("scientist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["salary"], "-", j["job_type"])
        print("  ", j["url"])
