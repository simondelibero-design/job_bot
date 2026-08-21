"""Indeed search-results scraper.

Reads the public job search page (no login required for browsing). Selectors
were captured from live Indeed markup on 2026-08-18 — Indeed changes its
frontend often, so if scraping starts returning nothing, re-inspect the page
and update the selectors below first.
"""
import time
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.indeed.com/jobs"


def _extract_card(card) -> dict | None:
    title_el = card.query_selector("h3.jobTitle a[data-jk]")
    if not title_el:
        return None
    source_job_id = title_el.get_attribute("data-jk")
    title_span = title_el.query_selector("span")
    title = (title_span.text_content() if title_span else title_el.text_content()).strip()

    company_el = card.query_selector('[data-testid="company-name"]')
    location_el = card.query_selector('[data-testid="text-location"]')
    # salary li carries a two-token data-testid ("attribute_snippet_testid
    # salary-snippet-container"); match on the second token specifically so
    # we don't grab the first generic attribute (often "Full-time") instead.
    salary_el = card.query_selector('[data-testid*="salary-snippet-container"] span')
    job_type_el = card.query_selector(
        '[data-testid="attribute_snippet_testid"]:not([data-testid*="salary"]) span'
    )

    # Snippet: within the parent <li>, Indeed renders 3 <ul>s per card —
    # [0] pay/benefits metadata, [1] description bullets, [2] "view all" links.
    # Grab index 1 defensively (skip if it looks like the metadata or links list).
    snippet = ""
    parent_li = card.evaluate_handle("el => el.closest('li')")
    uls = parent_li.query_selector_all("ul") if parent_li else []
    if len(uls) >= 2:
        text = uls[1].text_content().strip()
        if text and "View all" not in text:
            snippet = text

    return {
        "source": "indeed",
        "source_job_id": source_job_id,
        "title": title,
        "company": company_el.text_content().strip() if company_el else None,
        "location": location_el.text_content().strip() if location_el else None,
        "salary": salary_el.text_content().strip() if salary_el else None,
        "job_type": job_type_el.text_content().strip() if job_type_el else None,
        "url": f"https://www.indeed.com/rc/clk?jk={source_job_id}",
        "snippet": snippet,
    }


def search_indeed(keyword: str, location: str, radius_miles: int, max_pages: int = 1,
                   headless: bool = True) -> list[dict]:
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        for page_num in range(max_pages):
            url = (
                f"{BASE_URL}?q={quote_plus(keyword)}&l={quote_plus(location)}"
                f"&radius={radius_miles}&start={page_num * 10}"
            )
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)

            cards = page.query_selector_all(".job_seen_beacon")
            if not cards:
                break

            for card in cards:
                job = _extract_card(card)
                if job:
                    job["search_keyword"] = keyword
                    results.append(job)

            time.sleep(2)  # be polite between page requests

        browser.close()
    return results


if __name__ == "__main__":
    jobs = search_indeed("physics engineer", "Tacoma, WA", 25, max_pages=1, headless=False)
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["company"], "-", j["location"])
