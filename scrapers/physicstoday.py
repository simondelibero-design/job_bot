"""Physics Today Jobs (AIP — American Institute of Physics) — jobs.physicstoday.org.

Same Madgex job-board-as-a-service platform as scrapers/aps.py
(apsphysicsjobs.com) — confirmed independently (2026-08-26) rather than
assumed from the family resemblance: `curl` with a plain desktop UA returns
200 OK, plain server-rendered HTML, no login wall, no CAPTCHA, and the same
`<li class="lister__item" id="item-<id>">...` results markup with a
`js-clickable-area-link` job-title anchor and `lister__meta-item--*` metadata
`<li>`s. So this scraper reuses aps.py's plain `requests` + regex approach
unchanged — no browser automation needed here either.

Differences found from aps.py's site while verifying (Madgex tenants vary):
- Pagination DOES work here (unlike apsphysicsjobs.com, which has none for
  this template). Extra pages are at `/jobs/<n>/?Keywords=<kw>` (page 1 is
  the bare search URL), 20 jobs/page. Confirmed against `Keywords=physics`
  (1852 hits) which produced `/jobs/2/`, `/jobs/3/`, ... links; against
  `Keywords=physicist` (only 4 hits, one page) requesting `/jobs/2/`
  explicitly 301-redirects back to `/jobs/?keywords=physicist` — i.e. asking
  for a page past the end redirects to page 1 rather than erroring. This
  scraper follows that (requests follows redirects by default) and detects
  it via `resp.history` to stop paginating instead of silently re-appending
  page-1's results a second time.
- A keyword matching zero jobs returns HTTP 404 (still with a normal HTML
  body — its embedded analytics blob shows `returned-results: 0`), not a
  200 with an empty list. Handled as "no results" rather than an error.
- Same promoted "Employer profile" cards to skip as aps.py
  (`/job/<id>/employer-profile/` URLs) — did not actually show up in
  Physics Today's own result pages during testing, but the filter is kept
  for safety since it's cheap and matches the shared platform's behavior
  (confirmed present on the physicsworldjobs.com sibling scraper's results).
- No location/radius search implemented, same reasoning as aps.py: the
  search form only exposes a free-text `Keywords` field server-side; the
  location facets on the page are pre-computed browse-by-location links
  (`/jobs/california/?keywords=...`), not a radius search you can drive with
  a plain query param. `location`/`radius_miles` are accepted for interface
  parity but unused.

Verified live 2026-08-26 with `Keywords=physicist` (4 hits) and
`Keywords=quantum` (18 hits) — both returned real, sane job data.
"""
import re
import time

import requests

BASE_URL = "https://jobs.physicstoday.org/jobs/"
JOB_BASE_URL = "https://jobs.physicstoday.org"
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
        "source": "physicstoday",
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


def _parse_page(html: str, keyword: str) -> list[dict]:
    blocks = re.split(r'<li class="lister__item', html)[1:]
    results = []
    for block in blocks:
        job = _extract_job(block, keyword)
        # Skip promoted "Employer profile" cards — see module docstring.
        if job and job["title"] and job["url"] and not job["url"].rstrip("/").endswith("employer-profile"):
            results.append(job)
    return results


def search_physicstoday(keyword: str, location: str = None, radius_miles: int = None,
                         max_pages: int = 3) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — see module docstring."""
    params = {"Keywords": keyword}
    results = []
    seen_ids = set()

    for page_num in range(1, max_pages + 1):
        url = BASE_URL if page_num == 1 else f"{BASE_URL}{page_num}/"
        resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
        # Madgex returns HTTP 404 (with a normal HTML body, "returned-results:
        # 0" in its embedded analytics data) for a keyword that matches zero
        # jobs — that's a legitimate empty result, not an error, so don't
        # raise_for_status() on it. Only raise on other error statuses.
        if resp.status_code == 404:
            break
        resp.raise_for_status()

        # Requesting a page past the last one 301-redirects back to page 1
        # (`resp.history` is non-empty when that happens) — that would just
        # re-serve page 1's jobs, so stop instead of appending duplicates.
        if page_num > 1 and resp.history:
            break

        page_jobs = [j for j in _parse_page(resp.text, keyword) if j["source_job_id"] not in seen_ids]
        if not page_jobs:
            break

        for j in page_jobs:
            seen_ids.add(j["source_job_id"])
        results.extend(page_jobs)

        if page_num < max_pages:
            time.sleep(1)  # be polite between page requests

    return results


if __name__ == "__main__":
    jobs = search_physicstoday("physicist")
    print(f"Found {len(jobs)} jobs for 'physicist'")
    for j in jobs[:10]:
        print(j["title"], "-", j["company"], "-", j["location"], "-", j["salary"])
        print("  ", j["url"])

    jobs2 = search_physicstoday("quantum")
    print(f"\nFound {len(jobs2)} jobs for 'quantum'")
    for j in jobs2[:10]:
        print(j["title"], "-", j["company"], "-", j["location"], "-", j["salary"])
        print("  ", j["url"])
