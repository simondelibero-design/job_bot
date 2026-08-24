"""Sandia National Laboratories (SNL) — careers.sandia.gov / cg.sandia.gov.

SNL is a DOE national lab, contractor-operated (NTESS), so USAJobs.gov
doesn't cover its postings — same situation as PNNL and ORNL (see
scrapers/pnnl.py, scrapers/ornl.py). Unlike either of those, Sandia's
"careers" site (www.sandia.gov/careers/jobs-app/) is a thin redirect into a
full **Oracle PeopleSoft Fluid HCM "Candidate Gateway"** instance at
cg.sandia.gov — the same enterprise HR system used by many universities and
government contractors, not a modern web stack.

What was checked, live, on 2026-08-24, before settling on this approach:
- No JSON API. Network inspection while running a keyword search shows the
  search box submits a POST back to the *same* URL
  (`HRS_HRAM_FL.HRS_CG_SEARCH_FL.GBL`) that returns `text/xml` — PeopleSoft's
  proprietary partial-page-update protocol, not a REST/JSON endpoint. A
  plain `requests.get` of that URL (or any PeopleSoft "Page="-parameterized
  URL, including a guessed direct-job-detail URL) only ever returns the
  empty Fluid app shell — all real content is filled in by client-side JS
  after a stateful POST handshake, so this cannot be scraped with `requests`
  the way PNNL or ORNL can.
- No bot-detection wall, though. Once driven with Playwright (real browser,
  real JS), the search box works exactly as a human would experience it —
  type a keyword, press Enter, get results — with no CAPTCHA, no login
  required to search or read postings (only to apply). So this is the
  Playwright/HTML-scraping path (like indeed.py), not the API path.
- No stable per-posting URL. PeopleSoft Fluid doesn't expose real permalinks
  for job postings — the browser URL never changes as you navigate between
  search, a job's detail view, and the next job (it's all client-side state
  over one POST-driven URL). A plausible-looking guessed URL scheme
  (`...&Page=HRS_CE_JOB_DTL_FL&Action=A&JobOpeningId=<id>&SiteId=1...`)
  returns "You are not authorized for this page" when hit without the
  session having arrived there via a real search first — so it's not a
  usable deep link either. Every posting's `url` below is therefore the
  general search app URL, not a per-job link. This is an honest limitation
  of the ATS itself, not a shortcut taken here — a human still needs to
  re-search by Job ID on that page to reach a specific posting.

Given that, this scrapes by: loading the search app, typing the keyword,
reading each result row from the rendered results grid (title, Job ID,
location, job family, posted date — `li[id^="HRS_AGNT_RSLT_I$..._row_"]`
elements), then clicking into the first result and using the built-in
"Next Job" button (`#DERIVED_HRS_FLU_HRS_NEXT_PB`) to step through every
result's detail view in the same browser session, where the fuller fields
live (Full/Part Time, Regular/Temporary, Salary Range when published, and
the job description sections, all under predictable
`HRS_SCH_WRK_DESCR100$<n>` / `...grp$<n>` id pairs).

Verified against live results on 2026-08-24 (search: "physicist", 3 real
postings, including a published salary range on one).
"""
import time

from playwright.sync_api import Page, sync_playwright

CAREERS_URL = "https://www.sandia.gov/careers/jobs-app/"
COMPANY = "Sandia National Laboratories"

# Section labels that are company-wide boilerplate on every posting, not
# job-specific content — skipped when building the snippet.
BOILERPLATE_LABELS = {
    "about sandia",
    "posting duration",
    "security clearance",
    "eeo",
    "nnsa requirements for medpeds",
    "salary range",  # pulled out separately into `salary`
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _text(page: Page, selector: str) -> str:
    el = page.query_selector(selector)
    return (el.text_content() or "").strip() if el else ""


def _extract_detail(page: Page, keyword: str) -> dict | None:
    job_id = _text(page, "#HRS_SCH_WRK2_HRS_JOB_OPENING_ID")
    title = _text(page, "#HRS_SCH_WRK2_POSTING_TITLE")
    if not job_id or not title:
        return None

    location = _text(page, "#HRS_SCH_WRK_HRS_DESCRLONG") or None
    full_part = _text(page, "#HRS_SCH_WRK_HRS_FULL_PART_TIME")
    reg_temp = _text(page, "#HRS_SCH_WRK_HRS_REG_TEMP")
    job_type = ", ".join(p for p in (full_part, reg_temp) if p) or None

    salary = None
    snippet_parts = []
    for i in range(30):  # generous cap; loop breaks once labels run out
        label = _text(page, f"#HRS_SCH_WRK_DESCR100\\${i}lbl")
        if not label:
            body = _text(page, f"#win0divHRS_SCH_WRK_DESCR100\\${i}")
            if not body:
                break  # no more numbered sections
            label = ""
        value = _text(page, f"#win0divHRS_SCH_WRK_DESCR100grp\\${i}")
        norm_label = label.lower().strip()
        if norm_label == "salary range":
            # Value includes a trailing "*Salary range is estimated..."
            # disclaimer sentence on the same line — keep just the figures.
            salary = (value.split("*")[0].strip() or None) if value else None
        elif norm_label not in BOILERPLATE_LABELS and value:
            snippet_parts.append(value)

    snippet = " ".join(snippet_parts)[:1000]

    return {
        "source": "snl",
        "source_job_id": job_id,
        "title": title,
        "company": COMPANY,
        "location": location,
        "salary": salary,
        "job_type": job_type,
        # No stable per-posting URL exists in this PeopleSoft Fluid
        # instance (see module docstring) — points at the search app;
        # find this posting again there by its Job ID.
        "url": CAREERS_URL,
        "snippet": snippet,
        "search_keyword": keyword,
    }


def search_snl(keyword: str, location: str = None, radius_miles: int = None,
                headless: bool = True) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — Sandia's PeopleSoft search box is
    keyword-only, no separate geographic filter."""
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(CAREERS_URL, wait_until="networkidle", timeout=60000)

        box = page.locator("input[placeholder*='Search by job title']")
        box.wait_for(timeout=20000)
        box.fill(keyword)
        box.press("Enter")
        page.wait_for_timeout(5000)

        rows = page.query_selector_all("li[id^='HRS_AGNT_RSLT_I\\$'][id*='_row_']")
        count = len(rows)
        if count == 0:
            browser.close()
            return results

        rows[0].click()
        page.wait_for_timeout(2500)

        seen_ids = set()
        for _ in range(count):
            job = _extract_detail(page, keyword)
            if job and job["source_job_id"] not in seen_ids:
                seen_ids.add(job["source_job_id"])
                results.append(job)

            next_btn = page.query_selector("#DERIVED_HRS_FLU_HRS_NEXT_PB")
            if not next_btn:
                break
            next_btn.click()
            page.wait_for_timeout(2000)
            time.sleep(0.3)  # be polite between postings

        browser.close()
    return results


if __name__ == "__main__":
    jobs = search_snl("physicist", headless=True)
    print(f"Found {len(jobs)} jobs")
    for j in jobs:
        print(j["title"], "-", j["location"], "-", j["salary"], "-", j["job_type"])
        print("  snippet:", (j["snippet"] or "")[:150])
