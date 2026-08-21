"""Lever (jobs.lever.co) application filler.

Same approach as ats/greenhouse.py: fill the standard fields, surface
everything else (custom "cards[...]" questions, EEO dropdowns) for manual
review instead of guessing. Lever also commonly gates submission behind
hCaptcha (a hidden `h-captcha-response` field is present on postings that
use it) — that always needs a human in the loop, so this module never
attempts to solve or bypass it; it just leaves it for the dashboard's
review step, same as the CAPTCHA handling discussed for search/discovery.

Field names verified live against a real Veeva Systems Lever posting on
2026-08-18: name="name" (single full-name field, unlike Greenhouse's
split first/last), name="email", name="phone", name="urls[LinkedIn]",
name="resume" (file upload).
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    unanswered = []
    has_captcha = page.query_selector('input[name="h-captcha-response"]') is not None

    def fill_if_present(selector: str, value: str | None):
        if not value:
            return
        el = page.query_selector(selector)
        if el:
            el.fill(value)

    fill_if_present('input[name="name"]', resume.get("full_name"))
    fill_if_present('input[name="email"]', resume.get("email"))
    fill_if_present('input[name="phone"]', resume.get("phone"))
    fill_if_present('input[name="urls[LinkedIn]"]', resume.get("linkedin_url"))

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = page.query_selector('input[name="resume"][type="file"]')
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)

    known_names = {"name", "email", "phone", "urls[LinkedIn]", "resume", "org", "location"}
    for el in page.query_selector_all("input[required], textarea[required], select[required]"):
        name = el.get_attribute("name") or ""
        if name in known_names or name.startswith("eeo["):
            continue
        label = _label_for(page, el)
        unanswered.append(label or f"(unlabeled field: {name})")

    if has_captcha:
        unanswered.append("hCaptcha challenge (requires manual solve — see dashboard)")

    return {"platform": "lever", "needs_review": unanswered, "submitted": False}


def _label_for(page: Page, el) -> str | None:
    container = el.evaluate_handle(
        "el => el.closest('.application-question, .card, div')"
    )
    if container:
        text = container.as_element().text_content()
        return text.strip()[:120] if text else None
    return None
