"""Lawrence Berkeley National Laboratory (LBNL / "Berkeley Lab") — jobs.lbl.gov.

LBNL is a DOE Office of Science national lab, managed for DOE by the
University of California (not a typical for-profit contractor like most
other labs in this project), so USAJobs.gov doesn't cover its postings —
same situation as PNNL/ANL/LANL/etc.

jobs.lbl.gov runs on an old talent-community platform (internal branding
"TVAPP", cookie names like `ORA_OTSS_SESSION_ID` suggest an Oracle-hosted
SelectMinds-style system — NOT one of the platforms already documented in
this project: not Workday, not iCIMS, not SmartRecruiters, not Oracle
Fusion Cloud Recruiting). It does NOT have a plain public JSON API the way
PNNL/LANL do:

- The static server-rendered HTML at `/jobs/search/<id>` only ever embeds a
  fixed "10 most recently posted" promo widget — it is NOT the actual
  filtered listing, confirmed by diffing curl output against a real
  browser session.
- The real, keyword-filterable listing is loaded through an internal AJAX
  endpoint (`/ajax/content/job_results?JobSearch.id=<search_id>&page_index=<n>...`)
  that returns an HTML fragment, not JSON — and it 401s
  (`{"Status":"APP_ERROR","Errors":{"GENERIC_ERROR_STRING":"NotLoggedIn"}}`)
  unless called with a live anonymous session that has already completed a
  handshake of several other `/ajax/content/*` calls the page fires on
  load (`login_content`, `key_content`, `process-browser-locale`, etc.).
  Reproducing that handshake with plain `requests` would mean reverse
  engineering an undocumented internal session protocol; not attempted.
  Additionally, subresources (`site_css`, `LAB.min.js`, `js-dict`) return
  403 when requested by a fresh/cold Playwright context before that same
  handshake completes, even though the exact same URLs return 200 via
  plain curl or an already-warmed browser session — another sign this is
  session/cookie-gated, not a public API.
- Typing a keyword and pressing Enter in a real browser session fires
  `POST /ajax/jobs/search/create` (creates a new `JobSearch.id`) followed by
  `GET /ajax/content/job_results?JobSearch.id=<new_id>&page_index=1...`,
  and the returned HTML fragment is genuinely keyword-filtered (verified
  live: searching "physicist" correctly narrowed 60 open positions down to
  4 matching ones with different req IDs).

Because a working keyword search only exists behind real browser/session
state, this module drives an actual headless Chromium session with
Playwright (same fallback pattern as indeed.py) rather than reverse
engineering the AJAX handshake: navigate to the search page, type the
keyword into the visible search box (`#keyword`), press Enter, then parse
the resulting `div.job_list_row` cards (title link `a.job_link`, division
`p.jlr_company`, `span.location`, `span.category`, description
`p.jlr_description`) directly from the live DOM. Pages forward via the
`a[data-page="N"]` pagination control up to `max_pages`.

No job card or individual job detail page inspected exposes a structured
salary or employment-type field (Berkeley Lab, like most UC-managed labs,
doesn't publish comp ranges on postings), so `salary` and `job_type` are
always None here — same honest-gap pattern as ames.py/lanl.py.

`source_job_id` is the lab's own requisition number, taken from the job
card's `id="job_list_<id>"` attribute (confirmed to match the trailing
numeric suffix on the posting's own URL slug).

This module has been verified against live browser sessions (2026-08-26) —
keyword filtering, job card markup, and pagination were all confirmed by
driving a real headless session, not assumed from documentation.
"""
import re

from playwright.sync_api import sync_playwright

SEARCH_URL = "https://jobs.lbl.gov/jobs/search/10811416"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _extract_card(card) -> dict | None:
    row_id = card.get_attribute("id") or ""
    match = re.search(r"(\d+)$", row_id)
    source_job_id = match.group(1) if match else None

    title_el = card.query_selector("a.job_link")
    if not title_el or not source_job_id:
        return None

    company_el = card.query_selector("p.jlr_company")
    location_el = card.query_selector("span.location")
    category_el = card.query_selector("span.category")
    desc_el = card.query_selector("p.jlr_description")

    division = _clean(company_el.text_content() if company_el else None)

    return {
        "source": "lbnl",
        "source_job_id": source_job_id,
        "title": _clean(title_el.text_content()),
        "company": "Lawrence Berkeley National Laboratory" + (f" ({division})" if division else ""),
        "location": _clean(location_el.text_content() if location_el else None),
        "salary": None,  # not exposed on any card or detail page inspected
        "job_type": None,  # not exposed in structured form on any card inspected
        "url": title_el.get_attribute("href"),
        "snippet": (_clean(desc_el.text_content() if desc_el else None) or "")[:1000],
    }


def search_lbnl(keyword: str, location: str = None, radius_miles: int = None,
                 max_pages: int = 3, headless: bool = True) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — LBNL is a single-site employer
    (Berkeley, CA / "Bay Area") inside its own careers platform, not a
    general job board with geographic search.
    """
    results = []
    seen_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000)
        # Let the page's own session-bootstrap AJAX calls (login_content,
        # key_content, process-browser-locale, etc.) finish before touching
        # the search box — those establish the session state the keyword
        # search's own AJAX call depends on.
        page.wait_for_timeout(4000)

        page.click("#keyword")
        page.type("#keyword", keyword, delay=100)
        page.keyboard.press("Enter")
        page.wait_for_timeout(3000)

        for page_num in range(1, max_pages + 1):
            cards = page.query_selector_all("div.job_list_row")
            if not cards:
                break

            for card in cards:
                job = _extract_card(card)
                if job and job["source_job_id"] not in seen_ids:
                    seen_ids.add(job["source_job_id"])
                    job["search_keyword"] = keyword
                    results.append(job)

            next_link = page.query_selector(f'a[data-page="{page_num + 1}"]')
            if not next_link or not next_link.is_visible():
                break
            try:
                next_link.click(timeout=5000)
            except Exception:
                break
            page.wait_for_timeout(2500)

        browser.close()

    return results


if __name__ == "__main__":
    jobs = search_lbnl("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("   snippet:", (j["snippet"] or "")[:150])
