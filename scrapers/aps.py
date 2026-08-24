"""American Physical Society (APS) physics job board — apsphysicsjobs.com.

APS's own careers.aps.org redirects to apsphysicsjobs.com, which is run by
IOP Publishing's "Physics World Jobs" partner network on the Madgex career-
site platform (Wiley/Madgex job-board-as-a-service, used by many professional
societies). Free to browse, no membership/login required for job seekers.

There is NO public JSON API — the Madgex-hosted asset bundle
(asset-relay.madgexjb.com/.../index-*.js) looked SPA-like, but network
inspection with Playwright (2026-08-24) showed the actual search-results page
is plain server-rendered HTML with no XHR/JSON calls behind it. So this
scraper does a plain `requests` GET + regex extraction against the search
results markup (`<li class="lister__item" id="item-<id>">...`), the same
tier as scrapers/indeed.py's HTML scraping but without needing browser
automation, since there's no bot-detection or JS-rendering requirement here
(verified with a bare curl — plain UA, no login wall, no CAPTCHA, 200 OK).

Known limitations, found while building this (2026-08-24):
- Location/radius search requires a `LocationId` resolved via the site's
  JS autocomplete widget (`radialtown` free text alone is silently ignored —
  confirmed it doesn't change result counts). No location/radius filtering
  is implemented here; `location`/`radius_miles` params are accepted for
  interface parity but unused, same as scrapers/pnnl.py.
- Only the first results page (10 jobs) is returned. No pagination
  mechanism could be found for this search template — no page-number query
  param (tried PageNumber/pn/p/page — several returned distinct-looking but
  empty pages), no "next" link/button in the rendered DOM (checked via
  Playwright after full JS execution), and no results-per-page override
  (tried ResultsPerPage/rpp/PerPage/pagesize — all no-ops). Given APS/Physics
  World Jobs is a small, low-volume board (~66 hits for "physicist"
  nationwide at last check), the top-10-by-relevance page is still useful
  signal for a daily sweep, just not exhaustive.
"""
import re

import requests

BASE_URL = "https://www.apsphysicsjobs.com/searchjobs/"
JOB_BASE_URL = "https://www.apsphysicsjobs.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_job(block: str, keyword: str) -> dict | None:
    m_id = re.search(r'id="item-(\d+)"', block)
    if not m_id:
        return None
    source_job_id = m_id.group(1)

    m_url = re.search(r'href="\s*([^"]*?/job/\d+/[^"]*?)\s*"\s*class="js-clickable-area-link"', block, re.S)
    m_title = re.search(r"<span>(.*?)</span></a></h3>", block, re.S)
    m_loc = re.search(r'lister__meta-item--location">(.*?)</li>', block, re.S)
    m_sal = re.search(r'lister__meta-item--salary">(.*?)</li>', block, re.S)
    m_co = re.search(r'lister__meta-item--recruiter">(.*?)</li>', block, re.S)
    m_snip = re.search(r'lister__description[^"]*">(.*?)</p>', block, re.S)

    url = m_url.group(1).strip() if m_url else None
    if url and url.startswith("/"):
        url = JOB_BASE_URL + url

    return {
        "source": "aps",
        "source_job_id": source_job_id,
        "title": _clean(m_title.group(1)) if m_title else "",
        "company": _clean(m_co.group(1)) if m_co else None,
        "location": _clean(m_loc.group(1)) if m_loc else None,
        "salary": _clean(m_sal.group(1)) if m_sal else None,
        "job_type": None,  # not exposed on the search-results card markup
        "url": url,
        "snippet": _clean(m_snip.group(1)) if m_snip else "",
        "search_keyword": keyword,
    }


def search_aps(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — see module docstring: the site's
    location filter needs a JS-resolved LocationId that plain requests can't
    obtain, so this always searches nationwide/unfiltered by geography."""
    params = {"Keywords": keyword}
    resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    html = resp.text

    blocks = re.split(r'<li class="lister__item', html)[1:]
    results = []
    for block in blocks:
        job = _extract_job(block, keyword)
        # Skip promoted "Employer profile" cards (e.g. APS advertising its own
        # employer page) — these aren't real job postings, just have a job-like
        # URL (/job/<id>/employer-profile/) and get mixed into CurrentPageJobIds.
        if job and job["title"] and job["url"] and not job["url"].rstrip("/").endswith("employer-profile"):
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_aps("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["company"], "-", j["location"], "-", j["salary"])
        print("  ", j["url"])
