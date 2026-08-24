"""Pacific Northwest National Laboratory (PNNL) — careers.pnnl.gov.

PNNL is a DOE national lab, contractor-operated (Battelle), so USAJobs.gov
doesn't cover its postings the way it covers direct federal positions —
this needs its own source. Turned out to have a real public JSON API behind
its career site (`/api/jobs`), found by inspecting live network traffic
while browsing careers.pnnl.gov — no login, no browser automation, no
bot-detection dance, same tier of "actually has an API" as USAJobs.gov.

PNNL is unusually relevant here: it's literally in Washington state
(Richland), unlike every other DOE national lab.

Every posting's `apply_url` in the API response points to
`careers-pnnl.icims.com/jobs/<id>/...` — PNNL's application flow runs on
iCIMS, so `ats/icims.py` already applies once these postings reach the
application-prep stage.

This module has been verified against live responses (2026-08-24) —
schema, keyword search, and the single-page `limit` param were all
confirmed by inspecting real API traffic, not assumed from documentation.
"""
import re

import requests

BASE_URL = "https://careers.pnnl.gov/api/jobs"


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _format_salary(job: dict) -> str | None:
    lo, hi = job.get("salary_min_value"), job.get("salary_max_value")
    if not lo and not hi:
        return None
    if lo and hi:
        return f"${lo:,.0f} - ${hi:,.0f}"
    return f"${(lo or hi):,.0f}"


def _extract_job(job: dict, keyword: str) -> dict | None:
    data = job.get("data", {})
    req_id = data.get("req_id")
    if not req_id:
        return None

    return {
        "source": "pnnl",
        "source_job_id": req_id,
        "title": data.get("title", ""),
        "company": data.get("hiring_organization") or "Pacific Northwest National Laboratory",
        "location": data.get("short_location") or data.get("location_name"),
        "salary": _format_salary(data),
        "job_type": data.get("employment_type"),
        "url": data.get("apply_url"),
        "snippet": _strip_html(data.get("description", ""))[:1000],
        "search_keyword": keyword,
    }


def search_pnnl(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — PNNL's career site isn't a general
    job board with geographic search, it's a single employer's postings."""
    params = {
        "page": 1,
        "sortBy": "relevance",
        "descending": "false",
        "internal": "false",
        "keywords": keyword,
        "limit": 100,
    }
    resp = requests.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for job in data.get("jobs", []):
        extracted = _extract_job(job, keyword)
        if extracted:
            results.append(extracted)
    return results


if __name__ == "__main__":
    jobs = search_pnnl("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["salary"])
