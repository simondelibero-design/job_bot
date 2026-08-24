"""Lawrence Livermore National Laboratory (LLNL) — careers via SmartRecruiters.

LLNL is a DOE national lab, contractor-operated (Lawrence Livermore National
Security, LLC), so USAJobs.gov doesn't cover its postings — same situation
as PNNL. LLNL's public-facing careers page
(www.llnl.gov/join-our-team/careers/find-your-job) links every posting
straight out to `jobs.smartrecruiters.com/LLNL/<id>-<slug>` — found by
curling that page's raw HTML and grepping for `smartrecruiters.com` links,
no browser automation needed. That means LLNL is on SmartRecruiters'
standard public JSON API, no auth required:

    https://api.smartrecruiters.com/v1/companies/LLNL/postings

`ats/smartrecruiters.py` already knows how to drive the actual apply form
once a posting from here reaches the application-prep stage — worth noting
that module found SmartRecruiters' own bot detection blocks *Playwright*
automation on the apply form itself, but that's a different surface than
this read-only postings API, which has no such gate for plain `requests`.

The list endpoint (`/postings`) does NOT include the job description or a
salary field — only summary fields (title, location, employment type,
custom fields). To get real description text for the `snippet` field (used
for keyword scoring downstream), this module makes one extra GET per
matching posting to `/postings/<id>`, which returns the full
`jobAd.sections.jobDescription` HTML. No salary field was found anywhere in
the API responses actually inspected (2026-08-24) — LLNL postings don't
appear to publish structured pay ranges via this API — so `salary` is
always None here.

The posting's own `refNumber` (e.g. "REF8753Q") is used as `source_job_id`
— LLNL's human-facing requisition number, stable and unique.

Job URLs are built as `jobs.smartrecruiters.com/LLNL/<id>` — verified live
that SmartRecruiters' apply-page routing works fine with just the numeric
id and no SEO slug text at all (200 response either way), so the trailing
slug is skipped rather than reverse-engineered.

This module has been verified against live responses (2026-08-24) — the
endpoint, keyword search (`q` param), and detail lookup were all confirmed
against real API traffic, not assumed from documentation (SmartRecruiters'
public API docs exist but weren't consulted; this was found and verified
purely by inspecting LLNL's live site and live responses).
"""
import re

import requests

BASE_URL = "https://api.smartrecruiters.com/v1/companies/LLNL/postings"


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _fetch_description(posting_id: str) -> str:
    try:
        resp = requests.get(f"{BASE_URL}/{posting_id}", timeout=15)
        resp.raise_for_status()
        sections = resp.json().get("jobAd", {}).get("sections", {})
        text = sections.get("jobDescription", {}).get("text", "")
        return _strip_html(text)[:1000]
    except (requests.RequestException, ValueError):
        return ""


def _extract_job(posting: dict, keyword: str) -> dict | None:
    posting_id = posting.get("id")
    if not posting_id:
        return None

    location = posting.get("location") or {}
    employment = posting.get("typeOfEmployment") or {}

    return {
        "source": "llnl",
        "source_job_id": posting.get("refNumber") or posting_id,
        "title": posting.get("name", ""),
        "company": "Lawrence Livermore National Laboratory",
        "location": location.get("fullLocation"),
        "salary": None,
        "job_type": employment.get("label"),
        "url": f"https://jobs.smartrecruiters.com/LLNL/{posting_id}",
        "snippet": _fetch_description(posting_id),
        "search_keyword": keyword,
    }


def search_llnl(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — like PNNL, this is a single
    employer's postings, not a general job board with geographic search."""
    params = {"q": keyword, "limit": 100}
    resp = requests.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for posting in data.get("content", []):
        extracted = _extract_job(posting, keyword)
        if extracted:
            results.append(extracted)
    return results


if __name__ == "__main__":
    jobs = search_llnl("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("   ", j["url"])
        print("   snippet:", (j["snippet"] or "")[:150])
