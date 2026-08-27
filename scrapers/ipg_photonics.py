"""IPG Photonics — ipgphotonics.com/en-us/company/careers.

The careers page itself only embeds a small curated "featured jobs" widget
(24 static `<h4>` entries, several of which are actually category labels
like "Finance"/"HR", not real jobs) with "Apply Now!" links that all point
at `recruiting.adp.com` — IPG runs its actual job board on **ADP Recruiting
Management / myjobs.adp.com** ("MyJobs CX"), not one of the ATS platforms
already known to `ats/detect.py`.

Confirmed live 2026-08-26 by driving the real site once with Playwright
(this project's own script, not the shared browser tool) and recording the
XHR a real page load fires — the "Apply Now!" link chain is:
    ipgphotonics.com/company/careers
    -> recruiting.adp.com/srccar/public/nghome.guid?c=2179707&d=ExternalCareerSite&prc=RMPOD4
    -> myjobs.adp.com/ipgjobs (the real Angular SPA career site, domain "ipgjobs")

That SPA calls two plain, public, unauthenticated JSON endpoints on load:

    GET https://myjobs.adp.com/public/staffing/v1/career-site/ipgjobs
        -> a public config blob for this career site (no cookies, no login)
        that happens to carry a short-lived `myJobsToken` value in its own
        response body, plus this client's `orgoid` and its
        `settings.externalId` ("careersiteid", 228907 for IPG).

    GET https://my.adp.com/myadp_prefix/mycareer/public/staffing/v1/job-requisitions/apply-custom-filters
        ?$select=...&$top=200&tz=America/Los_Angeles
        headers: myjobstoken: <token from the call above>, rolecode: manager
        -> the full requisition list (91 postings, confirmed live), each
        with title, req ID, posting date, and location detail.

`myjobstoken` is minted anonymously by the first, fully public endpoint
(no login, no cookie jar, no account) — it's the same class of thing as the
CSRF token northrop_grumman.py pulls off its careers page before calling
its search API: ordinary session bootstrapping that the site's own
frontend does on every anonymous page load, not a bot-detection mechanism.
Reproducing it with two plain `requests` calls is not evading anything.

A `$filter=contains(jobTitle,'...')` param was tried against the
job-requisitions endpoint and silently ignored (still returned all 91
postings) — confirmed live, so there is no working server-side keyword
search here. IPG's whole board is under 100 postings, so this scraper
fetches everything in one `$top=200` request and filters client-side
against the title, same pattern as aps.py/anl.py for small single-employer
boards.

No structured salary or employment-type field exists anywhere in this
API's schema (confirmed by requesting a record with no `$select` filter at
all and inspecting every key present: only requisition/location plumbing,
no comp or full/part-time field) — matching what a human sees on the page,
so both are always None here.

Job detail page URL pattern (`myjobs.adp.com/ipgjobs/cx/job-details/{reqId}`)
confirmed live to resolve (HTTP 200) for a real reqId, following the
Angular route name ("job-details") found in the SPA's own JS bundle.

Verified live 2026-08-26: 91 total postings; "engineer" matched 32 by title
(Design Assurance Engineer, Integration Engineer, Electrical Engineer,
etc., mostly Marlborough MA / Oxford MA / Salem NH).
"""
import html
import re

import requests

CAREER_SITE_DOMAIN = "ipgjobs"
CONFIG_URL = f"https://myjobs.adp.com/public/staffing/v1/career-site/{CAREER_SITE_DOMAIN}"
SEARCH_URL = "https://my.adp.com/myadp_prefix/mycareer/public/staffing/v1/job-requisitions/apply-custom-filters"
JOB_PAGE_BASE = f"https://myjobs.adp.com/{CAREER_SITE_DOMAIN}/cx/job-details"
COMPANY = "IPG Photonics"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_SELECT_FIELDS = (
    "reqId,jobTitle,publishedJobTitle,type,jobDescription,jobQualifications,"
    "workLocations,workLevelCode,clientRequisitionID,postingDate,requisitionLocations"
)


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _get_token() -> str:
    """Anonymous session bootstrap — see module docstring. Raises if the
    public config endpoint doesn't hand back a token (e.g. site renamed)."""
    resp = requests.get(CONFIG_URL, headers={"User-Agent": _UA}, timeout=20)
    resp.raise_for_status()
    token = resp.json().get("myJobsToken")
    if not token:
        raise RuntimeError("ipg_photonics: no myJobsToken in career-site config response")
    return token


def _format_location(req: dict) -> str | None:
    locs = req.get("requisitionLocations") or []
    parts = []
    for loc in locs:
        addr = (loc or {}).get("address") or {}
        city = addr.get("cityName")
        state = (addr.get("countrySubdivisionLevel1") or {}).get("codeValue")
        if city and state:
            parts.append(f"{city}, {state}")
        elif city:
            parts.append(city)
    return "; ".join(parts) if parts else None


def _extract_job(req: dict, keyword: str) -> dict | None:
    req_id = req.get("reqId")
    if not req_id:
        return None

    return {
        "source": "ipg_photonics",
        "source_job_id": req.get("clientRequisitionID") or req_id,
        "title": req.get("publishedJobTitle") or req.get("jobTitle", ""),
        "company": COMPANY,
        "location": _format_location(req),
        "salary": None,  # no structured compensation field in this API's schema
        "job_type": None,  # no employment-type field either — see module docstring
        "url": f"{JOB_PAGE_BASE}/{req_id}",
        "snippet": _strip_html(req.get("jobDescription", ""))[:1000],
        "search_keyword": keyword,
    }


def search_ipg_photonics(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — no working server-side keyword or
    location filter was found on this API (see module docstring), and
    IPG's whole board is small enough to filter client-side after one
    fetch."""
    token = _get_token()
    resp = requests.get(
        SEARCH_URL,
        headers={
            "User-Agent": _UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://myjobs.adp.com/",
            "myjobstoken": token,
            "rolecode": "manager",
        },
        params={
            "$orderby": "postingDate desc",
            "$select": _SELECT_FIELDS,
            "$top": 200,
            "tz": "America/Los_Angeles",
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()

    keyword_lower = keyword.lower()
    results = []
    for req in data.get("jobRequisitions", []):
        title = req.get("publishedJobTitle") or req.get("jobTitle", "")
        if keyword_lower not in title.lower():
            continue
        job = _extract_job(req, keyword)
        if job:
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_ipg_photonics("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
