"""Two Sigma — twosigma.com/careers (job board actually lives on
careers.twosigma.com).

Not on any ATS platform this project already recognizes (no myworkdayjobs/
icims/greenhouse/lever/smartrecruiters/eightfold/ashbyhq marker anywhere)
— confirmed live 2026-08-26 by grepping the twosigma.com/careers/ page,
which is plain WordPress marketing content with no job data, then
following its careers.twosigma.com link. That subdomain's page source
embeds `avature.wizard.registrars` — Two Sigma runs on **Avature**, a real
enterprise ATS not previously seen in this codebase (distinct from every
platform in ats/detect.py's PLATFORM_PATTERNS).

Unlike a typical Avature-behind-JS-widget setup, careers.twosigma.com's
`/careers/OpenRoles` search page is genuinely server-side rendered — a
plain `requests.get` (no Playwright, no JS execution) returns full HTML
with real `<article class="article article--result">` job cards already
present, each carrying: title + full JobDetail URL (with a numeric
Avature requisition id as its final URL segment), and three
`paragraph_inner-span` text fields in a fixed order — location, department,
and employment/experience category (e.g. "Early Careers", "Experienced",
"Internship"). Confirmed live: no bot-wall, no CAPTCHA, no login gate on
this search path (login IS required elsewhere on the site — e.g.
`/careers/Login` — but never for browsing/searching open roles).

**Real server-side keyword search exists**, unlike Greenhouse/Lever/most
other sources here: the page's own search form has a text field
(`id="5083"`, `name="search"`) that Avature accepts as a plain GET query
param — confirmed live: `?search=quantitative` returns real filtered
results (10+), `?search=physicist` returns Avature's own literal
"No jobs found" state (a genuine, server-confirmed zero, not a bug in this
module). Pagination is a separate `jobOffset` GET param, confirmed to
return a disjoint set of postings when combined with `search` (checked by
diffing requisition ids between offset 0 and offset 10 on `search=engineer`
— zero overlap). Page size is fixed at 10 server-side; a `jobRecordsPerPage`
param exists in Avature's own "next page" links but was confirmed live to
have no effect on the actual page size returned (tested up to 500), so
this module just pages via `jobOffset` in the fixed 10-per-page stride
instead of trying to widen it.

**Location filtering is NOT free-text** — Avature's location field
(`id="5084"`, `name="5084[]"`) is a `CheckBoxListFormField`/autocomplete
facet requiring one of Avature's own location facet values, not a city
string a caller could construct from a US address the way ClearanceJobs'
`city` facet works. Reproducing the facet id list wasn't attempted (out of
scope for this project's effort budget, per the same judgment call
general_dynamics.py's docstring makes about a different unresolved
Avature/GD-search quirk) — `location`, if given, is instead matched
client-side as a case-insensitive substring against the location text each
result already carries.

No structured salary field appears anywhere in either the search-results
markup or the job detail page's field list, so `salary` is always None.
The job detail page (fetched once per result for a real description, same
pattern as boeing.py/draper.py) renders its content as a flat sequence of
labeled/unlabeled `article__content__view__field__value` divs — title,
location, country, business, function, experience level, then one final
long unlabeled div holding the actual job description; this module takes
the longest such value on the page as the snippet rather than relying on
a specific label, since the description is the only field long enough to
plausibly be confused with by a `[:1000]` truncation and every other field
observed live was a short one-line facet value.

Verified live 2026-08-26 against `careers.twosigma.com`: "quantitative"
returned 10 jobs on page 1 alone (Quantitative Researcher — Intern,
Quantitative Researcher — Experienced Hire, Quantitative Software Engineer,
etc., all real current New York postings); "physicist" returned Avature's
own "No jobs found" (verified zero).
"""
import html
import re

import requests

SEARCH_URL = "https://careers.twosigma.com/careers/OpenRoles"
COMPANY_NAME = "Two Sigma"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

PAGE_SIZE = 10  # fixed server-side; jobRecordsPerPage was confirmed live to have no effect
MAX_RESULTS = 100  # safety cap on pagination + detail-page fetches

_ARTICLE_RE = re.compile(
    r'<article class="article article--result"[^>]*>(.*?)</article>', re.S
)
_LINK_RE = re.compile(r'<a class="link" href="([^"]+)">\s*([^<]+?)\s*</a>', re.S)
_SPAN_RE = re.compile(r'paragraph_inner-span">([^<]+)</span>')
_ID_RE = re.compile(r"/(\d+)$")
_FIELD_RE = re.compile(
    r'<div class="article__content__view__field[^"]*">\s*'
    r'(?:<div class="article__content__view__field__label">\s*([^<]+?)\s*</div>)?\s*'
    r'<div class="article__content__view__field__value">(.*?)</div>\s*</div>',
    re.S,
)


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _fetch_snippet(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return ""
    values = [_strip_html(v) for _, v in _FIELD_RE.findall(resp.text)]
    return max(values, key=len, default="")[:1000]


def _extract_job(article_html: str, keyword: str, fetch_detail: bool) -> dict | None:
    link_match = _LINK_RE.search(article_html)
    if not link_match:
        return None  # the Avature "No jobs found" placeholder article has no link
    url, title = link_match.group(1), link_match.group(2).strip()

    id_match = _ID_RE.search(url)
    job_id = id_match.group(1) if id_match else url

    spans = _SPAN_RE.findall(article_html)
    location = spans[0] if len(spans) > 0 else None
    department = spans[1] if len(spans) > 1 else None
    job_type = spans[2] if len(spans) > 2 else None

    snippet = _fetch_snippet(url) if fetch_detail else ""
    if department:
        snippet = f"[{department}] {snippet}".strip()

    return {
        "source": "two_sigma",
        "source_job_id": job_id,
        "title": title,
        "company": COMPANY_NAME,
        "location": location,
        "salary": None,  # no structured compensation field found anywhere on this board
        "job_type": job_type,
        "url": url,
        "snippet": snippet[:1000],
        "search_keyword": keyword,
    }


def search_two_sigma(keyword: str, location: str = None, radius_miles: int = None,
                      fetch_descriptions: bool = True) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location`, if given, is matched
    client-side as a substring against each result's location text — see
    module docstring for why Avature's own location facet isn't used
    directly. `fetch_descriptions` (default True) controls whether each
    result's detail page is fetched for a real snippet; set False to skip
    those extra requests for a faster, snippet-less search."""
    location_lower = location.lower() if location else None

    results = []
    offset = 0
    while len(results) < MAX_RESULTS:
        resp = requests.get(
            SEARCH_URL, headers=HEADERS,
            params={"search": keyword, "jobOffset": offset},
            timeout=20,
        )
        resp.raise_for_status()

        articles = _ARTICLE_RE.findall(resp.text)
        if not articles:
            break

        page_had_job = False
        for article_html in articles:
            job = _extract_job(article_html, keyword, fetch_detail=fetch_descriptions)
            if not job:
                continue
            page_had_job = True
            if location_lower and location_lower not in (job["location"] or "").lower():
                continue
            results.append(job)

        if not page_had_job:
            break  # hit Avature's "No jobs found" placeholder article
        offset += PAGE_SIZE

    return results[:MAX_RESULTS]


if __name__ == "__main__":
    for kw in ("quantitative", "physicist"):
        jobs = search_two_sigma(kw)
        print(f"\n=== {kw!r}: found {len(jobs)} jobs ===")
        for j in jobs[:5]:
            print(j["title"], "-", j["location"], "-", j["job_type"])
            print("  ", j["url"])
            print("  ", j["snippet"][:150])
