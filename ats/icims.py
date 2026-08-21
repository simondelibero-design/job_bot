"""iCIMS (*.icims.com) application filler.

Live-inspected 2026-08-21 against a real General Dynamics Mission Systems
posting (careers-gdms.icims.com, a branded iCIMS tenant). The whole career
site — job listings, posting detail, and the apply flow — renders inside a
same-origin iframe (`iCIMS Content iFrame`). The apply flow's first step is
an email-capture gate (`#email`, name `css_loginName`) plus a GDPR consent
checkbox (`#accept_gdpr`) — and, at least on this tenant, an **hCaptcha**
widget (`textarea[name="h-captcha-response"]`) that must be solved before the
"Next" button will proceed.

Solving/bypassing CAPTCHAs and accepting consent/terms checkboxes are both
off-limits for automation in this project, so this handler prefills the one
safe field (email — just typing text) and stops there. Whether every iCIMS
tenant gates behind hCaptcha the same way hasn't been confirmed; the handler
flags whichever gate elements it actually finds rather than assuming.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    ctx = _content_frame(page)

    _click_if_present(ctx, "text=Apply for this job online")
    page.wait_for_timeout(1000)

    email_input = ctx.query_selector("#email")
    if not email_input:
        return {
            "platform": "icims",
            "needs_review": [
                "Couldn't find the iCIMS email-gate field — layout may differ "
                "for this tenant. Review and apply manually."
            ],
            "submitted": False,
        }

    email = resume.get("email")
    if email:
        email_input.fill(email)

    needs_review = ["Accept the GDPR/privacy consent checkbox yourself before continuing."]
    if ctx.query_selector('textarea[name="h-captcha-response"]') or ctx.query_selector(".h-captcha"):
        needs_review.append(
            "iCIMS requires solving an hCaptcha challenge on this step — "
            "email is pre-filled, solve the captcha and click Next yourself."
        )

    return {"platform": "icims", "needs_review": needs_review, "submitted": False}


def _content_frame(page: Page):
    for frame in page.frames:
        if "icims.com" in frame.url:
            return frame
    return page


def _click_if_present(ctx, selector: str):
    el = ctx.query_selector(selector)
    if el:
        el.click()
