"""Teamtailor (careers.{company}.com, e.g. careers.bluefors.com) application
filler.

Verified live 2026-08-26/27 against a real Bluefors posting driven with
this project's own Playwright: the job posting page itself
(`careers.bluefors.com/jobs/{id}-{slug}`) IS the apply page — clicking
"Apply now!" doesn't navigate anywhere (`page.url` is unchanged
afterward), it Turbo-loads `#job-application-form` into the same page.
No account-creation or sign-in gate anywhere in that path — every field is
immediately visible and fillable once the form loads. A cookie-consent
banner does sit in front of the "Apply now!" button and silently eats the
click if left up (confirmed: without dismissing it, "Apply now!" appeared
to click but the form never loaded), so this handler dismisses it first
by choosing "Decline all non-necessary cookies" — the privacy-preserving
option — purely to unblock the click path to the form, not to accept any
tracking.

Field ids are Teamtailor's own Rails-style naming (`candidate_first_name`,
`candidate_last_name`, `candidate_email`, `candidate_phone`,
`candidate_resume_remote_url` for the resume file input) — these come
from the platform itself, not per-tenant customization, so they should
hold across other Teamtailor-hosted career sites too. No plain-text
LinkedIn field exists on this form; a hidden `candidate[linkedin_url]`
input is only ever populated by clicking Teamtailor's own "Apply with
LinkedIn" OAuth button, which this project doesn't drive (that's an
OAuth/SSO grant, off-limits for automation the same way account creation
is).

`candidate_location` (labelled "Address") is a JS autocomplete combobox
(`role="combobox"`, Google-Places-backed, feeding a cluster of hidden
lat/long/city/country fields) that needs a selected suggestion, not just
typed text — same caution ats/ashby.py and ats/smartrecruiters.py already
apply to their own address/city autocomplete fields — so this handler
flags it for review instead of guessing at it.

Per-posting screening questions render as `<fieldset><legend>` groups
(confirmed: 4 Yes/No boolean questions on the test posting, e.g. "Are you
eligible to work in the U.S.?", "Are you at least 18 years of age or
older?") with a `[data-asterisk="true"]` marker on required ones — their
ids are randomized per page load (confirmed: the same posting produced
different ids across two separate loads), so they can't be targeted by id
at all, only found generically and flagged. The GDPR-style consent
checkbox (`candidate_consent_given`, required, "I agree that I have read
the (privacy policy)...") is a legal declaration, not a factual field —
consistent with how ats/ashby.py and ats/greenhouse.py leave "I certify"
attestations for a human to check themselves, this handler does not
auto-check it.

No CAPTCHA of any kind (reCAPTCHA/hCaptcha) was present anywhere on this
posting's form.
"""
from playwright.sync_api import Page

_TEXT_FIELDS = {
    "candidate_first_name": "first_name",
    "candidate_last_name": "last_name",
    "candidate_email": "email",
    "candidate_phone": "phone",
}


def fill_application(page: Page, resume: dict) -> dict:
    """Fills known fields on a Teamtailor job posting page already loaded in
    `page` (the posting page itself, not a separate apply URL — clicking
    "Apply now!" loads the form in place). Returns
    {"platform": "teamtailor", "needs_review": [...]}."""
    _dismiss_cookie_banner(page)

    form = page.query_selector("#job-application-form")
    if not form:
        apply_button = page.query_selector("button:has-text('Apply now')")
        if apply_button:
            apply_button.click()
            page.wait_for_timeout(2000)
        form = page.query_selector("#job-application-form")

    if not form:
        return {
            "platform": "teamtailor",
            "needs_review": [
                "Couldn't reach the Teamtailor application form (layout may "
                "have changed, or an account/sign-in gate is blocking it) — "
                "nothing was filled. Review and apply manually."
            ],
            "submitted": False,
        }

    def fill_if_present(field_id: str, value: str | None):
        if not value:
            return
        el = page.query_selector(f"#{field_id}")
        if el:
            el.fill(value)

    for field_id, resume_key in _TEXT_FIELDS.items():
        fill_if_present(field_id, resume.get(resume_key))

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = page.query_selector("#candidate_resume_remote_url")
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)
        # Dropzone.js processes the file asynchronously (client-side preview
        # + upload) and replaces the hidden input node afterward — give it a
        # moment before the caller inspects page state.
        page.wait_for_timeout(1500)

    unanswered = []

    address_input = page.query_selector("#candidate_location")
    if address_input:
        unanswered.append(
            "Address (autocomplete field — needs a selected suggestion, not "
            "just typed text)"
        )

    consent = page.query_selector("#candidate_consent_given")
    if consent:
        unanswered.append(
            "Privacy policy consent checkbox — requires a human to read and "
            "agree, not auto-checked."
        )

    for fieldset in form.query_selector_all("fieldset"):
        legend = fieldset.query_selector("legend")
        if not legend:
            continue
        if not fieldset.query_selector("[data-asterisk='true']"):
            continue  # not required
        text = legend.text_content() or ""
        text = text.replace("Required", "").strip()
        unanswered.append(text[:150] or "(unlabeled screening question)")

    return {"platform": "teamtailor", "needs_review": unanswered, "submitted": False}


def _dismiss_cookie_banner(page: Page):
    decline = page.query_selector("button:has-text('Decline all non-necessary cookies')")
    if decline:
        decline.click()
        page.wait_for_timeout(500)
