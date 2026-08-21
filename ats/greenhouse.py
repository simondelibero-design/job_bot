"""Greenhouse (job-boards.greenhouse.io) application filler.

Fills the standard fields Greenhouse asks on every posting. Never submits —
per-posting custom questions (the `question_<id>` / dynamic dropdown fields)
are collected and returned so the review dashboard can surface them for you
to answer and approve before anything goes out.

Selectors verified live against a real Anthropic Greenhouse posting on
2026-08-18 (see ats/README or main conversation for the inspection). Core
fields (#first_name, #last_name, #email, #phone, #resume) are standard
across Greenhouse postings; custom questions are posting-specific and can't
be answered generically.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    """Fills known fields on a Greenhouse application page already loaded
    in `page`. Returns {"platform": "greenhouse", "needs_review": [...]}."""
    unanswered = []

    def fill_if_present(selector: str, value: str | None):
        if not value:
            return
        el = page.query_selector(selector)
        if el:
            el.fill(value)

    fill_if_present("#first_name", resume.get("first_name"))
    fill_if_present("#last_name", resume.get("last_name"))
    fill_if_present("#email", resume.get("email"))
    fill_if_present("#phone", resume.get("phone"))

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = page.query_selector("#resume")
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)

    # Anything else required on the form is a per-posting custom question
    # (or an EEO/demographic dropdown) — surface it instead of guessing.
    known_ids = {"first_name", "last_name", "email", "phone", "resume", "country"}
    for el in page.query_selector_all("input[required], textarea[required], select[required]"):
        el_id = el.get_attribute("id") or ""
        if el_id in known_ids:
            continue
        label = _label_for(page, el)
        unanswered.append(label or f"(unlabeled field: {el_id or el.get_attribute('name')})")

    return {"platform": "greenhouse", "needs_review": unanswered, "submitted": False}


def _label_for(page: Page, el) -> str | None:
    el_id = el.get_attribute("id")
    if el_id:
        label = page.query_selector(f'label[for="{el_id}"]')
        if label:
            return label.text_content().strip()
    container = el.evaluate_handle("el => el.closest('div')")
    if container:
        text = container.as_element().text_content()
        return text.strip()[:120] if text else None
    return None
