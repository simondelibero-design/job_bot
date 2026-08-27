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

Two real bugs found and fixed live 2026-08-27, running the actual
prepare_application() pipeline against fresh PPPL and Iridium postings:
(1) `_content_frame`'s "first frame whose URL contains icims.com" check
returned the wrong frame on tenants where the *top-level page itself* is
also hosted directly on a `{tenant}.icims.com` subdomain (both PPPL's and
Iridium's are) — `page.frames[0]` is always the main frame, and since its
own URL matched too, the check never got to the real nested content
iframe (`...?in_iframe=1`) where the actual "Apply" button and form live.
Confirmed live: the outer frame's body has no "apply" text anywhere; the
real content only appears in the `in_iframe=1` frame, and only after a
few extra seconds to render. Now prefers a frame whose URL contains
`in_iframe=1` when one exists. (2) The apply-button text this handler
looked for, "Apply for this job online", doesn't match every tenant's
copy — PPPL's actual button reads "Apply for This Job". Broadened to a
visible-only partial-text match on "Apply" (a hidden "Please Enable
Cookies" message elsewhere on the page also contains that word, so
matching on visibility, not just text, matters here).
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    ctx = _content_frame(page)
    # PPPL/Iridium's nested content iframe reliably needs ~3s to render its
    # real content — confirmed live (2026-08-27) across repeated runs at
    # 1.5s (empty) vs 3s+ (populated). A plain text match also isn't safe
    # here: a hidden "Please Enable Cookies" message contains the word
    # "apply" in its body and was being matched first, so this uses a
    # visible-only locator to skip it.
    apply_locator = ctx.get_by_text("Apply", exact=False).locator("visible=true")
    try:
        apply_locator.first.wait_for(timeout=8000)
        apply_locator.first.click(timeout=3000)
    except Exception:
        pass

    # Re-fetch the content frame after the click: it navigates to a new
    # URL (.../job -> .../login), and querying the pre-click `ctx`
    # reference against that new content was unreliable in testing —
    # sometimes finding #email, sometimes not, depending on exactly when
    # Playwright's frame-tree updated relative to this check. Re-scanning
    # page.frames() fresh removes that race entirely. The render time
    # itself also varies by tenant — confirmed live: Iridium's login page
    # is ready within ~1s, PPPL's needs several seconds longer — so this
    # waits adaptively for #email itself rather than guessing a fixed delay.
    ctx = _content_frame(page)
    try:
        ctx.wait_for_selector("#email", timeout=8000)
    except Exception:
        pass
    ctx = _content_frame(page)
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
    icims_frames = [f for f in page.frames if "icims.com" in f.url]
    for frame in icims_frames:
        if "in_iframe=1" in frame.url:
            return frame
    if icims_frames:
        return icims_frames[0]
    return page
