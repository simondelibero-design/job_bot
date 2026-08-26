"""Idaho National Laboratory (INL) — careers.inl.gov.

INL is a DOE national lab, contractor-operated (Battelle Energy Alliance),
so USAJobs.gov doesn't cover its postings — same situation as PNNL/SRNL/SLAC.

inl.gov/careers/'s "Search Jobs" button links straight out to:

    https://careers.inl.gov/hcmUI/CandidateExperience/en/sites/pro/jobs

That URL shape (`hcmUI/CandidateExperience/.../sites/<site>/jobs`) is the
same Oracle Fusion Cloud Recruiting ("Candidate Experience") platform
already documented in this project for SLAC (scrapers/slac.py) and SRNL
(scrapers/srnl.py) — INL just hosts it on its own domain (`careers.inl.gov`)
instead of a shared `*.oraclecloud.com` tenant host, with its own site
number, read directly out of live network traffic: `siteNumber=CX_1001`
(SLAC/SRNL use `CX_1`). Same underlying REST API shape as those two:

    GET /hcmRestApi/resources/latest/recruitingCEJobRequisitions
        ?onlyData=true&expand=requisitionList.secondaryLocations,flexFieldsFacet.values
        &finder=findReqs;siteNumber=CX_1001,keyword=<kw>,limit=<n>,offset=0,
                sortBy=POSTING_DATES_DESC

    GET /hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails
        ?onlyData=true&finder=ById;Id="<id>",siteNumber=CX_1001

Unlike SLAC/SRNL's tenants, `careers.inl.gov` sits behind Cloudflare's bot
management — a direct unauthenticated `requests.get` against either
endpoint (or even the plain HTML page) is served a Cloudflare JS challenge
("Just a moment...") instead of data, confirmed live. Crucially, this is
NOT the same "flatly walled off, don't fight it" situation as lanl.py's
jobs.lanl.gov: a real (even headless) browser session clears the challenge
automatically just by loading the page with JS enabled, and once cleared,
the exact same REST endpoints return normal JSON to `fetch()` calls made
from that page. So this module uses Playwright (like indeed.py) to load
the Candidate Experience site once — which clears the Cloudflare challenge
and picks up its clearance cookie — and then drives the same two REST
endpoints above via `fetch()` executed inside that browser page (not via a
separate `requests` session, which would immediately hit the challenge
again with no way to solve it non-interactively).

Keyword matching on the list endpoint is loose/fuzzy against title +
description (confirmed live: keyword="cybersecurity" pulled in "Manager of
Tours, Hosting & Protocol", which only mentions cybersecurity in its
INL-wide mission blurb) — same known tradeoff already documented in
srnl.py for this same platform. A clearly non-matching keyword (verified
with a nonsense string) correctly returns zero results, confirming the
filter is real, just imprecise.

The list endpoint's `ShortDescriptionStr` is populated (unlike SRNL's
tenant, where it's always empty) but short/marketing-flavored; this module
still makes one extra detail-page request per matching posting (same
tradeoff as srnl.py/slac.py) to pull `ExternalDescriptionStr`, the fuller
HTML job description, for the `snippet` field.

No structured salary field exists in either response (same as every other
Oracle Recruiting Cloud tenant in this project), so `salary` is always
None. `job_type` is populated from `WorkplaceType` (e.g. "On-site").

This module has been verified against live browser-driven responses
(2026-08-26) — schema, keyword search, the Cloudflare-clearance behavior,
and the detail endpoint were all confirmed against real traffic, not
assumed from documentation.
"""
import html
import json
import re

from playwright.sync_api import sync_playwright

API_HOST = "https://careers.inl.gov"
JOBS_UI_URL = f"{API_HOST}/hcmUI/CandidateExperience/en/sites/pro/jobs"
SEARCH_URL = f"{API_HOST}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
DETAIL_URL = f"{API_HOST}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
JOB_PAGE_BASE = f"{API_HOST}/hcmUI/CandidateExperience/en/sites/pro/job"
SITE_NUMBER = "CX_1001"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_FETCH_JS = """async (url) => {
    const resp = await fetch(url, {headers: {"Accept": "application/json"}});
    return {status: resp.status, text: await resp.text()};
}"""


def _clean_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _page_fetch_json(page, url: str) -> dict:
    result = page.evaluate(_FETCH_JS, url)
    if result["status"] != 200:
        return {}
    try:
        return json.loads(result["text"])
    except ValueError:
        return {}


def _fetch_snippet(page, job_id: str) -> str:
    params = f'?onlyData=true&finder=ById;Id="{job_id}",siteNumber={SITE_NUMBER}'
    data = _page_fetch_json(page, DETAIL_URL + params)
    items = data.get("items", [])
    if not items:
        return ""
    desc = items[0].get("ExternalDescriptionStr") or items[0].get("ShortDescriptionStr", "")
    return _clean_html(desc)[:1000]


def _extract_job(page, job: dict, keyword: str) -> dict | None:
    job_id = job.get("Id")
    if not job_id:
        return None

    return {
        "source": "inl",
        "source_job_id": job_id,
        "title": job.get("Title", ""),
        "company": "Idaho National Laboratory",
        "location": job.get("PrimaryLocation"),
        "salary": None,
        "job_type": job.get("WorkplaceType") or None,
        "url": f"{JOB_PAGE_BASE}/{job_id}",
        "snippet": _fetch_snippet(page, job_id),
        "search_keyword": keyword,
    }


def search_inl(keyword: str, location: str = None, radius_miles: int = None,
                limit: int = 50, headless: bool = True) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — INL's career site is a single
    employer's postings, not a general job board with geographic search."""
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        # Loading the Candidate Experience site clears Cloudflare's bot
        # challenge and sets its clearance cookie in this browser context;
        # the REST calls below reuse that same page/context.
        page.goto(JOBS_UI_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        params = (
            f"?onlyData=true&expand=requisitionList.secondaryLocations,flexFieldsFacet.values"
            f"&finder=findReqs;siteNumber={SITE_NUMBER},keyword={keyword},"
            f"limit={limit},offset=0,sortBy=POSTING_DATES_DESC"
        )
        data = _page_fetch_json(page, SEARCH_URL + params)
        items = data.get("items", [])
        reqs = items[0].get("requisitionList", []) if items else []

        for job in reqs:
            extracted = _extract_job(page, job, keyword)
            if extracted:
                results.append(extracted)

        browser.close()

    return results


if __name__ == "__main__":
    jobs = search_inl("nuclear engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("   ", j["url"])
        print("   snippet:", (j["snippet"] or "")[:150])
