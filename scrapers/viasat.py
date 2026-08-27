"""Viasat, Inc. — careers.viasat.com (viasat.com/careers redirects here).

The careers page HTML references several `*.icims.com` hostnames
(`careers-viasat.icims.com`, `globalcareers-viasat.icims.com`), suggesting
plain iCIMS at first glance — but `careers-viasat.icims.com/jobs/search`
just JS-redirects back to careers.viasat.com, and
`globalcareers-viasat.icims.com` serves iCIMS's newer "adaptive"/SPA theme
(`new_job_table` UI module) with no server-rendered job list and no obvious
JSON endpoint reachable by URL-guessing.

To find the real data source without guessing blindly, this project's own
Playwright (not the shared browser tool) was driven once against
`careers.viasat.com/jobs?searchKeyword=engineer` to record actual XHR
traffic. That showed the visible page is a **Jibe/Oracle Recruiting Cloud**
career-site front end (script bundle at `app.jibecdn.com/prod/search/...`)
that calls Viasat's own public, unauthenticated JSON API — iCIMS is only
the backend ATS Viasat's recruiters use (`ats_code: "icims"` appears inside
each job record's metadata), not what a scraper talks to here:

    GET https://careers.viasat.com/api/jobs
        ?page=<n>&limit=<size>&sortBy=relevance&descending=false&internal=false

Confirmed live 2026-08-26: no auth/cookies/session required (a fresh,
cookie-less `requests.get` works); `limit=100` is the largest page size
that doesn't 422 (tried 200/300, both 422); 275 total open postings.
**`searchKeyword` on this endpoint does NOT filter server-side** — verified
by comparing `totalCount`/results for `searchKeyword=engineer`,
`searchKeyword=physicist`, a nonsense string, and no keyword at all: all
four returned the identical `totalCount: 275` and the identical first
result ("Embedded Software Engineer") — so filtering here happens
client-side against title + qualifications + responsibilities text, same
pattern as scrapers/_greenhouse.py for boards with no working keyword param.

Each job record is rich (`salary_min_value`/`salary_max_value` fields
exist but were 0 on every one of the 100 postings sampled — not populated
by Viasat, so `salary` is always None here, an honest gap rather than a
parsing failure), `employment_type` (e.g. "FULL_TIME"), and full HTML
`description`/`qualifications`/`responsibilities` fields concatenated here
for the snippet. `full_location` gives a human-readable, possibly
multi-site location string.
"""
import html
import re

import requests

API_URL = "https://careers.viasat.com/api/jobs"
JOB_PAGE_BASE = "https://careers.viasat.com/jobs"
COMPANY = "Viasat, Inc."

PAGE_SIZE = 100  # confirmed live: 200 and 300 both 422; 100 is the largest that works
MAX_RESULTS = 300  # safety cap on pagination (covers the full ~275-job board)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _format_job_type(employment_type: str) -> str | None:
    if not employment_type:
        return None
    return employment_type.replace("_", "-").title()  # "FULL_TIME" -> "Full-Time"


def _extract_job(record: dict, keyword: str) -> dict | None:
    slug = record.get("slug")
    if not slug:
        return None

    salary_min = record.get("salary_min_value") or 0
    salary_max = record.get("salary_max_value") or 0
    salary = f"${salary_min:,} - ${salary_max:,}" if salary_min and salary_max else None

    snippet_source = " ".join(filter(None, [
        record.get("description", ""),
        record.get("responsibilities", ""),
        record.get("qualifications", ""),
    ]))

    return {
        "source": "viasat",
        "source_job_id": record.get("req_id") or slug,
        "title": record.get("title", ""),
        "company": record.get("hiring_organization") or COMPANY,
        "location": record.get("full_location") or record.get("location_name"),
        "salary": salary,  # populated field exists but was 0 on every posting sampled
        "job_type": _format_job_type(record.get("employment_type")),
        "url": f"{JOB_PAGE_BASE}/{slug}?lang=en-us",
        "snippet": _strip_html(snippet_source)[:1000],
        "search_keyword": keyword,
    }


def search_viasat(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location`, if given, is a client-side
    case-insensitive substring match against `full_location` — this API's
    own `location` query param is a facet-based filter (exact city/state
    values from its own filter list), not a free-text/radius search."""
    keyword_lower = keyword.lower()
    location_lower = location.lower() if location else None

    all_results = []
    page = 1
    total_count = None
    while total_count is None or (page - 1) * PAGE_SIZE < min(total_count, MAX_RESULTS):
        resp = requests.get(
            API_URL,
            headers=_HEADERS,
            params={
                "page": page,
                "limit": PAGE_SIZE,
                "sortBy": "relevance",
                "descending": "false",
                "internal": "false",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if total_count is None:
            total_count = data.get("totalCount", 0)

        jobs = data.get("jobs", [])
        if not jobs:
            break

        for entry in jobs:
            record = entry.get("data") or {}
            extracted = _extract_job(record, keyword)
            if not extracted:
                continue

            haystack = f"{extracted['title']} {extracted['snippet']}".lower()
            if keyword_lower not in haystack:
                continue
            if location_lower and location_lower not in (extracted["location"] or "").lower():
                continue
            all_results.append(extracted)

        page += 1

    return all_results


if __name__ == "__main__":
    jobs = search_viasat("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
