"""SpaceX — spacex.com/careers.

spacex.com/careers is an Angular SPA (Angular Universal shell, no SSR
content — a bare `requests.get` returns only a ~3KB app skeleton with no
job data), so the real source had to be found by driving the page once
with Playwright (this project's own script, not the shared browser tool)
and recording every request it fires. That turned up a public, static
JSON file on SpaceX's Azure CDN
(`sxcontent9668.azureedge.us/cms-assets/job_posts_new.json`, gzip-encoded —
`curl --compressed` or `requests`' automatic decompression handles it fine)
with 2,198 lightweight job records, each carrying a `greenhouseId`.

That field gave away the real answer: **SpaceX's ATS is Greenhouse**
(`job-boards.greenhouse.io` / `boards.greenhouse.io`), one of the platforms
already in `ats/detect.py`'s `PLATFORM_PATTERNS` (and in `EASY_APPLY_PLATFORMS`
— `ats/greenhouse.py` can already fill SpaceX applications; this module is
just discovery). Confirmed live by inspecting real rendered job links
(`https://boards.greenhouse.io/spacex/jobs/<greenhouseId>`), then
confirming Greenhouse's own public board API — the same one this project
already knows about (task-level guidance references it directly) — serves
identical data with no auth, CAPTCHA, or session needed at all:

    GET https://boards-api.greenhouse.io/v1/boards/spacex/jobs
    GET https://boards-api.greenhouse.io/v1/boards/spacex/jobs/<id>?content=true

This module uses that Greenhouse API directly (not the Azure CDN file —
same data, standard endpoint, no reason to depend on SpaceX's internal CDN
path when the documented public API works) rather than the SpaceX site
itself. The bulk endpoint has no server-side keyword filter, so this
matches client-side against `title` (consistent with how a human would
scan the SpaceX jobs page, which is also just client-side filtering over
this same list) and fetches full `content` (HTML job description) only for
matches, one extra request per match — cheap at SpaceX's actual match
volumes for a specific keyword.

Metadata carries Employment Type and Discipline/Program as a list of
`{name, value}` dicts (Greenhouse's generic custom-field format) — pulled
out here for `job_type`; no structured salary field exists anywhere in
this pipeline, so `salary` is always None (not published in postings
inspected).

Verified live 2026-08-26: bulk endpoint returned 2,181 open SpaceX
positions; "propulsion" matched 12 titles (Propulsion Engineer variants
across Starship/Starlink) with real descriptions fetched successfully.
"""
import html
import re

import requests

BOARD_TOKEN = "spacex"
JOBS_URL = f"https://boards-api.greenhouse.io/v1/boards/{BOARD_TOKEN}/jobs"
JOB_DETAIL_URL = f"https://boards-api.greenhouse.io/v1/boards/{BOARD_TOKEN}/jobs/{{job_id}}"
COMPANY = "SpaceX"

MAX_RESULTS = 100  # safety cap on detail-page fetches

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _strip_html(text: str) -> str:
    # Greenhouse's `content` field comes back HTML-entity-escaped (literal
    # "&lt;div..." rather than "<div...") on top of being HTML itself, so
    # unescape before stripping tags, not after — stripping first leaves
    # the escaped angle brackets untouched and the tags visible as text.
    return re.sub(r"<[^>]+>", " ", html.unescape(text or "")).strip()


def _job_type(metadata: list) -> str | None:
    for field in metadata or []:
        if field.get("name") == "Employment Type" and field.get("value"):
            return field["value"]
    return None


def _fetch_content(job_id: int) -> str:
    try:
        resp = requests.get(
            JOB_DETAIL_URL.format(job_id=job_id),
            headers=_HEADERS,
            params={"content": "true"},
            timeout=20,
        )
        resp.raise_for_status()
        return _strip_html(resp.json().get("content", ""))[:1000]
    except (requests.RequestException, ValueError):
        return ""


def _extract_job(job: dict, keyword: str) -> dict | None:
    job_id = job.get("id")
    if not job_id:
        return None

    location = (job.get("location") or {}).get("name")

    return {
        "source": "spacex",
        "source_job_id": str(job.get("requisition_id") or job_id),
        "title": job.get("title", ""),
        "company": COMPANY,
        "location": location,
        "salary": None,  # not published on SpaceX/Greenhouse postings observed
        "job_type": _job_type(job.get("metadata")),
        "url": job.get("absolute_url") or f"https://boards.greenhouse.io/spacex/jobs/{job_id}",
        "snippet": _fetch_content(job_id),
        "search_keyword": keyword,
    }


def search_spacex(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Greenhouse's public board API
    has no server-side location filter; this module matches keyword only,
    same as the site's own client-side job list filtering."""
    resp = requests.get(JOBS_URL, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    all_jobs = resp.json().get("jobs", [])

    keyword_lower = keyword.lower()
    matches = [j for j in all_jobs if keyword_lower in (j.get("title") or "").lower()]

    results = []
    for job in matches[:MAX_RESULTS]:
        extracted = _extract_job(job, keyword)
        if extracted:
            results.append(extracted)
    return results


if __name__ == "__main__":
    jobs = search_spacex("propulsion")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
