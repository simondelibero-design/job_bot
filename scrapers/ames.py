"""Ames National Laboratory — operated by Iowa State University,
careers page at ameslab.gov/careers-and-internships.

Ames Lab is a DOE national lab, contractor-operated (Iowa State University),
so USAJobs.gov doesn't cover its postings — same situation as PNNL/ANL/LANL.

Ames Lab has no career site or API of its own. Its own careers page
(ameslab.gov/careers-and-internships/job-openings) links straight out to
individual postings on `isu.wd1.myworkdayjobs.com/en-US/IowaStateJobs` —
Iowa State University's single, campus-wide Workday tenant. Confirmed live
2026-08-24 by curling that careers page and grepping its outbound links.
That tenant's public CXS JSON API is the same platform-wide, unauthenticated
API as ANL's (see anl.py's docstring for the endpoint shape) — found the
same way, by grepping the page for `wday/cxs` and confirming with curl:
  - `POST /wday/cxs/isu/IowaStateJobs/jobs` (small JSON body, same shape as
    ANL's) returns a paginated list of ALL Iowa State job postings —
    faculty, ag extension, athletics, hospital staff, everything — not just
    Ames Lab. There is no `location`/`department`/`organization` facet that
    isolates just the lab: the only facet that even mentions it
    (`jobFamily` = "Ames Laboratory") only tags a small minority of actual
    Ames Lab postings and misses the rest, so it's not usable as a filter.
  - `GET /wday/cxs/isu/IowaStateJobs<externalPath>` returns full detail for
    one posting (jobDescription HTML, jobReqId, timeType, externalUrl),
    same shape as ANL's detail endpoint.

Because there's no server-side way to scope the tenant-wide search down to
"Ames Lab only", this module takes a different approach than pnnl.py/anl.py:
it pages through the *entire* ISU tenant listing (unauthenticated,
`searchText=""`, no facets — cheap, since ISU's total open-position count
runs well under 100 at any time), keeps only postings whose *title*
contains "Ames Laboratory" or "Ames National Laboratory" (verified live:
every Ames Lab posting inspected follows this titling convention, e.g.
"Postdoctoral Research Associate - Ames National Laboratory", "Ames
National Laboratory Research Technologist II"), fetches full detail only
for that small subset, and then keyword-filters on title + description
client-side (Workday's own `searchText` fuzzy-matches on "Ames" the city
name too, pulling in unrelated ISU jobs like "Clerk III" — confirmed live —
so it's not usable as the keyword filter here either).

Known limitation, stated honestly: a posting that doesn't put "Ames
[National] Laboratory" in its title (e.g. a generic-sounding "Health
Physicist" role that happens to support the lab) will be missed. No
reliable department/org field exists in this Workday tenant to catch those;
title-text matching is the best available signal.

hiringOrganization on every posting in this tenant reads simply "Iowa State
University" (not lab-specific), so `company` is hardcoded to "Ames National
Laboratory" here for postings this module has already screened by title.

Like anl.py, no posting inspected carries a compensation field, so `salary`
is always None.

Verified against live responses 2026-08-24.
"""
import re

import requests

TENANT = "isu"
SITE = "IowaStateJobs"
API_BASE = f"https://isu.wd1.myworkdayjobs.com/wday/cxs/{TENANT}/{SITE}"
CAREERS_URL = f"https://isu.wd1.myworkdayjobs.com/en-US/{SITE}"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

_AMES_LAB_RE = re.compile(r"ames\s+(national\s+)?laboratory", re.I)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _list_all_postings(page_size: int = 20, max_pages: int = 15) -> list[dict]:
    """Pages through the entire ISU Workday tenant (no search text, no
    facets) and returns the raw jobPostings list. Bounded by max_pages as a
    safety net in case `total` is ever wildly wrong."""
    postings = []
    offset = 0
    for _ in range(max_pages):
        payload = {"appliedFacets": {}, "limit": page_size, "offset": offset, "searchText": ""}
        resp = requests.post(f"{API_BASE}/jobs", json=payload, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("jobPostings", [])
        postings.extend(batch)
        offset += page_size
        if not batch or offset >= data.get("total", 0):
            break
    return postings


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
    description = _strip_html(jpi.get("jobDescription", ""))

    if keyword:
        haystack = f"{posting.get('title', '')} {description}".lower()
        if keyword.lower() not in haystack:
            return None

    return {
        "source": "ames",
        "source_job_id": jpi.get("jobReqId") or external_path,
        "title": posting.get("title", ""),
        "company": "Ames National Laboratory",
        "location": jpi.get("location") or posting.get("locationsText"),
        "salary": None,  # never populated on any posting inspected
        "job_type": jpi.get("timeType"),
        "url": jpi.get("externalUrl") or f"{CAREERS_URL}{external_path}",
        "snippet": description[:1000],
        "search_keyword": keyword,
    }


def search_ames(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Ames Lab is a single-site employer
    (Ames, IA) inside a shared ISU-wide job board, not a geographic search.

    Unlike pnnl.py/anl.py, `keyword` isn't sent to the API at all: the ISU
    tenant's own search matches too loosely (fuzzy-matches the city name
    "Ames") to double as an Ames-Lab-only filter, so this module pages the
    whole tenant, screens by title for Ames Lab postings, then applies
    `keyword` client-side against title + description of that subset.
    """
    all_postings = _list_all_postings()
    ames_postings = [p for p in all_postings if _AMES_LAB_RE.search(p.get("title", ""))]

    results = []
    for posting in ames_postings:
        job = _extract_job(posting, keyword)
        if job:
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_ames("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("   snippet:", (j["snippet"] or "")[:150])
