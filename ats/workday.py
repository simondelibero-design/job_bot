"""Workday (*.myworkdayjobs.com) application filler.

Live-inspected against two different tenants (2026-08-21): an initial attempt
on a Blue Origin posting got stuck behind a page-opened SSO popup the browser
tool couldn't drive. A second attempt on a Draper posting (no popup this
time) reached the actual apply wizard cleanly and hit the real, structural
blocker instead: every path through "Start Your Application" (Autofill with
Resume, Apply Manually, Use My Last Application) leads to a mandatory
"Create Account/Sign In" step — step 1 of a 7-step wizard, before any resume
or personal-info field is even shown. This is Workday's shared, tenant-wide
account UI (`data-automation-id="createAccountSubmitButton"`, `email`,
`password`, `verifyPassword`), not a per-tenant customization, so it's
universal across Workday postings, not just this one popup.

Creating accounts is off-limits for automation in this project, so there is
no further wizard content to fill generically — this handler detects the
gate and stops honestly rather than guessing at fields it has never seen.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    _click_if_present(page, '[data-automation-id="adventureButton"]')
    page.wait_for_timeout(1000)
    _click_if_present(page, '[data-automation-id="applyManually"]')
    page.wait_for_timeout(1000)

    gate_selectors = [
        '[data-automation-id="createAccountSubmitButton"]',
        '[data-automation-id="signInLink"]',
        '[data-automation-id="email"]',
    ]
    if any(page.query_selector(sel) for sel in gate_selectors):
        return {
            "platform": "workday",
            "needs_review": [
                "Workday requires creating an account (email + password) before "
                "any application fields appear — sign in or create an account "
                "yourself, then continue the wizard manually."
            ],
            "submitted": False,
        }

    return {
        "platform": "workday",
        "needs_review": [
            "Workday apply flow didn't match the known pattern (Apply → "
            "Apply Manually → Create Account) — layout may differ for this "
            "tenant. Review and apply manually."
        ],
        "submitted": False,
    }


def _click_if_present(page: Page, selector: str):
    el = page.query_selector(selector)
    if el:
        el.click()
