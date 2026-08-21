"""ZipRecruiter search-results scraper.

The results list (title/company/location/salary) is visible without an
account. Clicking into a job for the full description or apply link puts up
an account-creation wall for anonymous sessions.

To get past that, run `python scrapers/ziprecruiter_login.py` once — it
opens a real browser window to a persistent profile directory
(`ziprecruiter_profile/`), you log into your own account there, and closing
the window is enough (Playwright writes the session to that profile
continuously; nothing here ever sees your password). Pass that profile
directory's path as `profile_dir` to get past the signup wall and resolve
real job URLs.

The click-through URL-resolution path below is best-effort — it was written
without ever seeing an authenticated ZipRecruiter session (this module
doesn't handle credentials), so it needs a live test run once you've
actually logged in. If it doesn't resolve real URLs correctly, tell me what
happened and I'll fix the selectors against the real authenticated DOM.
"""
import re
import time
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.ziprecruiter.com/jobs-search"
SALARY_RE = re.compile(r"\$[\d,]+(?:\.\d+)?\s*(?:-|to)\s*\$[\d,]+(?:\.\d+)?\s*(?:/hr|/yr|a year|an hour|K)?", re.I)


def _extract_card(card) -> dict | None:
    card_id = card.get_attribute("id")  # e.g. "job-card-z5_ZLqF2XRd2nzRQwRL5lw"
    if not card_id:
        return None
    source_job_id = card_id.removeprefix("job-card-")

    title_el = card.query_selector("h2")
    company_el = card.query_selector('[data-testid="job-card-company"]')
    location_el = card.query_selector('[data-testid="job-card-location"]')
    if not title_el:
        return None

    full_text = card.text_content() or ""
    salary_match = SALARY_RE.search(full_text)

    return {
        "source": "ziprecruiter",
        "source_job_id": source_job_id,
        "title": title_el.text_content().strip(),
        "company": company_el.text_content().strip() if company_el else None,
        "location": location_el.text_content().strip() if location_el else None,
        "salary": salary_match.group(0) if salary_match else None,
        "job_type": None,
        "url": None,  # filled in by _resolve_url when authenticated
        "snippet": "",
    }


def _resolve_url(page, card_id: str, search_url: str) -> str | None:
    """Best-effort: click the card, see if the SPA router changes page.url,
    capture it, then return to the results list for the next card."""
    card = page.query_selector(f"#{card_id}")
    if not card:
        return None
    try:
        card.click()
        page.wait_for_timeout(1200)
        new_url = page.url
        if new_url != search_url:
            resolved = new_url
        else:
            resolved = None
        page.go_back(wait_until="domcontentloaded", timeout=10000)
        page.wait_for_timeout(800)
        return resolved
    except Exception:
        # Don't let one bad card kill the whole run — leave its url as None
        # and keep going.
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass
        return None


def search_ziprecruiter(keyword: str, location: str, radius_miles: int,
                         profile_dir: str | None = None,
                         storage_state_path: str | None = None,
                         headless: bool = True) -> list[dict]:
    results = []
    seen_ids = set()
    search_url = (
        f"{BASE_URL}?search={quote_plus(keyword)}&location={quote_plus(location)}"
        f"&radius={radius_miles}"
    )
    use_profile = bool(profile_dir and Path(profile_dir).exists())
    use_cookies = bool(storage_state_path and Path(storage_state_path).exists())
    authenticated = use_profile or use_cookies

    with sync_playwright() as p:
        if use_profile:
            context = p.chromium.launch_persistent_context(profile_dir, headless=headless)
            page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                storage_state=storage_state_path if use_cookies else None,
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        cards = page.query_selector_all('article[id^="job-card-"]')
        card_ids = [c.get_attribute("id") for c in cards]

        for card in cards:
            job = _extract_card(card)
            if job and job["source_job_id"] not in seen_ids:
                seen_ids.add(job["source_job_id"])
                job["search_keyword"] = keyword
                results.append(job)

        if authenticated:
            for job in results:
                full_card_id = f"job-card-{job['source_job_id']}"
                job["url"] = _resolve_url(page, full_card_id, search_url)
                time.sleep(1)  # be polite between clicks

        context.close()
    return results


if __name__ == "__main__":
    profile = Path(__file__).parent / "ziprecruiter_profile"
    cookies = Path(__file__).parent / "ziprecruiter_auth.json"
    profile_arg = str(profile) if profile.exists() else None
    cookies_arg = str(cookies) if cookies.exists() else None
    jobs = search_ziprecruiter(
        "physics engineer", "Tacoma, WA", 25,
        profile_dir=profile_arg, storage_state_path=cookies_arg, headless=False,
    )
    print(f"Found {len(jobs)} jobs (authenticated={profile_arg is not None or cookies_arg is not None})")
    for j in jobs[:5]:
        print(j["title"], "-", j["company"], "-", j["location"], "-", j["salary"], "-", j["url"])
