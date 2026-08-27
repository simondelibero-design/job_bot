"""National Instruments (NI) — ni.com/careers.

ni.com/careers no longer exists as its own site: it 301s straight to
`www.emerson.com/en-us/careers/`, which itself 301s again to
`www.emerson.com/en/corporate/careers` — Emerson Electric completed its
acquisition of NI in 2023, and NI's careers page is now simply Emerson's
own unified corporate careers page (confirmed live 2026-08-26 by following
both redirects with curl). There is no separate NI-only job board left to
scrape; NI postings now live inside Emerson's single company-wide system,
the same "one search covers every subsidiary" situation
scrapers/general_dynamics.py documents for GD's own family of companies.

Emerson's careers page is not on any ATS platform this project already
recognizes (no myworkdayjobs/icims/greenhouse/lever/smartrecruiters/
eightfold/ashbyhq marker) — it links out to
`hdjq.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs`,
an **Oracle Fusion Cloud Recruiting** ("Oracle Recruiting Cloud")
candidate-experience site. That UI itself is a JS shell with no embedded
job data, but it calls a genuinely public, unauthenticated REST API that a
plain `requests` call reaches directly, no login and no bot-wall
encountered anywhere in this path:

    GET https://hdjq.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions
        ?onlyData=true&expand=requisitionList
        &finder=findReqs;siteNumber=CX_1,limit=<n>,offset=<n>,keyword=<kw>

Confirmed live 2026-08-26: "engineer" returns `TotalJobsCount: 601` real
postings across every Emerson business unit; "physicist" returns a real,
verified zero; "National Instruments" as the keyword itself returns 16
real current NI-branded postings (e.g. still-open reqs that mention NI by
name), and "LabVIEW" (NI's flagship software, a term essentially unique to
NI's legacy business) returns 38 — confirming NI postings are still
findable inside Emerson's board via keyword even though there's no
separate NI-only endpoint anymore. `company` is left as "Emerson Electric
Co." for every result rather than trying to guess which postings are
"really NI" from the shared schema (see below) — a human reviewing the
dashboard can judge that from the title/description same as they would
for any GD subsidiary result.

**Location is NOT usable as a free-text filter**: the API accepts a
`location=<text>` fragment inside the `finder` string and echoes it back
in the response's `Location` field, but confirmed live it has zero effect
on `TotalJobsCount` or the results returned (identical counts with/without
it) — it wants a numeric `LocationId` facet value the way ClearanceJobs'
`city` facet does, not a plain string, so `location`/`radius_miles` are
accepted here for interface parity but unused, same "accepted but no
effect" pattern as clearancejobs.py/ornl.py.

No structured salary field exists anywhere on the requisition record
(every compensation-shaped key checked was null/absent on all postings
seen), so `salary` is always None. `job_type` is repurposed from
`WorkplaceType` (Oracle's own "On-site"/"Hybrid"/"Remote" classification —
the closest thing to an employment-type facet this API actually exposes),
same repurposing judgment call clearancejobs.py makes for its own board's
missing employment-type field. Job detail URLs follow the pattern the
site's own links use: `.../hcmUI/CandidateExperience/en/sites/CX_1/job/
{Id}` (confirmed live to return a real, if JS-shell, 200 page per posting).
"""
import requests

API_URL = "https://hdjq.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
JOB_PAGE_BASE = "https://hdjq.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job"
COMPANY_NAME = "Emerson Electric Co."
SITE_NUMBER = "CX_1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

PAGE_SIZE = 25
MAX_RESULTS = 200  # safety cap on pagination


def _extract_job(req: dict, keyword: str) -> dict | None:
    job_id = req.get("Id")
    if not job_id:
        return None

    return {
        "source": "national_instruments",
        "source_job_id": str(job_id),
        "title": req.get("Title", ""),
        "company": COMPANY_NAME,
        "location": req.get("PrimaryLocation"),
        "salary": None,  # no compensation field anywhere in this API's schema
        # No dedicated employment-type facet on this API; WorkplaceType
        # ("On-site"/"Hybrid"/"Remote") is the closest categorical field
        # actually available per-posting — see module docstring.
        "job_type": req.get("WorkplaceType"),
        "url": f"{JOB_PAGE_BASE}/{job_id}",
        "snippet": (req.get("ShortDescriptionStr") or "").strip()[:1000],
        "search_keyword": keyword,
    }


def search_national_instruments(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — see module docstring for why
    this API's location filter isn't usable as free text. Search this
    board with `keyword="National Instruments"` or `keyword="LabVIEW"` to
    surface NI-legacy postings specifically within Emerson's unified
    listing."""
    results = []
    offset = 0
    total = None
    while total is None or (offset < min(total, MAX_RESULTS)):
        finder = f"findReqs;siteNumber={SITE_NUMBER},limit={PAGE_SIZE},offset={offset},keyword={keyword}"
        params = {"onlyData": "true", "expand": "requisitionList", "finder": finder}
        resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        item = (data.get("items") or [{}])[0]
        if total is None:
            total = item.get("TotalJobsCount", 0)

        reqs = item.get("requisitionList", [])
        if not reqs:
            break
        for req in reqs:
            extracted = _extract_job(req, keyword)
            if extracted:
                results.append(extracted)
        offset += PAGE_SIZE

    return results[:MAX_RESULTS]


if __name__ == "__main__":
    for kw in ("National Instruments", "LabVIEW", "physicist"):
        jobs = search_national_instruments(kw)
        print(f"\n=== {kw!r}: found {len(jobs)} jobs ===")
        for j in jobs[:5]:
            print(j["title"], "-", j["location"], "-", j["job_type"])
            print("  ", j["url"])
            print("  ", j["snippet"][:150])
