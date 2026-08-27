"""Jane Street — janestreet.com/join-jane-street.

Not on any of the ATS platforms this project already knows (no myworkday
jobs/icims/greenhouse/lever/smartrecruiters/eightfold/ashbyhq marker
anywhere in the site's HTML) — Jane Street runs its own fully custom
careers site, and unlike most "custom" sites investigated in this project
it doesn't even need HTML scraping: the open-roles page
(janestreet.com/join-jane-street/open-roles/) loads two plain public JSON
files client-side with jQuery's `$.getJSON`, confirmed by reading the
page's own unminified `open_positions-*.js` bundle:

    GET https://www.janestreet.com/jobs/main.json
    GET https://www.janestreet.com/static/position-directories.json

`main.json` is a flat list of every posting Jane Street's CMS has ever
carried (234 entries checked live 2026-08-26) — full-time, new-grad, *and*
internship listings all live in this one file (`availability` distinguishes
them, e.g. "Full-Time: Experienced" vs. "Summer Internship"). It is NOT
already filtered to currently-open roles: `position-directories.json` is a
separate flat list of the numeric ids (as strings) that are actually live,
and the frontend's own `convertJSON()` explicitly checks
`positionDirectories.includes(l.id.toString())` before ever displaying a
job — this module reproduces that exact filter, or a plain "all jobs"
listing includes closed reqs (confirmed live: `main.json` also embeds a
`min_salary`/`max_salary` free-text-formatted pair, e.g. "100,000"/
"120,000", present on U.S. roles and null elsewhere — a real, if partial,
structured salary field, unlike most sources in this project).

The separate `/jobs/internships.json` file the same bundle also fetches
was checked and is NOT used here: live 2026-08-26 every one of its 49
entries has `"status": "closed"` — it exists for the frontend's own
"previously offered, don't show again" de-dup logic
(`handleClosedInternships()`), not as a second source of open postings.
Current internships already appear in `main.json` itself (via
`availability` values like "Summer Internship").

Per-job detail URL is built the same way the frontend does it
(`displayFilteredJobs()`): `/join-jane-street/position/{id}/`. `city` is a
3-4 letter internal code (NYC, LDN, HKG, AMS, CHI, SGP, MUM, SHA, PHL, SF,
ATX, "NYC/HKG") — mapped to a human-readable name via the same
`cityNameConversion` table the frontend embeds; an unrecognized code falls
back to the raw abbreviation rather than guessing.

No server-side keyword search exists on this static-file API, so matching
happens client-side against title + category + team + overview text, same
pattern as Greenhouse/Lever's shared helpers.

One real oddity, left untouched rather than "fixed": one live posting's
`position` field ("Machine Learning Researcher") is spelled using Lisu/
Canadian-Aboriginal-syllabics homoglyphs for the M/L/R
(confirmed live 2026-08-26, one specific Hong Kong req) — that's Jane
Street's own playful content, not a scraping artifact, so it's passed
through unmodified rather than "normalized" into something the API didn't
actually return.

Verified live 2026-08-26: 234 total entries in `main.json`, all 234 also
present in `position-directories.json` at the time of testing (i.e.
nothing was actually filtered out during this run, though the check is
still applied since it reflects the site's own real logic and could matter
on a different day); "quantitative" matched 13 real postings across
Trading/Research; "physicist"/"physics" matched 0 (a real, verified zero —
Jane Street's postings don't use that word, consistent with them hiring
physics grads into "Quantitative Trader"/"Quantitative Researcher" titled
roles rather than titles containing "physicist").
"""
import html
import re

import requests

MAIN_JOBS_URL = "https://www.janestreet.com/jobs/main.json"
POSITION_DIRECTORIES_URL = "https://www.janestreet.com/static/position-directories.json"
JOB_PAGE_BASE = "https://www.janestreet.com/join-jane-street/position"
COMPANY_NAME = "Jane Street"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Straight from the site's own open_positions-*.js bundle's `cityNameConversion`.
CITY_NAMES = {
    "NYC": "New York",
    "LDN": "London",
    "HKG": "Hong Kong",
    "AMS": "Amsterdam",
    "CHI": "Chicago",
    "SGP": "Singapore",
    "MUM": "Mumbai",
    "SHA": "Shanghai",
    "PHL": "Philadelphia",
    "SF": "San Francisco",
    "ATX": "Austin",
    "NYC/HKG": "New York/Hong Kong",
}


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _format_salary(job: dict) -> str | None:
    lo, hi = job.get("min_salary"), job.get("max_salary")
    if not lo and not hi:
        return None
    if lo and hi:
        return f"${lo} - ${hi} a year"
    return f"${lo or hi} a year"


def _extract_job(job: dict, keyword: str) -> dict | None:
    job_id = job.get("id")
    if not job_id:
        return None

    city = job.get("city") or ""
    location = CITY_NAMES.get(city, city or None)
    snippet = _strip_html(job.get("overview", ""))[:1000]

    return {
        "source": "jane_street",
        "source_job_id": str(job_id),
        "title": job.get("position", ""),
        "company": COMPANY_NAME,
        "location": location,
        "salary": _format_salary(job),
        "job_type": job.get("availability"),
        "url": f"{JOB_PAGE_BASE}/{job_id}/",
        "snippet": snippet,
        "search_keyword": keyword,
    }


def search_jane_street(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — this is a single flat listing
    with no server-side geographic filter; matching is purely by keyword."""
    resp = requests.get(MAIN_JOBS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    all_jobs = resp.json()

    resp2 = requests.get(POSITION_DIRECTORIES_URL, headers=HEADERS, timeout=20)
    resp2.raise_for_status()
    open_ids = set(resp2.json())

    needle = keyword.lower()
    results = []
    for job in all_jobs:
        if str(job.get("id")) not in open_ids:
            continue
        haystack = " ".join(
            str(job.get(f, "")) for f in ("position", "category", "team", "overview")
        ).lower()
        if needle not in haystack:
            continue
        extracted = _extract_job(job, keyword)
        if extracted:
            results.append(extracted)
    return results


if __name__ == "__main__":
    for kw in ("quantitative", "physicist"):
        jobs = search_jane_street(kw)
        print(f"\n=== {kw!r}: found {len(jobs)} jobs ===")
        for j in jobs[:5]:
            print(j["title"], "-", j["location"], "-", j["job_type"], "-", j["salary"])
            print("  ", j["url"])
            print("  ", j["snippet"][:120])
