"""APS Physics Jobs (apsphysicsjobs.com, Madgex platform) application filler.

Fills the standard fields this board asks on every posting. Live-verified
2026-08-24 against a real Basilisk Industries posting: clicking "Apply"
scrolls to an in-page form (`#apply-form`) hosted directly on
apsphysicsjobs.com — no redirect out to the employer's own site, no account
gate, no CAPTCHA.

Never submits. The "covering message" field is required on every posting;
it's pre-filled with a fixed, user-specified line (COVERING_MESSAGE below)
rather than anything auto-generated per posting — still surfaced in
needs_review so it gets a look before the human clicks submit, same as
every other field here. The marketing-opt-in checkboxes (job alerts, IOP
Publishing emails, APS emails) are left unchecked — opting in is a decision
for the user, not a default.
"""
from playwright.sync_api import Page

COVERING_MESSAGE = "I'll be honest, it sounds cool and I'm interested."


def fill_application(page: Page, resume: dict) -> dict:
    unanswered = []

    apply_link = page.query_selector("a:has-text('Apply')")
    if apply_link:
        apply_link.click()
        page.wait_for_timeout(500)

    def fill_if_present(selector: str, value: str | None):
        if not value:
            return
        el = page.query_selector(selector)
        if el:
            el.fill(value)

    fill_if_present("#inpFirstName", resume.get("first_name"))
    fill_if_present("#inpLastName", resume.get("last_name"))
    fill_if_present("#inpEmail", resume.get("email"))

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = page.query_selector("#UploadField")
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)

    covering_message = page.query_selector("#inpCoveringMessage")
    if covering_message:
        covering_message.fill(COVERING_MESSAGE)
        unanswered.append(
            f"Covering message pre-filled with a fixed line: \"{COVERING_MESSAGE}\" "
            "— read it before submitting, edit if you want something more specific."
        )

    return {"platform": "aps", "needs_review": unanswered, "submitted": False}
