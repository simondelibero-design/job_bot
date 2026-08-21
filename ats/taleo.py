"""Taleo (*.taleo.net) application filler.

Live-inspected 2026-08-21 against a real Herman Miller/PMG posting
(pmg.taleo.net). Clicking "Apply Online" leads straight to a Login page
requiring a Taleo user account ("User Name"/"Password", with a "New User"
registration link) before any application field is shown — the same
account-creation blocker found on Workday, just further upstream (Workday
at least lets you choose Autofill/Manual/Last-Application before hitting
it; Taleo puts it before anything else).

Creating accounts is off-limits for automation in this project, so there's
nothing further to fill generically here — detect the gate and hand off.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    _click_if_present(page, "a:has-text('Apply Online'), a:has-text('Apply Now')")
    page.wait_for_timeout(1000)

    if page.query_selector("input[type=password]") or page.query_selector("text=New User"):
        return {
            "platform": "taleo",
            "needs_review": [
                "Taleo requires signing in or creating an account before any "
                "application fields appear — create an account yourself, "
                "then continue manually."
            ],
            "submitted": False,
        }

    return {
        "platform": "taleo",
        "needs_review": [
            "Taleo apply flow didn't match the known pattern (Apply Online → "
            "Login/New User) — layout may differ for this tenant. Review "
            "and apply manually."
        ],
        "submitted": False,
    }


def _click_if_present(page: Page, selector: str):
    el = page.query_selector(selector)
    if el:
        el.click()
