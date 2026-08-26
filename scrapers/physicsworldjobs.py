"""Physics World Jobs (IOP Publishing) — physicsworldjobs.com.

Same Madgex job-board-as-a-service platform as scrapers/aps.py
(apsphysicsjobs.com — which is itself run by IOP Publishing's Physics World
Jobs network under the hood) and as scrapers/physicstoday.py. Confirmed
independently (2026-08-26): `curl` with a plain desktop UA returns 200 OK,
plain server-rendered HTML, no login wall, no CAPTCHA, and the same
`<li class="lister__item" id="item-<id>">...` results markup with a
`js-clickable-area-link` job-title anchor and `lister__meta-item--*` metadata
`<li>`s as the other two scrapers. Reuses the same plain `requests` + regex
approach — no browser automation needed.

Differences found from aps.py's site while verifying (Madgex tenants vary):
- Pagination works here too (like physicstoday.py, unlike aps.py's site).
  Extra pages are at `/jobs/<n>/?keywords=<kw>` (page 1 is the bare search
  URL), 20 jobs/page. Confirmed against `keywords=physicist` (180 total
  site hits per the page's own analytics counter, 25 matched-and-returned
  per that same counter, 20 shown on page 1) which produced a real
  `/jobs/2/?keywords=physicist` link.
- Real promoted "Employer profile" cards DO show up in normal search
  results here (unlike physicstoday.py) — e.g. `/job/30027/employer-profile/`
  — 4 of them mixed into the 20 `physicist` results on 2026-08-26. These are
  employers advertising their own profile page, not real job postings, and
  are filtered out the same way aps.py does it (by URL suffix), same as
  physicstoday.py.
- No location/radius search implemented, same reasoning as aps.py: the
  search form only exposes a free-text `Keywords`/`keywords` field
  server-side; location facets on the page are pre-computed browse-by-location
  links, not a radius search drivable with a plain query param.
  `location`/`radius_miles` are accepted for interface parity but unused.

Verified live 2026-08-26 with `keywords=physicist` (25 matched, 20 on page 1,
real second page confirmed) and `keywords=quantum` — both returned real,
sane job data.
- Also confirmed: a keyword matching zero jobs returns HTTP 404 (still with
  a normal HTML body — its embedded analytics blob shows
  `returned-results: 0`), not a 200 with an empty list. Handled as "no
  results" rather than an error.
"""
import re
import time

import requests

BASE_URL = "https://www.physicsworldjobs.com/jobs/"
JOB_BASE_URL = "https://www.physicsworldjobs.com"
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
        "source": "physicsworldjobs",
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
        # Skip promoted "Employer profile" cards (e.g. an employer advertising
        # their own /job/<id>/employer-profile/ page) — these aren't real job
        # postings but get mixed into normal search results. See module docstring.
        if job and job["title"] and job["url"] and not job["url"].rstrip("/").endswith("employer-profile"):
            results.append(job)
    return results


def search_physicsworldjobs(keyword: str, location: str = None, radius_miles: int = None,
                             max_pages: int = 3) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — see module docstring."""
    params = {"keywords": keyword}
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

        # Requesting a page past the last one redirects back to page 1
        # (`resp.history` non-empty) — that would just re-serve page 1's
        # jobs, so stop instead of appending duplicates.
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
    jobs = search_physicsworldjobs("physicist")
    print(f"Found {len(jobs)} jobs for 'physicist'")
    for j in jobs[:10]:
        print(j["title"], "-", j["company"], "-", j["location"], "-", j["salary"])
        print("  ", j["url"])

    jobs2 = search_physicsworldjobs("quantum")
    print(f"\nFound {len(jobs2)} jobs for 'quantum'")
    for j in jobs2[:10]:
        print(j["title"], "-", j["company"], "-", j["location"], "-", j["salary"])
        print("  ", j["url"])
