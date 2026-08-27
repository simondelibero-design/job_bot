"""Bluefors (dilution refrigerators / cryostats for quantum computing labs) —
bluefors.com/careers.

bluefors.com/careers redirects to bluefors.com/people/ (a marketing page,
not a job board itself); it links out to `careers.bluefors.com`, which runs
on **Teamtailor** (identified from `assets-aws.teamtailor-cdn.com` script
tags and a `content-security-policy: frame-ancestors 'self'
app.teamtailor.com` response header — confirmed live 2026-08-26) — not one
of the ATS platforms already known to `ats/detect.py`. Not a Finland/EU-
hosted job board quirk like Quantinuum's Lever board (see
scrapers/quantinuum.py) — Teamtailor doesn't split by data-region the same
way; the standard `careers.{company}.com` custom domain is all there is.

`careers.bluefors.com/jobs` is a real, plain, server-rendered HTML listing
— no login, no CAPTCHA, no JS execution required (confirmed by a bare curl
GET with no cookies returning the full 20-job first page). It carries a
"27 jobs" total count and paginates via a Turbo-Stream partial-page
endpoint: `careers.bluefors.com/jobs/show_more?page=2` (confirmed live:
returns an `<turbo-stream action="append">` fragment with 7 more `<li>`
job entries, same markup shape as page 1's list items). This helper walks
that pagination fully rather than trusting the site's own `?query=`
search param, since (unlike the Jobs2Web platform in _successfactors.py)
Teamtailor's `?query=` DID appear to genuinely filter when spot-checked
(`?query=engineer` returned a plausible, smaller, relevant subset) — but
matching this project's other Teamtailor-adjacent helpers' caution, and
since the full board is small (27 postings), this fetches everything and
filters client-side on title, avoiding any dependency on undocumented
server-search behavior.

Each job's own page (`careers.bluefors.com/jobs/{id}-{slug}`) embeds a
schema.org `JobPosting` JSON-LD block with real structured fields:
`identifier.value` (matches the numeric id in the URL), `employmentType`
(e.g. "FULL_TIME"), `datePosted`, and `jobLocation[0].address`
(`addressLocality` + `addressCountry`; remote roles additionally carry
`jobLocationType: "TELECOMMUTE"`). `description` in that JSON-LD is
HTML markup that's itself HTML-entity-escaped (e.g. literal `&lt;p&gt;`
text), so it needs `html.unescape` before AND after stripping tags to come
out clean — confirmed live 2026-08-26 against job 8055772 (Cryogenic R&D
Engineer, Syracuse, NY).

No structured salary field exists anywhere in this pipeline (list page or
JSON-LD), matching what a human sees on the page — `salary` is always None.

Verified live 2026-08-26: 27 total open postings across Syracuse NY,
Espoo FI, and various remote/field-service roles; "cryogenic" and
"engineer" both returned real, relevant matches (Cryogenic R&D Engineer,
Cryo Engineer, Resident Cryogenic Engineer, Service Engineer, etc.).
"""
import html
import json
import re

import requests

BASE_URL = "https://careers.bluefors.com"
COMPANY = "Bluefors"

_PAGE_SIZE = 20  # confirmed live: page 1 of /jobs carries 20 entries
_MAX_PAGES = 10  # safety cap (27 postings / 20 per page = 2 pages today)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

_JOB_ITEM_RE = re.compile(
    r'href="(https://careers\.bluefors\.com/jobs/(\d+)-[a-z0-9-]*)"\s*>'
    r'\s*<span[^>]*></span>\s*([^<]+?)\s*</a>',
    re.S,
)
_LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>\s*(\{.*?"@type":\s*"JobPosting".*?\})\s*</script>',
    re.S,
)


def _strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_listing_page(page: int) -> str:
    if page == 1:
        resp = requests.get(f"{BASE_URL}/jobs", headers=HEADERS, timeout=20)
    else:
        resp = requests.get(f"{BASE_URL}/jobs/show_more", headers=HEADERS,
                             params={"page": page}, timeout=20)
    resp.raise_for_status()
    return resp.text


def _list_all_jobs() -> list[dict]:
    seen_ids = set()
    jobs = []
    for page in range(1, _MAX_PAGES + 1):
        content = _fetch_listing_page(page)
        matches = _JOB_ITEM_RE.findall(content)
        if not matches:
            break
        new_count = 0
        for url, job_id, title in matches:
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            new_count += 1
            jobs.append({"id": job_id, "url": url, "title": html.unescape(title).strip()})
        if new_count < _PAGE_SIZE:
            break
    return jobs


def _fetch_detail(url: str) -> dict | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    match = _LD_JSON_RE.search(resp.text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _format_location(job_posting: dict) -> str | None:
    locations = job_posting.get("jobLocation") or []
    if not locations:
        return None
    address = (locations[0] or {}).get("address") or {}
    city = address.get("addressLocality")
    country = address.get("addressCountry")
    parts = [p for p in (city, country) if p]
    location = ", ".join(parts) if parts else None
    if job_posting.get("jobLocationType") == "TELECOMMUTE" and location:
        location = f"{location} (Remote)"
    return location


def search_bluefors(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused — no geocoded radius search here.
    `location` is a client-side case-insensitive substring match against
    the job's JSON-LD address (city/country/remote note)."""
    keyword_lower = keyword.lower()
    location_lower = location.lower() if location else None

    matched = [j for j in _list_all_jobs() if keyword_lower in j["title"].lower()]

    results = []
    for job in matched:
        posting = _fetch_detail(job["url"])
        job_location = _format_location(posting) if posting else None
        if location_lower and (not job_location or location_lower not in job_location.lower()):
            continue
        results.append({
            "source": "bluefors",
            "source_job_id": job["id"],
            "title": job["title"],
            "company": COMPANY,
            "location": job_location,
            "salary": None,  # no structured compensation field anywhere in this pipeline
            "job_type": (posting or {}).get("employmentType"),
            "url": job["url"],
            "snippet": _strip_html((posting or {}).get("description", ""))[:1000],
            "search_keyword": keyword,
        })
    return results


if __name__ == "__main__":
    jobs = search_bluefors("cryogenic")
    print(f"Found {len(jobs)} jobs for 'cryogenic'")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])

    print()
    jobs = search_bluefors("engineer")
    print(f"Found {len(jobs)} jobs for 'engineer'")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"])
