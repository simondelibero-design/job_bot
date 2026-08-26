"""National Renewable Energy Laboratory (NREL) — nrel.wd5.myworkdayjobs.com/NLR.

NREL is a DOE national lab, contractor-operated (Alliance for Sustainable
Energy, LLC), so USAJobs.gov doesn't cover its postings — same situation as
PNNL, LANL, and ANL.

nrel.gov/careers/find-job.html points out to NREL's Workday-hosted career
site. WebSearch turned up the career site URL as
nrel.wd5.myworkdayjobs.com/NREL, but that path 404s live — the actual site
name is "NLR", confirmed by following the search result link and by curling
nrel.wd5.myworkdayjobs.com/NLR (200 OK). Interestingly, the postings
themselves now refer to the employer internally as the "National Laboratory
of the Rockies (NLR)" rather than NREL (verified live 2026-08-24, e.g. job
posting R14216's body text: "NLR is located at the foothills of the Rocky
Mountains in Golden, Colorado...") — apparently a rebrand in progress. This
module keeps `company` as "National Renewable Energy Laboratory (NLR)" so
matching/search downstream still finds it under the name everyone searches
for, while acknowledging the site's own new label.

Same Workday CXS JSON API pattern as anl.py, just a different tenant/site:
  - `POST /wday/cxs/nrel/NLR/jobs` with `{"appliedFacets": {}, "limit": N,
    "offset": 0, "searchText": "..."}` returns a paginated list of matching
    postings (title, externalPath, locationsText, postedOn, a bulletFields
    req-id).
  - `GET /wday/cxs/nrel/NLR<externalPath>` (externalPath already includes
    the leading "/job/...") returns full detail for one posting:
    jobDescription (HTML), jobReqId, location, timeType, externalUrl (the
    human-facing apply page), etc.
Found by grepping the Workday-hosted job page for its `wday/cxs` network
calls (same discovery method as pnnl.py/anl.py), then confirmed live with
curl — no login, no browser automation, no bot-detection wall.

The list endpoint alone doesn't carry a description, so this scraper does
one extra GET per posting (bounded by `limit`) to build a real snippet,
same tradeoff as anl.py.

Applying still goes through Workday's own UI, which (per ats/workday.py)
gates every application behind mandatory account creation — irrelevant
here since this project only discovers/logs jobs, never auto-applies.

Workday's list/detail endpoints here carry no structured compensation
field, but several NREL posting bodies do embed a plain-text
"Annual Salary Range" line inside jobDescription (e.g. "$83,600 -
$150,500") — this module does not attempt to regex-mine that out, matching
the project's established convention (anl.py, ornl.py, bnl.py) of leaving
`salary` as None when a source has no structured salary field, rather than
parsing free text out of a description.

Verified against live responses 2026-08-24.
"""
import re

import requests

TENANT = "nrel"
SITE = "NLR"
API_BASE = f"https://nrel.wd5.myworkdayjobs.com/wday/cxs/{TENANT}/{SITE}"
CAREERS_URL = f"https://nrel.wd5.myworkdayjobs.com/{SITE}"

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
        "source": "nrel",
        "source_job_id": jpi.get("jobReqId") or (bullet[0] if bullet else external_path),
        "title": posting.get("title", ""),
        "company": "National Renewable Energy Laboratory (NLR)",
        "location": jpi.get("location") or posting.get("locationsText"),
        "salary": None,  # no structured compensation field; see module docstring
        "job_type": jpi.get("timeType"),
        "url": jpi.get("externalUrl") or f"{CAREERS_URL}{external_path}",
        "snippet": _strip_html(jpi.get("jobDescription", ""))[:1000],
        "search_keyword": keyword,
    }


def search_nrel(keyword: str, location: str = None, radius_miles: int = None,
                 limit: int = 20) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Workday's search here is keyword +
    facet based, not a geographic radius search.

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
    jobs = search_nrel("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("   snippet:", (j["snippet"] or "")[:150])
