"""JazzHR (*.applytojob.com) application filler.

Fills the standard fields JazzHR asks on every posting. Field IDs use
JazzHR's platform-wide `resumator-*` naming (legacy "The Resumator" branding)
— not per-tenant customization — so these selectors are stable across
postings the same way Greenhouse's `#first_name` etc. are.

Never submits — a "Human Check" reCAPTCHA sits in front of the submit
button on every posting seen so far, and per-posting custom questions
(`resumator-questionnaire[id]`) plus the voluntary EEOC veteran/disability
self-ID radios are collected and returned so the review dashboard can
surface them for you to answer and approve before anything goes out.

Selectors verified live against a real Labelmaster/American Labelmark
JazzHR posting on 2026-08-21.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    """Fills known fields on a JazzHR application form already loaded in
    `page`. Returns {"platform": "jazzhr", "needs_review": [...]}."""
    unanswered = []

    # The form exists in the DOM from page load but stays hidden (a
    # collapsed inline reveal, not a real navigation) until "Apply Now" is
    # clicked.
    apply_link = page.query_selector("a:has-text('Apply Now')")
    if apply_link:
        apply_link.click()
        page.wait_for_timeout(500)

    def fill_if_present(selector: str, value: str | None):
        if not value:
            return
        el = page.query_selector(selector)
        if el:
            el.fill(value)

    fill_if_present("#resumator-firstname-value", resume.get("first_name"))
    fill_if_present("#resumator-lastname-value", resume.get("last_name"))
    fill_if_present("#resumator-email-value", resume.get("email"))
    fill_if_present("#resumator-phone-value", resume.get("phone"))
    fill_if_present("#resumator-address-value", resume.get("address"))
    fill_if_present("#resumator-city-value", resume.get("city"))
    fill_if_present("#resumator-state-value", resume.get("state"))
    fill_if_present("#resumator-postal-value", resume.get("postal"))

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = page.query_selector("#resumator-resume-value")
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)

    # Per-posting custom questions (resumator-questionnaire[id]) and the
    # voluntary EEOC veteran/disability self-ID sections are posting- or
    # policy-specific — surface instead of guessing.
    known_prefixes = ("resumator-firstname", "resumator-lastname", "resumator-email",
                       "resumator-phone", "resumator-address", "resumator-city",
                       "resumator-state", "resumator-postal", "resumator-resume")
    skip_names = {"resumator-xml-value", "g-recaptcha-response", "submit_resume", "cancel_resume"}
    seen_names = set()
    for el in page.query_selector_all("input, select, textarea"):
        name = el.get_attribute("name") or ""
        if el.get_attribute("type") in ("hidden", "button", "submit") or not name:
            continue
        if name.startswith(known_prefixes) or name in skip_names:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        label = _label_for(page, el)
        unanswered.append(label or f"(unlabeled field: {el.get_attribute('id') or name})")

    unanswered.append("Solve the 'Human Check' reCAPTCHA before submitting.")

    return {"platform": "jazzhr", "needs_review": unanswered, "submitted": False}


def _label_for(page: Page, el) -> str | None:
    el_id = el.get_attribute("id")
    if el_id:
        label = page.query_selector(f'label[for="{el_id}"]')
        if label:
            return label.text_content().strip()
    container = el.evaluate_handle("el => el.closest('li') || el.closest('div')")
    if container:
        text = container.as_element().text_content()
        return text.strip()[:120] if text else None
    return None
