"""Fermi National Accelerator Laboratory (Fermilab, FNAL) —
fermilab.wd5.myworkdayjobs.com.

Fermilab is a DOE national lab, contractor-operated (Fermi Research
Alliance, LLC), so USAJobs.gov doesn't cover its postings — this needs its
own source.

fermilab.jobs (the lab's own careers landing page, found via WebSearch and
confirmed live with curl — plain WordPress, HTTP 200, no bot wall) doesn't
host listings itself; its "Job categories" page links out to individual
postings on `fermilab.wd5.myworkdayjobs.com/en-US/FermilabCareers/...` —
same Workday platform as ANL (see scrapers/anl.py), just a different tenant
("fermilab" vs "argonne") and pod ("wd5" vs "wd1"). Grepping the fetched
fermilab.jobs HTML for `myworkdayjobs.com` links surfaced the exact tenant/
site/pod, which is all that's needed to hit Workday's public CXS JSON API
directly — same discovery method, same API shape, same "no login required"
tier as ANL:
  - `POST /wday/cxs/fermilab/FermilabCareers/jobs` (JSON body:
    `{"appliedFacets": {}, "limit": N, "offset": 0, "searchText": "..."}`)
    returns matching postings (title, externalPath, locationsText,
    postedOn, a bulletFields req-id).
  - `GET /wday/cxs/fermilab/FermilabCareers<externalPath>` returns full
    detail: jobDescription (HTML), jobReqId, location, timeType,
    externalUrl (human-facing apply page), etc.

As with ANL, the list endpoint has no description, so this does one extra
GET per posting (bounded by `limit`) to build a real snippet. Applying goes
through Workday's own UI, which (per ats/workday.py) gates every
application behind mandatory account creation — irrelevant here since this
project only discovers/logs jobs, never auto-applies.

No compensation field appears on either endpoint here, so `salary` is
always None — same as ANL and same as what a human sees on the postings.

Verified against live responses 2026-08-24.
"""
import re

import requests

TENANT = "fermilab"
SITE = "FermilabCareers"
API_BASE = f"https://fermilab.wd5.myworkdayjobs.com/wday/cxs/{TENANT}/{SITE}"
CAREERS_URL = f"https://fermilab.wd5.myworkdayjobs.com/{SITE}"

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
        "source": "fnal",
        "source_job_id": jpi.get("jobReqId") or (bullet[0] if bullet else external_path),
        "title": posting.get("title", ""),
        "company": "Fermi National Accelerator Laboratory",
        "location": jpi.get("location") or posting.get("locationsText"),
        "salary": None,  # Workday's postings here never carry a compensation field
        "job_type": jpi.get("timeType"),
        "url": jpi.get("externalUrl") or f"{CAREERS_URL}{external_path}",
        "snippet": _strip_html(jpi.get("jobDescription", ""))[:1000],
        "search_keyword": keyword,
    }


def search_fnal(keyword: str, location: str = None, radius_miles: int = None,
                 limit: int = 20) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Workday's search here is keyword +
    facet based, not a geographic radius search, and Fermilab is effectively
    a single-site employer (Batavia, IL) anyway.

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
    jobs = search_fnal("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
