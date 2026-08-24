"""Oak Ridge National Laboratory (ORNL) application filler.

scrapers/ornl.py discovers postings from jobs.ornl.gov (SAP SuccessFactors
"Jobs2Web," server-rendered, no gate for browsing/searching). "Apply now"
on a posting, though, redirects to a different SuccessFactors-branded
career portal (career-hcm20.ns2cloud.com, live-verified 2026-08-24) with a
"Career Opportunities: Sign In" page — the same account-creation gate
ats/successfactors.py already documented for *.successfactors.com/.eu
domains, just on a different hostname ats/detect.py's successfactors
pattern doesn't match, so ORNL gets its own module rather than being
folded into that one.

Creating accounts is off-limits for automation here, so this detects the
gate the same way ats/successfactors.py does and hands off.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    _click_if_present(page, "a:has-text('Apply now')")

    # ORNL's apply link bounces through more than one redirect before
    # landing on the SuccessFactors sign-in page, so a single wait can land
    # mid-navigation ("Execution context was destroyed") — poll instead of
    # trusting one fixed delay.
    gated = _poll_for_gate(page)
    if gated:
        return {
            "platform": "ornl",
            "needs_review": [
                "ORNL requires signing in or creating an account before any "
                "application fields appear — create an account yourself, "
                "then continue manually."
            ],
            "submitted": False,
        }

    return {
        "platform": "ornl",
        "needs_review": [
            "ORNL apply flow didn't match the known pattern (Apply now → "
            "Sign In/Create Account) — layout may have changed. Review and "
            "apply manually."
        ],
        "submitted": False,
    }


def _click_if_present(page: Page, selector: str):
    el = page.query_selector(selector)
    if el:
        el.click()


def _poll_for_gate(page: Page, timeout_ms: int = 15000) -> bool:
    elapsed = 0
    step = 500
    while elapsed < timeout_ms:
        try:
            if page.query_selector("input[type=password]") or page.query_selector("text=Create an account"):
                return True
        except Exception:
            pass  # mid-navigation — the next poll will catch the settled page
        page.wait_for_timeout(step)
        elapsed += step
    return False
