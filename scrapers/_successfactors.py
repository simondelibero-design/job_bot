"""Shared helper for companies hosted on SAP SuccessFactors' "Jobs2Web"
recruiting-marketing career sites (the `j2w` JS bundle path visible in page
source, `/platform/js/j2w/...`) — confirmed live 2026-08-26 against
jobs.oxinst.com (Oxford Instruments) and careers.stratasys.com (Stratasys).
Both are plain server-rendered HTML, no login, no CAPTCHA, no JS execution
required to read the listing or detail pages.

Two different SuccessFactors template "skins" were seen across these two
tenants (same platform, different visual theme the company chose):
  - Oxford Instruments: a card/tile layout (`<li class="job-tile
    job-id-{id}" ... data-url="/job/...">`, per-field ids like
    `job-{id}-desktop-section-location-value`).
  - Stratasys: an older table layout (`<tr class="data-row">` with
    `<a class="jobTitle-link" href="/job/.../{id}/">` and a bare
    `<span class="jobLocation">`).
Both duplicate every job's markup 2-3x per page (desktop/tablet/mobile
responsive variants of the same tile), so results must be de-duplicated by
the numeric id in the job's URL. `_extract_jobs_from_listing` below handles
both skins with one pass: it finds every unique `(/job/.../{id}/, id)` pair,
then for the FIRST such href occurrence grabs the anchor text as the title,
and searches near that href (both the tile-layout's id-scoped
`-location-value` span and the table-layout's bare `jobLocation` span) for
the location text.

Load-bearing finding, confirmed live on both tenants 2026-08-26: the
search page's own `?q=` keyword parameter is NOT a real filter — it fails
silently. Requesting `?q=cryogenic` on jobs.oxinst.com and a nonsense
string like `?q=zzzznonexistentqqq` both returned the exact same 10 job
ids (verified: the two id sets are identical, not merely overlapping), and
those 10 are a strict subset of the unfiltered first page. Trusting `?q=`
would have silently produced wrong/incomplete results, so this helper does
NOT use it — instead it walks the FULL unfiltered listing (paginated via
`&startrow=N`, 25 jobs/page, stopping when a page returns fewer than 25
unique new ids or a safety cap is hit) and filters client-side on `keyword`
against the job title, same "no real server search" pattern as
_greenhouse.py/_lever.py. `location`, if given, is also a client-side
case-insensitive substring match against the tile's own location text — no
geocoding.

Each job's detail page (`{base_url}{path}`) carries a `class="jobdescription"`
block with the full posting text (server-rendered, confirmed identical
container on both tenants) — fetched here, but ONLY for jobs that already
passed the client-side keyword filter, to avoid firing a detail-page
request for every job on the board. No structured salary or employment-type
field was found anywhere in either tenant's listing or detail markup (not
merely unpopulated — grepped for "full-time"/"part-time"/"permanent" etc.
and found nothing), so both are always None here, same honest-gap
convention as mitre.py/quantinuum.py for fields that don't exist.
"""
import html
import re

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

_PAGE_SIZE = 25
_MAX_RESULTS = 300  # safety cap on pagination across the whole board
_HREF_RE = re.compile(r'href="(/job/[^"]+?/(\d+)/)"')


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _extract_jobs_from_listing(content: str) -> list[dict]:
    """Parse one listing page (either SuccessFactors template skin) into
    de-duplicated {id, path, title, location} dicts. See module docstring."""
    # Keep the raw (still HTML-entity-escaped) href for matching against
    # `content` — the attribute text in the page itself is escaped (e.g. a
    # literal "&amp;" for a title containing "&"), so searching with an
    # unescaped path would never find it. Only unescape when building the
    # value that actually leaves this function (the job's `path`/URL).
    seen_paths = {}
    for raw_path, job_id in _HREF_RE.findall(content):
        seen_paths.setdefault(job_id, raw_path)

    jobs = []
    for job_id, raw_path in seen_paths.items():
        title_match = re.search(
            r'<a[^>]*href="' + re.escape(raw_path) + r'"[^>]*>\s*([^<]+?)\s*</a>', content, re.S
        )
        title = html.unescape(title_match.group(1)).strip() if title_match else ""

        # Tile skin (Oxford Instruments): id-scoped location value.
        loc_match = re.search(
            rf'job-{job_id}-[a-z]+-section-location-value">\s*([^<]+?)\s*<', content, re.S
        )
        if not loc_match:
            # Table skin (Stratasys): bare jobLocation span near the href.
            idx = content.find(raw_path)
            window = content[idx: idx + 2000]
            loc_match = re.search(r'jobLocation[^"]*">\s*([^<]+?)\s*<', window, re.S)
        location = html.unescape(loc_match.group(1)).strip() if loc_match else None

        jobs.append({"id": job_id, "path": html.unescape(raw_path), "title": title, "location": location})
    return jobs


def _fetch_description(base_url: str, path: str) -> str:
    try:
        resp = requests.get(f"{base_url}{path}", headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return ""
    match = re.search(r'class="jobdescription">(.*?)jobmarkets', resp.text, re.S)
    if not match:
        return ""
    return _strip_html(match.group(1))[:1000]


def fetch_successfactors_jobs(base_url: str, source: str, company_name: str, keyword: str,
                               location: str = None, radius_miles: int = None) -> list[dict]:
    """Fetch a SuccessFactors "Jobs2Web" career site's full listing (all
    pages) and keyword/location-filter it client-side — see module
    docstring for why the site's own `?q=` param can't be trusted.
    `radius_miles` is accepted for interface parity but unused (no
    geocoded search on this platform)."""
    all_listings = []
    seen_ids = set()
    startrow = 0
    while len(all_listings) < _MAX_RESULTS:
        resp = requests.get(
            f"{base_url}/search/",
            headers=HEADERS,
            params={"q": "", "locationsearch": "", "startrow": startrow},
            timeout=20,
        )
        resp.raise_for_status()
        page_jobs = _extract_jobs_from_listing(resp.text)
        new_jobs = [j for j in page_jobs if j["id"] not in seen_ids]
        if not page_jobs:
            break
        for j in new_jobs:
            seen_ids.add(j["id"])
            all_listings.append(j)
        if len(page_jobs) < _PAGE_SIZE:
            break
        startrow += _PAGE_SIZE

    keyword_lower = keyword.lower()
    location_lower = location.lower() if location else None

    results = []
    for job in all_listings:
        if keyword_lower not in job["title"].lower():
            continue
        if location_lower and (not job["location"] or location_lower not in job["location"].lower()):
            continue
        results.append({
            "source": source,
            "source_job_id": job["id"],
            "title": job["title"],
            "company": company_name,
            "location": job["location"],
            "salary": None,  # no structured compensation field on this platform
            "job_type": None,  # no employment-type field found on either tenant checked
            "url": f"{base_url}{job['path']}",
            "snippet": _fetch_description(base_url, job["path"]),
            "search_keyword": keyword,
        })
    return results
