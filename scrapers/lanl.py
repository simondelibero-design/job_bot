"""Los Alamos National Laboratory (LANL) — careers via lanl.jobs.

LANL is a DOE national lab, contractor-operated (Triad National Security,
LLC), so USAJobs.gov doesn't cover its postings — same situation as PNNL
and LLNL.

LANL actually runs two separate career surfaces, and they behave very
differently:

- jobs.lanl.gov (Oracle iRecruitment / E-Business Suite, lands on
  "OA_HTML/IrcVisitor.jsp") is the account-required system that lanl.gov's
  own "How to Apply" page points to. A plain `requests.get` against it
  returns no page content at all — just an obfuscated JS bot-detection
  challenge (an F5-style "TSPD" cookie-issuing script) that has to run in a
  real browser before anything else loads. This is the same category of
  wall as ZipRecruiter's Cloudflare block elsewhere in this project, so per
  project convention it's not fought or spoofed — this module does not
  touch jobs.lanl.gov at all.

- lanl.jobs (a separate, modern public job-search front end at
  lanl.jobs/search/searchjobs) is NOT behind that wall, and has a real
  public JSON API behind its search box:

      https://lanl.jobs/Search/SearchResults?Keyword=<kw>&jtStartIndex=0&jtPageSize=<n>

  found by curling the search page's raw HTML, then curling the
  `JobSearchResultsTable.js` it loads and grepping for the AJAX call inside
  — no browser automation, no login. This endpoint returns every matching
  posting in one page: `jtPageSize=500` returned all ~385 open postings
  with no pagination needed for any realistic keyword-filtered result set
  (verified live 2026-08-24).

The list endpoint's fields are all HTML-wrapped in stray `<span>` tags
(stripped below) and don't include the job description, employment type,
or salary. For the `snippet` field (used for keyword scoring downstream),
this module makes one extra GET per matching posting against its detail
page (`lanl.jobs/search/jobdetails/<slug>/<id>`), which embeds a
schema.org JobPosting JSON-LD block with the full description and
`employmentType`. No populated `baseSalary` was observed on any posting
inspected, so `salary` is always None here.

The posting's own `ReferenceNumber` (e.g. "IRC145008") is used as
`source_job_id` — LANL's human-facing requisition number.

Job URL slugs are cosmetic — verified live that an arbitrary/wrong slug
still 302-redirects to the correct posting by id alone — but this module
reproduces lanl.jobs' own client-side slug algorithm (lowercase, spaces to
hyphens, strip anything else non-alphanumeric, per its
`common.min.js:convertToSlug`) anyway, for a clean direct URL instead of
relying on the redirect.

This module has been verified against live responses (2026-08-24) —
schema, keyword search, and the detail-page JSON-LD were all confirmed by
inspecting real traffic, not assumed from documentation.
"""
import json
import re

import requests

SEARCH_URL = "https://lanl.jobs/Search/SearchResults"
DETAIL_URL = "https://lanl.jobs/search/jobdetails"

_JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _slugify(title: str) -> str:
    slug = (title or "").lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9_\-]", "", slug)


def _fetch_detail(job_id: str, slug: str) -> dict:
    """Returns {"snippet": ..., "job_type": ...}; blank values on any failure
    so a single bad detail page doesn't sink the whole search."""
    try:
        resp = requests.get(f"{DETAIL_URL}/{slug}/{job_id}", timeout=15)
        resp.raise_for_status()
        match = _JSON_LD_RE.search(resp.text)
        if not match:
            return {"snippet": "", "job_type": None}
        data = json.loads(match.group(1))
        return {
            "snippet": _strip_html(data.get("description", ""))[:1000],
            "job_type": data.get("employmentType"),
        }
    except (requests.RequestException, ValueError):
        return {"snippet": "", "job_type": None}


def _extract_job(record: dict, keyword: str) -> dict | None:
    job_id = record.get("ID")
    if not job_id:
        return None

    title = _strip_html(record.get("Title", ""))
    ref_number = _strip_html(record.get("ReferenceNumber", "")) or job_id
    location = _strip_html(record.get("LocationName", ""))
    slug = _slugify(title)

    detail = _fetch_detail(job_id, slug)

    return {
        "source": "lanl",
        "source_job_id": ref_number,
        "title": title,
        "company": "Los Alamos National Laboratory",
        "location": location or None,
        "salary": None,
        "job_type": detail["job_type"],
        "url": f"{DETAIL_URL}/{slug}/{job_id}",
        "snippet": detail["snippet"],
        "search_keyword": keyword,
    }


def search_lanl(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — like PNNL, this is a single
    employer's postings, not a general job board with geographic search."""
    params = {"Keyword": keyword, "jtStartIndex": 0, "jtPageSize": 200}
    resp = requests.get(SEARCH_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for record in data.get("Records", []):
        extracted = _extract_job(record, keyword)
        if extracted:
            results.append(extracted)
    return results


if __name__ == "__main__":
    jobs = search_lanl("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("   ", j["url"])
        print("   snippet:", (j["snippet"] or "")[:150])
