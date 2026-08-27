"""nLIGHT — nlight.net/careers.

The careers page is a Squarespace site that embeds a Jobvite widget via a
raw code block (`<div class="jv-careersite" data-careersite="nlight"
data-force-redirect></div>`, found by grepping the page HTML for
"jobvite") — Jobvite is not one of the ATS platforms already known to
`ats/detect.py`. That `data-careersite="nlight"` slug redirects to
Jobvite's own hosted career site:

    GET https://jobs.jobvite.com/nlight/jobs

Unlike every JS-SPA ATS elsewhere in this project, this page is genuinely
server-rendered — the full open-positions list (68 postings, grouped by
department, confirmed live 2026-08-26) is right there in the initial HTML
as plain `<table class="jv-job-list">` rows, no API call or JS execution
needed to read it. Each job's detail page
(`jobs.jobvite.com/nlight/job/<id>`) is also server-rendered and embeds a
`schema.org/JobPosting` JSON-LD block with `employmentType`, `jobLocation`,
and the full HTML `description` — parsed here instead of the human-facing
HTML around it since it's already structured.

`baseSalary` exists as a key in that JSON-LD but is always empty
(`minValue`/`maxValue`/`currency` all `""`) on every posting checked —
Jobvite emits the key unconditionally as part of its schema, not because
nLIGHT populates it. Some postings do put real numbers in the free-text
description instead (e.g. "Compensation: $100,000-$150,000 depending on
experience" on a live "Electrical Engineer" posting), so `salary` is
regex-extracted from the description text when present, same approach as
northrop_grumman.py's `_SALARY_RE`, rather than trusting the always-empty
structured field.

No free-text/keyword search exists on the listing page itself — it's a
static grouped list, not a search form — so this scraper fetches the full
listing once and filters client-side against the title (matching
aps.py/anl.py's pattern for a small single-employer board), then only
fetches the JSON-LD detail page for postings that already matched, to keep
request volume down.

Verified live 2026-08-26: 68 total postings; "engineer" matched several
real listings (Electrical Engineer, Electro-Optical Engineer,
Electro-Optical Software Engineer, etc., mostly Camas WA / Longmont CO).
"""
import html
import json
import re

import requests

CAREERSITE = "nlight"
LISTING_URL = f"https://jobs.jobvite.com/{CAREERSITE}/jobs"
JOB_PAGE_BASE = f"https://jobs.jobvite.com/{CAREERSITE}/job"
COMPANY = "nLIGHT"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA}

_JOB_LINK_RE = re.compile(r'href="/' + CAREERSITE + r'/job/([A-Za-z0-9]+)">([^<]+)</a>')
_JSONLD_RE = re.compile(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', re.S)
_SALARY_RE = re.compile(r"Compensation:\s*(\$[\d,]+\s*-\s*\$[\d,]+)", re.I)


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_detail(job_id: str) -> dict:
    """Returns {"snippet", "salary", "job_type", "location"}; blank/None
    values on any failure so one bad detail page doesn't sink the search."""
    try:
        resp = requests.get(f"{JOB_PAGE_BASE}/{job_id}", headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        match = _JSONLD_RE.search(resp.text)
        if not match:
            return {"snippet": "", "salary": None, "job_type": None, "location": None}
        data = json.loads(match.group(1))
        desc_html = data.get("description", "")
        desc_text = _strip_html(desc_html)
        salary_match = _SALARY_RE.search(desc_text)

        locs = data.get("jobLocation") or []
        loc_parts = []
        for loc in locs:
            addr = (loc or {}).get("address") or {}
            city = addr.get("addressLocality")
            region = addr.get("addressRegion")
            if city and region:
                loc_parts.append(f"{city}, {region}")
            elif city:
                loc_parts.append(city)

        return {
            "snippet": desc_text[:1000],
            "salary": salary_match.group(1) if salary_match else None,
            "job_type": data.get("employmentType"),
            "location": "; ".join(loc_parts) if loc_parts else None,
        }
    except (requests.RequestException, ValueError):
        return {"snippet": "", "salary": None, "job_type": None, "location": None}


def search_nlight(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — nLIGHT's Jobvite listing page has
    no search or location-filter form, just a static grouped list, so
    filtering happens client-side against the title."""
    resp = requests.get(LISTING_URL, headers=_HEADERS, timeout=20)
    resp.raise_for_status()

    keyword_lower = keyword.lower()
    results = []
    for job_id, title in _JOB_LINK_RE.findall(resp.text):
        if keyword_lower not in title.lower():
            continue
        detail = _fetch_detail(job_id)
        results.append({
            "source": "nlight",
            "source_job_id": job_id,
            "title": title,
            "company": COMPANY,
            "location": detail["location"],
            "salary": detail["salary"],
            "job_type": detail["job_type"],
            "url": f"{JOB_PAGE_BASE}/{job_id}",
            "snippet": detail["snippet"],
            "search_keyword": keyword,
        })
    return results


if __name__ == "__main__":
    jobs = search_nlight("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["salary"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
