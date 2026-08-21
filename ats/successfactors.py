"""SAP SuccessFactors (*.successfactors.com) application filler.

Live-inspected 2026-08-21 against a real career site (career10.successfactors.com,
"Vinarchy"). Applying lands on a "Career Opportunities: Sign In" page —
email + password, with "Not a registered user yet? Create an account to
apply" — the same account-creation blocker as Workday and Taleo, just
under SAP's branding.

Creating accounts is off-limits for automation in this project, so there's
nothing further to fill generically here — detect the gate and hand off.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    _click_if_present(page, "a:has-text('Apply'), button:has-text('Apply')")
    page.wait_for_timeout(1000)

    if page.query_selector("input[type=password]") or page.query_selector("text=Create an account"):
        return {
            "platform": "successfactors",
            "needs_review": [
                "SuccessFactors requires signing in or creating an account "
                "before any application fields appear — create an account "
                "yourself, then continue manually."
            ],
            "submitted": False,
        }

    return {
        "platform": "successfactors",
        "needs_review": [
            "SuccessFactors apply flow didn't match the known pattern "
            "(Apply → Sign In/Create Account) — layout may differ for this "
            "tenant. Review and apply manually."
        ],
        "submitted": False,
    }


def _click_if_present(page: Page, selector: str):
    el = page.query_selector(selector)
    if el:
        el.click()
