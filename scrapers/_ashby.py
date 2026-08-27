"""Shared helper for companies hosted on Ashby's public job-board API.

Ashby (ashbyhq.com) is a newer ATS, not previously used by any scraper in
this codebase. It exposes a real public JSON API for any org's board, no
auth, no login, no bot-detection dance — same tier as Greenhouse/Lever:

    GET https://api.ashbyhq.com/posting-api/job-board/{org_slug}

`org_slug` is the slug in the company's own jobs.ashbyhq.com URL (e.g.
jobs.ashbyhq.com/helion -> "helion"). Confirmed live 2026-08-26 for
helion (104 postings) and formenergy (184 postings) by fetching each
company's real careers page, extracting the embedded
`jobs.ashbyhq.com/{slug}` link/iframe src, and hitting this endpoint
directly. A POST to `api.ashbyhq.com/posting-api/job-board/{slug}`
(a guess based on Ashby's GraphQL-style internal API) 401s — the real
public endpoint is a plain unauthenticated GET, confirmed by matching the
returned job titles/locations against what each company's own careers
page renders.

Two things this API does NOT have, confirmed live against both boards
checked (2026-08-26), by inspecting every key present across all returned
jobs on both:
  - No structured compensation field (a "compensation" key exists in the
    schema but was `null`/absent on every posting checked on either
    board) — `salary` is always None here, same honest-gap treatment as
    scrapers/_greenhouse.py and scrapers/_lever.py for boards with no
    populated salary field.
  - No server-side keyword search — a `?q=engineer` query param is
    silently ignored (still returns the full unfiltered list, confirmed
    live) — so filtering happens client-side against the job title, same
    pattern as Greenhouse/Lever's public APIs.

Every job returned already has `isListed: true` (confirmed on both boards
checked — the API itself only returns currently-listed postings, there's
nothing further to filter there).
"""
import re

import requests

API_BASE = "https://api.ashbyhq.com/posting-api/job-board"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _extract_job(job: dict, source: str, company_name: str, keyword: str) -> dict | None:
    job_id = job.get("id")
    if not job_id:
        return None

    return {
        "source": source,
        "source_job_id": job_id,
        "title": job.get("title", ""),
        "company": company_name,
        "location": job.get("location"),
        "salary": None,  # Ashby's public API carries no populated compensation field
        "job_type": job.get("employmentType"),
        "url": job.get("jobUrl") or job.get("applyUrl"),
        "snippet": _strip_html(job.get("descriptionPlain") or job.get("descriptionHtml", ""))[:1000],
        "search_keyword": keyword,
    }


def fetch_ashby_jobs(org_slug: str, source: str, company_name: str, keyword: str,
                      location: str = None, radius_miles: int = None) -> list[dict]:
    """Fetch and keyword/location-filter a single company's Ashby board.

    `location`, if given, is a client-side case-insensitive substring match
    against Ashby's `location` string — no geocoding. `radius_miles` is
    accepted for interface parity with the other search_* functions but
    unused — same as Greenhouse/Lever, this is a single-employer board, not
    a general geographic job search.
    """
    resp = requests.get(f"{API_BASE}/{org_slug}", headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    keyword_lower = keyword.lower()
    location_lower = location.lower() if location else None

    results = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        if keyword_lower not in title.lower():
            continue
        if location_lower:
            job_location = (job.get("location") or "").lower()
            if location_lower not in job_location:
                continue
        extracted = _extract_job(job, source, company_name, keyword)
        if extracted:
            results.append(extracted)
    return results
