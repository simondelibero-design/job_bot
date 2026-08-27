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

Real bug found and fixed live 2026-08-27, running the actual
prepare_application() pipeline against fresh IonQ/Anduril postings rather
than the original single hand-inspected one: Greenhouse's current form
marks required fields with `aria-required="true"`, not the plain HTML
`required` attribute this handler originally looked for. The old
`input[required]` selector was matching 8 unrelated, unlabeled hidden
helper inputs (internal to a JS-managed combobox) instead of the real
custom questions, producing useless `"(unlabeled field: None)"`
needs_review entries on every posting instead of the actual questions.
Confirmed live: `label[for="<id>"]` lookup still works correctly once
matched against the right elements — `_label_for` itself wasn't broken,
only the selector feeding it was. Also found: Greenhouse renders both the
real geocoded `#candidate-location` field AND plain fixed-choice custom
questions (e.g. "Are you authorized to work...?") with the identical
`role="combobox" aria-autocomplete="list" aria-haspopup="true"` pattern —
confirmed live, no attribute reliably tells them apart. Either way,
neither can be safely answered with a plain `.fill()` (that types text
into the box but never performs the click/arrow-key selection the widget
needs to register a real answer), so every combobox-role field is flagged
generically rather than guessing which kind it is.

Known minor limitation, not worth chasing further: `_label_for`'s
container-div fallback (used when a required element has no matching
`label[for]`) can occasionally grab unrelated nearby text — confirmed
live on IonQ's posting, where a hidden required element inside the resume
section's wrapper div produces a spurious "Resume/CV*" needs_review entry
even though the resume upload itself succeeded correctly (verified
separately: the filename shows up in the page after fill). Harmless
false positive, not a real gap in what gets filled.
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
    # `[aria-required="true"]` is the real signal on Greenhouse's current
    # form, not the plain HTML `required` attribute — see module docstring.
    known_ids = {"first_name", "last_name", "email", "phone", "resume", "country"}
    for el in page.query_selector_all('[aria-required="true"]'):
        el_id = el.get_attribute("id") or ""
        if el_id in known_ids:
            continue
        label = _label_for(page, el)
        if el.get_attribute("role") == "combobox":
            label = f"{label or el_id} (dropdown/combobox — needs a real selection, not just typed text)"
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
