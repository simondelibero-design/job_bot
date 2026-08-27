"""SLB (formerly Schlumberger) — careers.slb.com.

careers.slb.com is a Sitecore site whose job search
(careers.slb.com/job-listing) is powered by Coveo, using Coveo's newer
"Atomic" web-component framework (`<atomic-search-interface>`,
`static.cloud.coveo.com/atomic/...`) rather than a classic Coveo-for-Sitecore
REST call embedded server-side. The Atomic component's own JS
(`/static/js/js-atomic-job-listing-search.js`) reads its Coveo
`organizationId`/`accessToken`/`searchHub` straight out of plain `<input
type="hidden">` fields on the page and passes them to
`atomic-search-interface.initialize({accessToken, organizationId})` — i.e.
these are static, non-secret values the page itself ships to every visitor
(a public *search-only* Coveo token, not a write/admin credential), so
reproducing the same call with `requests` is ordinary client-parity, not
credential theft. Confirmed live 2026-08-26:

    organizationId = "schlumbergerproduction0cs2zrh7"
    accessToken     = "xx914ae3d7-f62f-4dea-9368-2f78d68650e1"
    searchHub       = "CoveoJobsHub"
    pipeline        = "ATSJobsPipeline"

The same JS also reveals how the widget restricts Coveo's org-wide index
(which spans SLB's whole public website, not just jobs) down to job
postings — an advanced-query filter `@source=="ATS_Jobs_Source - Prod"` —
without which a query like "engineer" returns arbitrary marketing/product
pages that happen to mention the word:

    POST https://{organizationId}.org.coveo.com/rest/search/v2
         Authorization: Bearer {accessToken}
         {"q": "<keyword>", "searchHub": "CoveoJobsHub",
          "pipeline": "ATSJobsPipeline", "numberOfResults": ...,
          "firstResult": ..., "aq": "@source==\\"ATS_Jobs_Source - Prod\\""}

Confirmed live (2026-08-26) with the `aq` filter applied: "engineer"
returned 484 real job postings (Process Engineer - Navi Mumbai, Quality
Engineer - Shreveport, Manufacturing Engineer - Sugar Land, etc.) with
correctly job-flavored `raw` fields (`jobexperiencelevel`, `category`,
`city`, `country`, full HTML `description`) — a completely different result
set from the same query without the filter.

Each result's `raw.clickableuri` is SLB's own job-detail URL
(`careers.slb.com/jobdescription.aspx?id=<jobId>`); interestingly the raw
field value itself carries a trailing " 1" token on every result checked
(consistent across `clickableuri`/`sysclickableuri`/`uri` for the same
record) — this looks like a quirk in how SLB exports records into the
Coveo index, not a formatting bug introduced here, so it's reproduced
byte-for-byte rather than guessed at and stripped; the URL loads fine with
it included (confirmed live with a direct request).

No structured compensation or employment-type field exists in this index's
schema (`raw` was inspected in full on multiple results, no salary-shaped
key), so both are always None — `jobexperiencelevel` (e.g. "Experienced
Professional") is a seniority band, not full/part-time, so it isn't
reused as `job_type`.
"""
import html
import re

import requests

ORG_ID = "schlumbergerproduction0cs2zrh7"
ACCESS_TOKEN = "xx914ae3d7-f62f-4dea-9368-2f78d68650e1"
SEARCH_URL = f"https://{ORG_ID}.org.coveo.com/rest/search/v2"
SEARCH_HUB = "CoveoJobsHub"
PIPELINE = "ATSJobsPipeline"
JOBS_FILTER = '@source=="ATS_Jobs_Source - Prod"'
COMPANY = "SLB"

PAGE_SIZE = 25
MAX_RESULTS = 100  # safety cap on pagination

_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _strip_html(text: str) -> str:
    text = re.sub(r"<!\[CDATA\[|\]\]>", "", text or "")
    return html.unescape(re.sub(r"<[^>]+>", " ", text)).strip()


def _extract_job(result: dict, keyword: str) -> dict | None:
    raw = result.get("raw", {})
    permanent_id = raw.get("permanentid")
    if not permanent_id:
        return None

    city = raw.get("city")
    countries = raw.get("country") or []
    location_parts = [p for p in [city, ", ".join(countries) if countries else None] if p]

    return {
        "source": "slb",
        "source_job_id": permanent_id,
        "title": result.get("Title", ""),
        "company": COMPANY,
        "location": ", ".join(location_parts) if location_parts else None,
        "salary": None,  # no compensation field in this Coveo index's schema
        "job_type": None,  # "jobexperiencelevel" is a seniority band, not full/part-time
        "url": raw.get("clickableuri") or result.get("ClickUri"),
        "snippet": _strip_html(raw.get("description", ""))[:1000],
        "search_keyword": keyword,
    }


def search_slb(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — SLB's Coveo index isn't queried
    with a geographic radius filter here (only a free-text `q`), matching
    boeing.py/draper.py's Workday-facet scrapers."""
    all_results = []
    first_result = 0
    total = None
    while total is None or first_result < min(total, MAX_RESULTS):
        payload = {
            "q": keyword,
            "searchHub": SEARCH_HUB,
            "pipeline": PIPELINE,
            "numberOfResults": PAGE_SIZE,
            "firstResult": first_result,
            "aq": JOBS_FILTER,
        }
        resp = requests.post(SEARCH_URL, headers=_HEADERS, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if total is None:
            total = data.get("totalCount", 0)

        results = data.get("results", [])
        if not results:
            break
        for result in results:
            extracted = _extract_job(result, keyword)
            if extracted:
                all_results.append(extracted)
        first_result += PAGE_SIZE

    return all_results


if __name__ == "__main__":
    jobs = search_slb("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
