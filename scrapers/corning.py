"""Corning Incorporated — corning.com/careers / corningjobs.corning.com.

www.corning.com/careers 403s with an Akamai EdgeSuite "Access Denied" error
page — but that URL was only ever a guess (the pattern given for other
companies in this batch); a plain web search found Corning's real,
separately-hosted careers site instead: **corningjobs.corning.com**, which
loads fine (200) and is a completely different, non-Akamai-fronted host, so
no wall was crossed to reach it.

corningjobs.corning.com runs on **SAP SuccessFactors' Career Site Builder**
("job2web" — confirmed by its bundled `/platform/js/j2w/*.js` files and
image assets served from `rmkcdn.successfactors.com`), not one of the
platforms already in `ats/detect.py`. Unlike every other ATS covered in
this project so far, this one needs no JSON API reverse-engineering at
all: its search results page is plain server-rendered HTML returned from a
simple, unauthenticated GET —

    GET https://corningjobs.corning.com/search/?q=<kw>&locale=en_US&startrow=<offset>

— each result appearing as a `<tr class="data-row">` containing a
`<a class="jobTitle-link" href="/job/<slug>/<numeric-id>/">` (title +
canonical job-detail URL), plus separate `<td>` cells for location,
department, posting date, and facility. A results-count string like
`Results <b>1 – 25</b> of <b>917</b>` gives the real total; a query with no
matches (confirmed live with "physicist", 2026-08-26) simply omits the
`data-row` markup entirely rather than erroring, so the row-parsing regex
naturally returns an empty list — treated here as a real zero, not a
failure. Pagination uses `startrow=` in steps of 25 (the fixed page size),
confirmed live against the "engineer" query's 37 pages.

Confirmed live (2026-08-26): "engineer" returned 917 real matches (Lead AI
Engineer, Plant Engineering Manager, Development Engineer - Process
Industrialization, etc., across Corning's global sites); "scientist"
returned 54, heavily weighted toward materials science (Lead Scientist -
Laser Damage & Optical Materials, Sr. Scientist Surface Technology, Research
Scientist - Materials & Mechanics, Sr. Scientist Polymer Mechanics, etc. —
squarely in this project's target domain); "physicist" returned 0, a real
verified zero (Corning's postings use "scientist"/"engineer" almost
exclusively), not a broken query.

Each job's own detail page (`https://corningjobs.corning.com/job/...`) has
the full description in a `class="jobdescription"` div, fetched here for
the snippet. No structured salary or employment-type field exists anywhere
in this pipeline (neither the search rows nor the detail page expose one),
so both are always None here.

No account gate, no login, no CAPTCHA anywhere in this discovery path —
this module is discovery-only, same as the national-lab scrapers.
"""
import html as html_module
import re

import requests

BASE_URL = "https://corningjobs.corning.com"
SEARCH_URL = f"{BASE_URL}/search/"
COMPANY = "Corning Incorporated"

PAGE_SIZE = 25
MAX_RESULTS = 200  # safety cap on pagination + detail-page fetches

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": _UA}

_ROW_RE = re.compile(r'<tr class="data-row">(.*?)</tr>', re.S)
_TITLE_LINK_RE = re.compile(r'class="jobTitle-link"\s+href="([^"]+)">([^<]*)</a>')
_LOCATION_RE = re.compile(r'<span class="jobLocation">\s*([^<]+?)\s*</span>')
_TOTAL_RE = re.compile(r'of <b>(\d+)</b>')
_DESC_RE = re.compile(r'class="jobdescription"[^>]*>(.*?)</div>\s*</div>', re.S)


def _strip_html(text: str) -> str:
    return html_module.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_snippet(url: str) -> str:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return ""
    match = _DESC_RE.search(resp.text)
    if not match:
        return ""
    return _strip_html(match.group(1))[:1000]


def _extract_job(row_html: str, keyword: str) -> dict | None:
    title_match = _TITLE_LINK_RE.search(row_html)
    if not title_match:
        return None
    rel_url, title = title_match.groups()
    url = f"{BASE_URL}{rel_url}"

    # The numeric trailing path segment is this platform's stable job id
    # (e.g. "/job/Obispado-Lead-AI-Engineer-NLE-64060/1407490700/" -> the
    # "1407490700") — there's no separate structured id field in the row.
    id_match = re.search(r"/(\d+)/?$", rel_url)
    job_id = id_match.group(1) if id_match else rel_url

    location_match = _LOCATION_RE.search(row_html)

    return {
        "source": "corning",
        "source_job_id": job_id,
        "title": html_module.unescape(title.strip()),
        "company": COMPANY,
        "location": html_module.unescape(location_match.group(1)) if location_match else None,
        "salary": None,  # no structured compensation field anywhere in this pipeline
        "job_type": None,  # no employment-type field either — only a department/facility, not a fit for this
        "url": url,
        "snippet": _fetch_snippet(url),
        "search_keyword": keyword,
    }


def search_corning(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — this career site's search box is
    keyword-only; location filtering here happens via separate facet
    checkboxes on the page, not a query param this scraper drives."""
    all_results = []
    startrow = 0
    total = None
    while total is None or (startrow < min(total, MAX_RESULTS)):
        resp = requests.get(
            SEARCH_URL,
            headers=_HEADERS,
            params={"q": keyword, "locale": "en_US", "startrow": startrow},
            timeout=20,
        )
        resp.raise_for_status()
        page_html = resp.text

        if total is None:
            total_match = _TOTAL_RE.search(page_html)
            total = int(total_match.group(1)) if total_match else 0

        rows = _ROW_RE.findall(page_html)
        if not rows:
            break

        for row_html in rows:
            extracted = _extract_job(row_html, keyword)
            if extracted:
                all_results.append(extracted)

        startrow += PAGE_SIZE

    return all_results


if __name__ == "__main__":
    jobs = search_corning("scientist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
