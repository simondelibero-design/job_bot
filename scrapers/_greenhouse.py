"""Shared helper for companies hosted on Greenhouse's public job board API.

Greenhouse exposes a real public JSON API for any company's board, no auth,
no login, no bot-detection dance — same tier as scrapers/usajobs.py and
scrapers/pnnl.py:
    GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
returns every open posting for that `board_token` in one response (id,
title, absolute_url, location.name, departments, offices, metadata,
updated_at, requisition_id, company_name, and content = the full HTML job
description when `content=true` is passed).

Two things this API does NOT have, confirmed live against ionq/
andurilindustries/psiquantum (2026-08-26) by inspecting every key present
across all returned jobs on all three boards:
  - No structured compensation field of any kind (no "salary", "pay_range",
    etc.) — `salary` is always None here, same convention as anl.py/ornl.py/
    bnl.py/nrel.py for sources with no structured salary field.
  - No employment-type field either (the only `metadata` entry seen on any
    of the three boards was a "Division" facet) — `job_type` is always None.
  - No server-side keyword search parameter — the endpoint just returns the
    board's full current listing. So unlike pnnl.py/usajobs.py (which pass
    `keyword` to the remote API), filtering here happens client-side after
    the fetch, matching `keyword` case-insensitively against the job title
    or its stripped HTML description — closer to aps.py/anl.py's pattern of
    "small single-employer board, do the search step locally."

`board_token` is the slug that appears in the company's own Greenhouse URL
(`job-boards.greenhouse.io/{token}` or the newer `boards.greenhouse.io/
{token}` — both resolve, it's the same board either way). It is NOT always
a simple lowercasing of the company's name — confirmed live 2026-08-26:
IonQ -> "ionq", PsiQuantum -> "psiquantum", but Anduril Industries ->
"andurilindustries" (bare "anduril" 404s). Rigetti Computing and Atom
Computing were also fingerprinted as Greenhouse-hosted but turned out on
inspection to actually be on Lever (jobs.lever.co/rigetti and
jobs.lever.co/atomcomputing, confirmed via each company's own careers
page) — not covered by this helper; no Greenhouse board_token exists for
them to guess.
"""
import re

import requests

API_BASE = "https://boards-api.greenhouse.io/v1/boards"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _extract_job(job: dict, source: str, company_name: str, keyword: str) -> dict | None:
    job_id = job.get("id")
    if not job_id:
        return None

    return {
        "source": source,
        "source_job_id": str(job_id),
        "title": job.get("title", ""),
        "company": job.get("company_name") or company_name,
        "location": (job.get("location") or {}).get("name"),
        "salary": None,  # Greenhouse's public API carries no compensation field
        "job_type": None,  # ...nor an employment-type field, on any board checked
        "url": job.get("absolute_url"),
        "snippet": _strip_html(job.get("content", ""))[:1000],
        "search_keyword": keyword,
    }


def fetch_greenhouse_jobs(board_token: str, source: str, company_name: str, keyword: str,
                           location: str = None, radius_miles: int = None) -> list[dict]:
    """Fetch and keyword-filter a single company's Greenhouse board.

    `location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — same as pnnl.py/aps.py, these are
    single-employer boards, not general geographic job search, and
    Greenhouse's public API has no location filter param anyway.
    """
    resp = requests.get(f"{API_BASE}/{board_token}/jobs", params={"content": "true"},
                         headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    needle = keyword.lower()
    results = []
    for job in data.get("jobs", []):
        extracted = _extract_job(job, source, company_name, keyword)
        if not extracted:
            continue
        haystack = f"{extracted['title']} {extracted['snippet']}".lower()
        if needle in haystack:
            results.append(extracted)
    return results
