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

Third real gap found and fixed live 2026-08-27: several companies embed
Greenhouse's application widget on their own branded domain via a
`gh_jid=` query param (see ats/detect.py's pattern for this) instead of
linking to `boards.greenhouse.io` directly — confirmed on PsiQuantum,
Jump Trading, and Waymo. The actual form fields live inside a
`job-boards.greenhouse.io/embed/job_app?...` iframe on the page, not the
top-level DOM, so every `page.query_selector(...)` call here used to find
nothing. Waymo's variant needs an extra step even the iframe-aware fix
alone doesn't cover: the discovered job URL lands on a description page
with an "Apply now" link, and the iframe only appears after clicking it
(same "one click before the real form" situation ats/ashby.py hit).
`_resolve_context()` below tries, in order: fields already on the
top-level page (the normal `boards.greenhouse.io` case) → an existing
Greenhouse iframe (PsiQuantum/Jump Trading) → clicking an "Apply" link/
button and checking again for the iframe. Everything else in this module
operates on whatever context that resolves to, unchanged.

Known remaining gap, confirmed live but not fixed: Waymo's `gh_jid=` page
doesn't actually embed the classic iframe at all — clicking "Apply" reveals
a form section directly on the same top-level page (`#apply` anchor, no
new iframe), using entirely different, dynamically-suffixed field ids
(`form_first_name_1_3_0` rather than `#first_name`) that also appeared
duplicated across what look like two separate field sets on the one
posting checked. This is a different, newer Greenhouse embeddable-widget
variant, not the same platform version this handler already knows how to
fill — `_resolve_context()` falls back to returning the bare `page` in
this case, so known_ids/aria-required detection still runs and surfaces
real questions, but the standard fields (name/email/phone/resume) won't
get auto-filled here specifically. Solving this properly would need
matching fields by label text the way ats/ashby.py locates LinkedIn,
rather than assuming a fixed id — not done here given the scope already
covered this session.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    """Fills known fields on a Greenhouse application — either a native
    `boards.greenhouse.io` page, or one embedded via `gh_jid=` in another
    company's own page (see module docstring). Returns
    {"platform": "greenhouse", "needs_review": [...]}."""
    ctx = _resolve_context(page)
    unanswered = []

    def fill_if_present(selector: str, value: str | None):
        if not value:
            return
        el = ctx.query_selector(selector)
        if el:
            el.fill(value)

    fill_if_present("#first_name", resume.get("first_name"))
    fill_if_present("#last_name", resume.get("last_name"))
    fill_if_present("#email", resume.get("email"))
    fill_if_present("#phone", resume.get("phone"))

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = ctx.query_selector("#resume")
    resume_uploaded = False
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)
        resume_uploaded = True
        # On some tenants (confirmed live 2026-08-27 on PsiQuantum) the
        # #resume node gets swapped out for a "file attached" widget right
        # after a successful upload, and whatever replaces it can still
        # carry aria-required="true" with no id in `known_ids` below — that
        # produced a false "Resume/CV*" needs_review entry even though the
        # upload genuinely succeeded (verified separately: the filename
        # shows up in the rendered page). Filtered out by label text below
        # now that upload success is tracked explicitly.

    # Anything else required on the form is a per-posting custom question
    # (or an EEO/demographic dropdown) — surface it instead of guessing.
    # `[aria-required="true"]` is the real signal on Greenhouse's current
    # form, not the plain HTML `required` attribute — see module docstring.
    known_ids = {"first_name", "last_name", "email", "phone", "resume", "country"}
    for el in ctx.query_selector_all('[aria-required="true"]'):
        el_id = el.get_attribute("id") or ""
        if el_id in known_ids:
            continue
        label = _label_for(ctx, el)
        if resume_uploaded and label and "resume" in label.lower():
            continue  # see resume_uploaded note above — a real upload, not a real gap
        if el.get_attribute("role") == "combobox":
            label = f"{label or el_id} (dropdown/combobox — needs a real selection, not just typed text)"
        unanswered.append(label or f"(unlabeled field: {el_id or el.get_attribute('name')})")

    return {"platform": "greenhouse", "needs_review": unanswered, "submitted": False}


def _resolve_context(page: Page):
    """Returns whatever should be queried for form fields — see module
    docstring for the three cases this handles."""
    if page.query_selector("#first_name"):
        return page

    iframe_el = page.query_selector("iframe[src*='greenhouse.io']")
    if iframe_el:
        frame = iframe_el.content_frame()
        if frame:
            return frame

    apply_link = page.query_selector("a:has-text('Apply'), button:has-text('Apply')")
    if apply_link:
        apply_link.click()
        page.wait_for_timeout(1500)
        iframe_el = page.query_selector("iframe[src*='greenhouse.io']")
        if iframe_el:
            frame = iframe_el.content_frame()
            if frame:
                return frame

    return page


def _label_for(ctx, el) -> str | None:
    el_id = el.get_attribute("id")
    if el_id:
        label = ctx.query_selector(f'label[for="{el_id}"]')
        if label:
            return label.text_content().strip()
    container = el.evaluate_handle("el => el.closest('div')")
    if container:
        text = container.as_element().text_content()
        if not text:
            return None
        text = text.strip()
        # The container-div fallback can sweep up an entire file-upload
        # widget's button cluster (confirmed live 2026-08-27 on PsiQuantum's
        # Cover Letter field: "Cover Letter*AttachAttachDropboxEnter
        # manually...") when there's no cleaner label association — keep
        # just the heading text before the first upload-button word, which
        # is the actual field name.
        for marker in ("Attach", "Dropbox"):
            idx = text.find(marker)
            if idx > 0:
                text = text[:idx]
        return text.strip()[:120] or None
    return None
