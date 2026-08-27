"""The D. E. Shaw group — deshaw.com/careers.

Not on any ATS platform this project already recognizes (no myworkdayjobs/
icims/greenhouse/lever/smartrecruiters/eightfold/ashbyhq marker anywhere) —
confirmed live 2026-08-26 that deshaw.com/careers is a Next.js site whose
server-rendered page embeds the *entire* job listing dataset directly in
its own `<script id="__NEXT_DATA__" type="application/json">` tag —
exactly the pattern scrapers/clearancejobs.py documents (a real backend
JSON response baked verbatim into SSR HTML), except here it's Next.js's
own `getServerSideProps`/`getStaticProps` payload rather than a
Vike/vite-plugin-ssr `pageContext` blob. One plain `requests.get` on the
single careers page returns everything; no separate API call, no
Playwright, no bot-wall or login gate encountered anywhere in this path.

`props.pageProps` on that page carries several distinct job lists:
  - `regularJobs` (77 live 2026-08-26) — the general open-to-everyone
    posting list, covers experienced hires and full-time roles.
  - `internships` (11 live) — student/summer postings, same schema as
    regularJobs, genuinely open (unlike Jane Street's like-named-but-all-
    closed `internships.json` file — checked here too, and these actually
    have `activeOnJobsListing: true`).
  - `internalJobs` (83 live) — deliberately excluded: every one of these
    reads as a current-employee-only internal transfer/mobility posting
    (the key name itself signals this, and pairing it with the public
    "Careers" page's own external candidate flow would misrepresent
    postings this project's user could actually apply to). Only
    `regularJobs` + `internships` are combined here.

Per-job fields (from each entry's nested `data` object): `id`, `displayName`
(title), `jobUrl` (a Title-Case slug — the site's own rendered `<a href>`
links use the same slug lowercased, confirmed live, so this module
lowercases it to build the real URL), `jobDescription.websiteDescription`
+ `.responsibilitiesHtml` (both feed the snippet), and `jobMetadata.
jobLocations` (a list of `{name, abbreviation}` — joined with "; " when a
posting spans more than one office, e.g. some roles list both "New York"
and "Denver"). `jobMetadata.workStatus` (e.g. "Regular Full-Time") doubles
as `job_type`; it was confirmed live to equal the job's own top-level
`status` field on every entry checked, so only one is used.

No structured salary field exists anywhere in this payload (not merely
unpopulated — no such key appears in the schema at all, confirmed by
inspecting every key on several full job records), so `salary` is always
None here — same honest-gap situation as anl.py/bnl.py/mitre.py.

No server-side keyword search exists (this is the full current listing
embedded once, not a paginated API), so filtering is client-side against
title + description + responsibilities text, same pattern as Greenhouse/
Lever's shared helpers and jane_street.py.

Verified live 2026-08-26: 88 total open external postings (77 regular + 11
internship); "quantitative" matched several real postings (Quantitative
Strategies roles); "physicist"/"physics" and "engineer" also checked live
and returned real, non-empty results for "engineer" (D. E. Shaw runs
significant Software Development and Technology postings).
"""
import html
import re

import requests

CAREERS_URL = "https://www.deshaw.com/careers"
COMPANY_NAME = "The D. E. Shaw group"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _format_location(job_metadata: dict) -> str | None:
    locations = job_metadata.get("jobLocations") or []
    names = [loc.get("name") for loc in locations if loc.get("name")]
    return "; ".join(names) if names else None


def _extract_job(entry: dict, keyword: str) -> dict | None:
    job = entry.get("data") or {}
    job_id = job.get("id")
    job_url_slug = job.get("jobUrl")
    if not job_id or not job_url_slug:
        return None

    desc = job.get("jobDescription") or {}
    snippet_parts = [
        _strip_html(desc.get("websiteDescription", "")),
        _strip_html(desc.get("responsibilitiesHtml") or desc.get("responsibilities") or ""),
    ]
    snippet = " ".join(p for p in snippet_parts if p)[:1000]

    metadata = job.get("jobMetadata") or {}

    return {
        "source": "deshaw",
        "source_job_id": str(job_id),
        "title": job.get("displayName", ""),
        "company": COMPANY_NAME,
        "location": _format_location(metadata),
        "salary": None,  # no salary key anywhere in this API's schema
        "job_type": job.get("status") or metadata.get("workStatus"),
        "url": f"{CAREERS_URL}/{job_url_slug.lower()}",
        "snippet": snippet,
        "search_keyword": keyword,
    }


def search_deshaw(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — this is a single embedded
    listing with no server-side geographic filter; matching is purely by
    keyword, same as jane_street.py."""
    resp = requests.get(CAREERS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    match = _NEXT_DATA_RE.search(resp.text)
    if not match:
        return []
    import json
    data = json.loads(match.group(1))
    props = data.get("props", {}).get("pageProps", {})

    all_entries = (props.get("regularJobs") or []) + (props.get("internships") or [])

    needle = keyword.lower()
    results = []
    for entry in all_entries:
        job = entry.get("data") or {}
        if not job.get("activeOnJobsListing", True):
            continue
        desc = job.get("jobDescription") or {}
        haystack = " ".join([
            job.get("displayName", ""),
            desc.get("websiteDescription") or "",
            desc.get("responsibilities") or "",
        ]).lower()
        if needle not in haystack:
            continue
        extracted = _extract_job(entry, keyword)
        if extracted:
            results.append(extracted)
    return results


if __name__ == "__main__":
    for kw in ("quantitative", "engineer", "physicist"):
        jobs = search_deshaw(kw)
        print(f"\n=== {kw!r}: found {len(jobs)} jobs ===")
        for j in jobs[:5]:
            print(j["title"], "-", j["location"], "-", j["job_type"])
            print("  ", j["url"])
            print("  ", j["snippet"][:150])
