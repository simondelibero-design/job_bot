"""SLAC National Accelerator Laboratory application filler.

Live-verified 2026-08-24 against a real posting on careersearch.stanford.edu
(Oracle Fusion Cloud Recruiting "Candidate Experience" — see
scrapers/slac.py for how these postings are discovered). Clicking
"Apply Now" opens a lighter gate than Workday's full account-creation wall:
a single "Let's get started" step asking for an email address
(`#primary-email-1`) plus a required "I agree with terms and conditions"
checkbox (`#legal-disclaimer-checkbox`) before a "Next" button proceeds.
That step renders inside its own iframe
(`.../job/<id>/apply/email`), confirmed by inspecting `page.frames` — so,
like ats/icims.py, this handler has to locate that frame explicitly rather
than querying the top-level page, or every selector below silently misses.

Accepting terms/consent is off-limits for automation here (same rule that
keeps ats/icims.py from checking its GDPR checkbox), so this fills the one
safe field — email, just typing text — and stops, leaving the checkbox and
"Next" for the human. Notably, this step also has a hidden honeypot field
(`#honey-pot-0`) — a spam-bot trap that must stay empty; filling it would
flag the application as automated, so this handler never touches it.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    try:
        page.wait_for_selector("text=Apply Now", timeout=10000)
    except Exception:
        pass
    _click_if_present(page, "text=Apply Now")

    ctx = _wait_for_apply_frame(page)
    email_input = ctx.query_selector("#primary-email-1") if ctx else None
    if not email_input:
        return {
            "platform": "slac",
            "needs_review": [
                "Couldn't find the SLAC email-gate field — layout may have "
                "changed. Review and apply manually."
            ],
            "submitted": False,
        }

    email = resume.get("email")
    if email:
        email_input.fill(email)

    return {
        "platform": "slac",
        "needs_review": [
            "Accept the terms and conditions checkbox yourself and click "
            "Next to continue — email is pre-filled."
        ],
        "submitted": False,
    }


def _wait_for_apply_frame(page: Page, timeout_ms: int = 10000):
    """The apply gate renders inside its own iframe that only appears after
    the "Apply Now" click navigates it — poll page.frames until it shows up
    and has actually loaded the email field, rather than assuming a fixed
    delay is enough."""
    elapsed = 0
    step = 250
    while elapsed < timeout_ms:
        for frame in page.frames:
            if "/apply/" in frame.url and frame.query_selector("#primary-email-1"):
                return frame
        page.wait_for_timeout(step)
        elapsed += step
    return None


def _click_if_present(page: Page, selector: str):
    el = page.query_selector(selector)
    if el:
        el.click()
