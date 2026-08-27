"""Eightfold.ai application filler.

Eightfold hosts discovery already (see scrapers/_eightfold.py — Northrop
Grumman, Lockheed Martin, Applied Materials, GlobalFoundries all use it),
but that only reverse-engineered the *search* API, never the actual
application form. Investigated live 2026-08-27 with this project's own
Playwright across all four tenants' real postings.

**Real, tenant-dependent split — not a platform-wide gate like Workday's.**
Clicking "Apply" leads to one of two outcomes depending on the tenant:
  - Northrop Grumman, GlobalFoundries: a genuine "Sign in / Create an
    account" wall (email + password/SSO, "First time here? Create an
    account") before any application field appears — same
    account-creation blocker as Workday/Taleo, so this handler detects
    it and hands off honestly rather than guessing.
  - Applied Materials, Lockheed Martin: no gate at all — "Apply" goes
    straight to a real "Application Form" with Resume/CV upload, Contact
    Information (first/last name, email, phone — stable ids
    `Contact_Information_{firstname,lastname,email,phone}`, confirmed
    identical across both tenants), and per-posting custom questions.
    Filled here.

One extra step some tenants need before "Apply" is even clickable: a
`#welcomeModal` intro dialog intercepts the click otherwise (confirmed on
Lockheed Martin — Playwright's actionability wait hung the full 30s
against it before this was found and handled; Applied Materials didn't
show one on the posting checked, so this is a no-op there). Dismissed via
its close button (`[aria-label="Close welcome message"]`) before clicking
Apply.

Custom questions use a generated `input-N` id for the actual field, with
`aria-labelledby` pointing at a separate `Application_Questions_q_*_label`
element carrying the real question text — same indirection pattern
`ats/greenhouse.py`/`ats/ashby.py` already handle for their own platforms,
just via a different attribute. `[aria-required="true"]` correctly marks
which are actually required (confirmed: "Preferred Pronoun" is present but
NOT required, "How did you hear about this position?" is). A
`g-recaptcha-response` field is present but invisible on the tenants
checked — same "doesn't block reaching the fields, only fires on submit,
which this project never does" treatment as every other handler's
submit-time CAPTCHA.

Note: "Preferred Name" is a real optional field seen on Lockheed Martin's
form (`Application_Questions_q_preferredName`) — left unfilled and
unflagged here since it isn't required, but worth a `/profile` entry
later if it comes up as required on some other posting.
"""
import re

from playwright.sync_api import Page

_CONTACT_FIELDS = {
    "Contact_Information_firstname": "first_name",
    "Contact_Information_lastname": "last_name",
    "Contact_Information_email": "email",
    "Contact_Information_phone": "phone",
}


def fill_application(page: Page, resume: dict) -> dict:
    """Fills known fields on an Eightfold job page. Returns
    {"platform": "eightfold", "needs_review": [...]}."""
    close_modal = page.query_selector("[aria-label='Close welcome message']")
    if close_modal:
        close_modal.click()
        page.wait_for_timeout(500)

    apply_btn = page.query_selector("a:has-text('Apply'), button:has-text('Apply')")
    if apply_btn:
        try:
            apply_btn.click(timeout=5000)
            page.wait_for_timeout(2500)
        except Exception:
            pass

    if page.query_selector("input[type=email]") and (
        page.query_selector("text=Create an account") or page.query_selector("text=Sign in using Google")
    ):
        return {
            "platform": "eightfold",
            "needs_review": [
                "This tenant requires signing in or creating an account before "
                "any application fields appear — sign in or create an account "
                "yourself, then continue manually."
            ],
            "submitted": False,
        }

    form = page.query_selector("#Contact_Information_firstname")
    if not form:
        return {
            "platform": "eightfold",
            "needs_review": [
                "Couldn't find the Eightfold application form after clicking "
                "Apply — layout may differ for this tenant, or it may require "
                "signing in. Review and apply manually."
            ],
            "submitted": False,
        }

    for field_id, resume_key in _CONTACT_FIELDS.items():
        value = resume.get(resume_key)
        if not value:
            continue
        el = page.query_selector(f"#{field_id}")
        if el:
            el.fill(value)

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = page.query_selector("input[type=file]")
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)

    unanswered = []
    seen_questions = set()
    known_ids = set(_CONTACT_FIELDS.keys())
    for el in page.query_selector_all('[aria-required="true"]'):
        el_id = el.get_attribute("id") or ""
        if el_id in known_ids:
            continue
        question_key = _question_key(el_id)
        if question_key in seen_questions:
            continue  # a sibling radio option for a question already captured
        seen_questions.add(question_key)
        label = _label_for(page, el, el_id)
        unanswered.append(label or f"(unlabeled field: {el_id})")

    return {"platform": "eightfold", "needs_review": unanswered, "submitted": False}


def _question_key(el_id: str) -> str:
    """Radio-button options for one question get separate elements with a
    trailing option/index suffix — two different formats confirmed live:
    `Application_questions_q_consent-Yes-0` / `-No-1` (Applied Materials)
    and `Application_Questions_1006_1-0.0` / `-1.0` (Lockheed Martin).
    Stripping either groups sibling options back into one question so it
    isn't listed twice."""
    stripped = re.sub(r"-[^-]+-\d+$", "", el_id)  # Applied Materials' format
    stripped = re.sub(r"-\d+\.\d+$", "", stripped)  # Lockheed Martin's format
    return stripped


def _label_for(page: Page, el, el_id: str = "") -> str | None:
    labelledby = el.get_attribute("aria-labelledby")
    if labelledby:
        label_el = page.query_selector(f"#{labelledby}")
        if label_el:
            text = label_el.text_content().strip()
            if text:
                return text
    aria_label = el.get_attribute("aria-label")
    # A bare "Yes"/"No" aria-label is just the radio *option*, not the
    # question — confirmed live on Applied Materials (id
    # "Application_questions_q_consent-Yes-0", aria-label "Yes", no
    # question-text label anywhere else on the element or its fieldset,
    # which only has a generic sr-only "Application questions" legend).
    # Fall back to the semantic `q_<name>` segment already embedded in the
    # id, which is at least identifiable, rather than a bare "Yes".
    if aria_label and aria_label.strip().lower() not in ("yes", "no", "true", "false"):
        return aria_label.strip()
    match = re.search(r"q_(\w+?)(?:-|$)", el_id)
    if match:
        return match.group(1).replace("_", " ")
    return aria_label.strip() if aria_label else None
