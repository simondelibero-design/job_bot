"""Ouster, Inc. (LIDAR, merged with Velodyne in 2023) — ouster.com/company/careers.

ouster.com/company/careers is a Next.js marketing page whose "View All Jobs"
link points at a separate hosted board: **ouster.applytojob.com/apply**
(found by grepping the marketing page HTML for career/job hrefs). That
domain and the page's own markup (`resumator-jobboard-home` body class,
`DV_S3_BUCKET_NAME = "resumator"`, `#resumator-*` element ids) identify the
platform as **JazzHR** (formerly "The Resumator" — `applytojob.com` is
JazzHR's public job-board hosting domain), which is not one of the ATS
platforms `ats/detect.py` already knows and has no documented public JSON
API the way Greenhouse/Lever do.

Confirmed live 2026-08-26: a plain `requests.get` (desktop UA, no
cookies/session/JS) on the board's root page returns HTTP 200 with the full
current openings list **server-rendered directly into the HTML** — no XHR,
no bot-detection, no login. All 27 open postings render on one page (no
pagination markup found), each as an
`<li class="list-group-item">` containing a title link
(`href="https://ouster.applytojob.com/apply/<job-code>/<title-slug>"`) and a
location `<li>`. Verified titles included "Mechanical Engineer",
"Senior Electrical Engineer", "Sr. Data Infrastructure & Quality Engineer"
(San Francisco, CA) and "Senior Cost Accountant" (Bangkok, Thailand) — a
real, current, geographically varied board, not a stub.

No server-side keyword or location search parameter exists on this board
(no `<form>`/query-string search found on the listing page) — filtering
happens client-side against title + department, same pattern as
scrapers/_greenhouse.py for single-employer boards with no search API.

Each job's own detail page (fetched here for the description snippet) also
carries a real employment-type field
(`<div id='resumator-job-employment' title="Type">Full Time</div>`), used
for `job_type`; no salary field exists anywhere on either page, so `salary`
is always None, same honest-gap situation as the Greenhouse/Lever helpers.
"""
import html as html_lib
import re

import requests

BOARD_URL = "https://ouster.applytojob.com/apply"
COMPANY = "Ouster, Inc."

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

_LIST_RE = re.compile(
    r"<a href=\"(https://ouster\.applytojob\.com/apply/([^/\"]+)/[^\"]+)\">"
    r"\s*([^<]+?)\s*</a>\s*</h3>\s*<ul[^>]*>\s*"
    r"<li><i class='fa fa-map-marker'></i>([^<]*)</li>"
)
_EMPLOYMENT_RE = re.compile(
    r"id='resumator-job-employment'[^>]*>\s*<i[^>]*></i>\s*([^<]+?)\s*</div>"
)
_DESCRIPTION_RE = re.compile(
    r'id="job-description">(.*?)</div>\s*</div>', re.S
)


def _strip_html(text: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_detail(url: str) -> dict:
    """Returns {"snippet": ..., "job_type": ...}; blanks on any failure so
    one bad detail page doesn't sink the whole search."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return {"snippet": "", "job_type": None}

    desc_match = _DESCRIPTION_RE.search(resp.text)
    employment_match = _EMPLOYMENT_RE.search(resp.text)
    return {
        "snippet": _strip_html(desc_match.group(1))[:1000] if desc_match else "",
        "job_type": html_lib.unescape(employment_match.group(1)).strip() if employment_match else None,
    }


def search_ouster(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location`, if given, is a client-side
    case-insensitive substring match against the listing's location text —
    no geocoding, no server-side location param exists on this board."""
    resp = requests.get(BOARD_URL, headers=_HEADERS, timeout=20)
    resp.raise_for_status()

    keyword_lower = keyword.lower()
    location_lower = location.lower() if location else None

    results = []
    for url, job_code, title, job_location in _LIST_RE.findall(resp.text):
        title = html_lib.unescape(title).strip()
        job_location = html_lib.unescape(job_location).strip()

        if keyword_lower not in title.lower():
            continue
        if location_lower and location_lower not in job_location.lower():
            continue

        detail = _fetch_detail(url)
        results.append({
            "source": "ouster",
            "source_job_id": job_code,
            "title": title,
            "company": COMPANY,
            "location": job_location or None,
            "salary": None,  # no salary field anywhere on this board
            "job_type": detail["job_type"],
            "url": url,
            "snippet": detail["snippet"],
            "search_keyword": keyword,
        })
    return results


if __name__ == "__main__":
    jobs = search_ouster("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
