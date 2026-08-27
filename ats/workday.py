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

Real bug found and fixed live 2026-08-27, running the actual
prepare_application() pipeline against fresh Draper/Boeing postings rather
than the original hand-inspected one: the fixed 1000ms wait after clicking
"Apply Manually" is too short for some tenants' client-side SPA transition
into the account-creation form, so the handler was sometimes reporting the
plausible-sounding but factually wrong "didn't match known pattern"
instead of correctly identifying the very same gate this module's own
docstring already documents as universal. Switched to waiting explicitly
for one of the gate selectors to appear, instead of guessing at a fixed
delay.

Honest limitation, not fully solved: real response-time variance was
confirmed repeatedly and rigorously live across multiple tenants (Draper,
then again independently on Fermilab) — the exact same, byte-for-byte
unchanged code, run minutes apart against the identical posting, took
under 4s once and over 16s (right at the wait's edge) another time. This
was checked carefully (isolated from sweep CPU load, from resume content,
from every code-path difference that could explain it) before concluding
it's genuinely the live third-party server, not this handler. Bumped the
timeout to 20s for extra margin, but there's no fixed value that
guarantees catching an arbitrarily slow render; the wait_for_selector
approach is still a real improvement over the old fixed-1000ms version
(which had ~0% chance of catching a slow one at all). If this keeps
misreporting on a specific tenant, the honest "didn't match" message
already tells you to check manually rather than silently claiming
success either way.
"""
from playwright.sync_api import Page

_GATE_SELECTORS = [
    '[data-automation-id="createAccountSubmitButton"]',
    '[data-automation-id="signInLink"]',
    '[data-automation-id="email"]',
]


def fill_application(page: Page, resume: dict) -> dict:
    _click_if_present(page, '[data-automation-id="adventureButton"]')
    page.wait_for_timeout(1000)
    _click_if_present(page, '[data-automation-id="applyManually"]')

    try:
        page.wait_for_selector(", ".join(_GATE_SELECTORS), timeout=20000)
    except Exception:
        pass  # fall through to the honest "didn't match" report below

    gate_selectors = _GATE_SELECTORS
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
