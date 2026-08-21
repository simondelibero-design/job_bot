"""SmartRecruiters (jobs.smartrecruiters.com "Easy Apply") application filler.

Field structure verified live 2026-08-21 against a real Intuitive posting,
driven interactively (via a browser tool, not Playwright automation): no
account/sign-in gate, clicking "I'm interested" drops straight into a form
— resume dropzone, name/email/phone/city, optional social links. Renders
inside nested web-component shadow DOM, but Playwright's selector engine
pierces open shadow roots, so plain CSS ID selectors work.

**However**, driving that same navigation through Playwright automation
(both headless and headed) got blocked by SmartRecruiters' own bot
detection ("Access is temporarily restricted... Automated (bot) activity"),
before the form ever loaded. This is the same category of wall as
ZipRecruiter's Cloudflare block — not something this project bypasses or
spoofs. So this handler is defensive: it fills the known fields *if* it
actually reaches them, but explicitly checks for that block first and
surfaces it honestly rather than silently reporting an empty review list
(which would otherwise look like "auto-filled, ready to review" when
nothing was touched at all).

Core identity fields (name/email/resume/social links) have stable,
semantic IDs across postings when the form does load. City and phone
don't — they're rendered as `#spl-form-element_<n>`, numbered by each
posting's specific field layout — so they're located by their `<label>`
text instead and left for human review rather than guessed at.
Experience/Education sections are usually auto-populated by
SmartRecruiters' own resume parser once the file is dropped, so those are
flagged for the human to double-check rather than filled directly. Never
submits.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    unanswered = []

    interested_link = page.query_selector("a:has-text(\"I'm interested\")")
    if interested_link:
        href = interested_link.get_attribute("href")
        if href:
            page.goto(href, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

    if page.query_selector("text=temporarily restricted") or page.query_selector("text=An error occurred"):
        return {
            "platform": "smartrecruiters",
            "needs_review": [
                "SmartRecruiters blocked automated access to the apply form "
                "(bot detection) — nothing was filled. Open and apply manually."
            ],
            "submitted": False,
        }

    if not page.query_selector("#first-name-input"):
        return {
            "platform": "smartrecruiters",
            "needs_review": [
                "Couldn't reach the Easy Apply form (layout may have changed, "
                "or the page didn't finish loading) — nothing was filled. "
                "Review and apply manually."
            ],
            "submitted": False,
        }

    def fill_if_present(selector: str, value: str | None):
        if not value:
            return
        el = page.query_selector(selector)
        if el:
            el.fill(value)

    fill_if_present("#first-name-input", resume.get("first_name"))
    fill_if_present("#last-name-input", resume.get("last_name"))
    fill_if_present("#email-input", resume.get("email"))
    fill_if_present("#confirm-email-input", resume.get("email"))
    fill_if_present("#linkedin-input", resume.get("linkedin_url"))

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = page.query_selector("#file-input")
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)
        unanswered.append(
            "Resume uploaded — double-check SmartRecruiters' auto-parsed "
            "Experience/Education sections match before submitting."
        )

    phone_input = _input_for_label(page, "Phone number")
    if phone_input and resume.get("phone"):
        phone_input.fill(resume["phone"])
    elif phone_input:
        unanswered.append("Phone number")

    if _input_for_label(page, "City"):
        unanswered.append("City (autocomplete field — needs a selected suggestion, not just typed text)")

    return {"platform": "smartrecruiters", "needs_review": unanswered, "submitted": False}


def _input_for_label(page: Page, label_text: str):
    label = page.query_selector(f"label:has-text('{label_text}')")
    if not label:
        return None
    input_id = label.get_attribute("for")
    return page.query_selector(f"#{input_id}") if input_id else None
