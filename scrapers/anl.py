"""Argonne National Laboratory (ANL) — argonne.wd1.myworkdayjobs.com.

ANL is a DOE national lab, contractor-operated (UChicago Argonne, LLC), so
USAJobs.gov doesn't cover its postings — this needs its own source.

anl.gov itself sits behind a Cloudflare challenge (confirmed live,
2026-08-24: `curl https://www.anl.gov/careers` comes back HTTP 403 with a
"Just a moment..." JS-challenge body, not real content) — but that's just
the marketing site. Argonne's actual career site runs on Workday
(argonne.wd1.myworkdayjobs.com/Argonne_Careers), found via WebSearch, and
Workday's public CXS JSON API behind that site is NOT behind Cloudflare and
needs no login or session:
  - `POST /wday/cxs/argonne/Argonne_Careers/jobs` with a small JSON body
    (`{"appliedFacets": {}, "limit": N, "offset": 0, "searchText": "..."}`)
    returns a paginated list of matching postings (title, externalPath,
    locationsText, postedOn, a bulletFields req-id).
  - `GET /wday/cxs/argonne/Argonne_Careers<externalPath>` (externalPath
    already includes the leading "/job/...") returns full detail for one
    posting: jobDescription (HTML), jobReqId, location, timeType,
    externalUrl (the human-facing apply page), etc.
This is the same tier of "actually has an API" as PNNL and USAJobs.gov —
found by grepping the Workday-hosted job page for its `wday/cxs` network
calls, then confirmed live with curl. Same discovery method as pnnl.py,
just against Workday's platform-wide API instead of a bespoke one.

The list endpoint alone doesn't carry a description, so this scraper does
one extra GET per posting (bounded by `limit`) to build a real snippet —
more requests than pnnl.py needs, but still plain unauthenticated `requests`
calls, same tier of scraper.

Applying still goes through Workday's own UI, which (per ats/workday.py)
gates every application behind mandatory account creation — irrelevant
here since this project only discovers/logs jobs, never auto-applies.

Workday's postings here never carry a compensation field (neither the list
nor the detail endpoint), matching what a human sees on the page too, so
`salary` is always None.

Verified against live responses 2026-08-24.
"""
import re

import requests

TENANT = "argonne"
SITE = "Argonne_Careers"
API_BASE = f"https://argonne.wd1.myworkdayjobs.com/wday/cxs/{TENANT}/{SITE}"
CAREERS_URL = f"https://argonne.wd1.myworkdayjobs.com/{SITE}"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _fetch_detail(external_path: str) -> dict | None:
    try:
        resp = requests.get(f"{API_BASE}{external_path}", headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def _extract_job(posting: dict, keyword: str) -> dict | None:
    external_path = posting.get("externalPath")
    if not external_path:
        return None

    detail = _fetch_detail(external_path) or {}
    jpi = detail.get("jobPostingInfo", {})
    bullet = posting.get("bulletFields") or []

    return {
        "source": "anl",
        "source_job_id": jpi.get("jobReqId") or (bullet[0] if bullet else external_path),
        "title": posting.get("title", ""),
        "company": "Argonne National Laboratory",
        "location": jpi.get("location") or posting.get("locationsText"),
        "salary": None,  # Workday's postings here never carry a compensation field
        "job_type": jpi.get("timeType"),
        "url": jpi.get("externalUrl") or f"{CAREERS_URL}{external_path}",
        "snippet": _strip_html(jpi.get("jobDescription", ""))[:1000],
        "search_keyword": keyword,
    }


def search_anl(keyword: str, location: str = None, radius_miles: int = None,
               limit: int = 20) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Workday's search here is keyword +
    facet based, not a geographic radius search, and ANL is effectively a
    single-site employer (Lemont, IL) anyway.

    `limit` bounds both the Workday page size and (since each result needs
    an extra detail GET for its description) the number of follow-up
    requests this makes — keep it modest for interactive use.
    """
    payload = {"appliedFacets": {}, "limit": limit, "offset": 0, "searchText": keyword}
    resp = requests.post(f"{API_BASE}/jobs", json=payload, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for posting in data.get("jobPostings", []):
        job = _extract_job(posting, keyword)
        if job:
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_anl("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
