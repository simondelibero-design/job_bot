"""Ashby (jobs.ashbyhq.com) application filler.

Verified live 2026-08-26/27 against a real Helion Energy posting
(scrapers/helion.py's org board) driven with this project's own Playwright
(not a shared interactive browser tool): `jobs.ashbyhq.com/helion` and
`.../application` load a fully server-rendered SPA with no account-creation
or sign-in gate anywhere in the path — clicking "Apply for this Job" (an
`<a href=".../application">`) drops straight into the real form with every
field already visible. (Note: Form Energy's own hosted jobs page at
`jobs.ashbyhq.com/formenergy` returned `{"organization": null}` from
Ashby's own `ApiOrganizationFromHostedJobsPageName` query and rendered
"Page not found" — that company only embeds the widget on their own site
and has not enabled Ashby's hosted page, a per-org opt-out, not a platform
gate. Helion's hosted page is enabled and was used for all verification
below; scrapers/_ashby.py's API-based discovery still works fine for both.)

Every question on an Ashby form (system fields and per-posting custom
questions alike) is wrapped in a
`div.ashby-application-form-field-entry[data-field-path="<field-id>"]`
containing a `label.ashby-application-form-question-title` with the
question text — these are Ashby's own stable, un-hashed platform class
names (unlike the neighboring `_container_1258i_28`-style CSS-module
classes, which are build-hash-scoped and not to be relied on), consistent
across both Helion job postings inspected. A required question's label
additionally carries a class containing `_required_` (confirmed against
all 10 required questions on the test posting) — more complete than the
native HTML `required` attribute, which Ashby only sets on its four plain
text/file system fields (name/email/phone/resume) and leaves off custom
radio groups, Yes/No button-pairs, and the location autocomplete, even
though the site visibly marks all of those required too.

`#_systemfield_email` and `#_systemfield_resume` (file input) are stable
across every org tested. Name and phone are NOT: confirmed live
2026-08-27 that a second org (Digital Biotechnologies) configures its
form with separate First/Last Name fields rather than Helion's single
combined Name field — and on that split variant, `_systemfield_name`
itself is repurposed to mean just "First Name", while "Last Name" and
"Phone Number" get ordinary per-posting random-UUID field ids exactly
like a custom question, not `phone`. Blindly filling whatever sits at
`#_systemfield_name` with the resume's full name (the original approach)
would silently write "Simon DeLibero" into a field actually labeled
"First Name" on this variant — a real correctness bug, not just a missed
field. Every standard field (first/last/full name, phone, LinkedIn) is
therefore matched generically by its own question-title label text
instead of assumed fixed ids, the same approach already used for
LinkedIn/Website (per-posting numeric `question_<n>` ids that were never
stable to begin with). A `#_systemfield_location` free-text-looking field
is actually a JS autocomplete combobox (`role="combobox"`, no plain value
semantics) that needs a selected suggestion, not just typed text — same
caution ats/smartrecruiters.py already applies to its City field — so
this handler does not fill it, and leaves it for manual review when
required.

An invisible reCAPTCHA (`size=invisible` anchor iframe, sitekey embedded
in the page) is present on the form but doesn't render any visible
challenge and doesn't block reaching or filling any field — it only fires
on submit, which this project never clicks, so it isn't flagged here
(same "doesn't count against fillable" treatment as every other handler's
submit-time CAPTCHA).
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from playwright.sync_api import Page

from db.database import lookup_profile_answer

# Matched against each entry's own question-title label text, most
# specific first — "first name" must be checked before the bare "name"
# fallback, or it would swallow "First Name" too. Only used for entries
# not already filled by the `#_systemfield_*` fast path below.
_LABEL_FIELD_MAP = [
    ("first name", "first_name"),
    ("last name", "last_name"),
    ("phone", "phone"),
    ("linkedin", "linkedin_url"),
    ("name", "full_name"),  # bare "Name" (Helion-style combined field) — checked last
]


def fill_application(page: Page, resume: dict) -> dict:
    """Fills known fields on a real Ashby job page (`jobs.ashbyhq.com/{org}/{id}`)
    or its `.../application` form directly. Returns
    {"platform": "ashby", "needs_review": [...], "auto_answered": [...]}.

    Bug found live 2026-08-27, running the real prepare_application()
    pipeline against a fresh queue job rather than a hand-driven test: the
    job URL discovery actually stores (and ats/apply.py navigates to) is
    the listing page, one click before the form — this function used to
    assume it was already on `.../application` (true only because the
    original verification script clicked through manually before calling
    this function, which the real pipeline never does). Now clicks
    "Apply for this Job" itself first if the form isn't already present.

    Confirmed live 2026-08-27 on a Digital Biotechnologies posting: Ashby
    has a genuinely separate "Autofill from resume" dropzone
    (`.ashby-application-form-autofill-input-root input[type=file]`) above
    the actual form fields — distinct from the real `#_systemfield_resume`
    upload further down — that parses an uploaded resume server-side and
    autofills name/phone/email itself ("Parsing your resume. Autofilling
    key fields..."). Uploaded to first, before anything else, and given
    time to finish; every per-field fill below only ever touches a field
    that's still empty afterward, so the native parse always wins and ours
    is strictly the backup."""
    entries = page.query_selector_all(".ashby-application-form-field-entry")
    if not entries:
        apply_link = page.query_selector("a[href*='/application']")
        if apply_link:
            apply_link.click()
            page.wait_for_timeout(1500)
            entries = page.query_selector_all(".ashby-application-form-field-entry")
    if not entries:
        return {
            "platform": "ashby",
            "needs_review": [
                "Couldn't find the Ashby application form on this page "
                "(layout may have changed, or an account/sign-in gate is "
                "blocking it) — nothing was filled. Review and apply manually."
            ],
            "submitted": False,
        }

    handled_paths = set()
    resume_pdf = resume.get("resume_pdf_path")

    autofill_input = page.query_selector(
        ".ashby-application-form-autofill-input-root input[type='file']"
    )
    if autofill_input and resume_pdf:
        autofill_input.set_input_files(resume_pdf)
        try:
            page.wait_for_selector(
                ".ashby-application-form-autofill-input-root [role='progressbar']",
                state="detached", timeout=8000,
            )
        except Exception:
            page.wait_for_timeout(3000)  # no progressbar seen at all — fall back to a flat wait
        # Confirmed live 2026-08-27: the parsed-resume autofill re-renders
        # the whole form (React remount), which detaches every ElementHandle
        # grabbed before this point — including `entries` above — even
        # though the same selectors still match fine against the new DOM.
        # Re-query everything after the autofill settles rather than reusing
        # stale handles.
        entries = page.query_selector_all(".ashby-application-form-field-entry")

    email = resume.get("email")
    if email:
        el = page.query_selector("#_systemfield_email")
        if el and not (el.input_value() or "").strip():
            el.fill(email)
        if el:
            handled_paths.add("_systemfield_email")

    resume_input = page.query_selector("#_systemfield_resume")
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)
        handled_paths.add("_systemfield_resume")

    # Name/phone/LinkedIn: matched by each entry's own label text rather
    # than assumed ids — see module docstring for why (a single org's form
    # layout choice, e.g. combined vs split name, changes which id means
    # what). First match wins per entry; already-filled entries are skipped
    # so the resume-parse autofill's own values are never overwritten.
    for entry in entries:
        path = entry.get_attribute("data-field-path") or ""
        if path in handled_paths:
            continue
        label_el = entry.query_selector(".ashby-application-form-question-title")
        label_text = (label_el.text_content() or "").strip().lower() if label_el else ""
        if not label_text:
            continue
        for keyword, resume_key in _LABEL_FIELD_MAP:
            if keyword not in label_text:
                continue
            value = resume.get(resume_key)
            if not value:
                break
            input_el = entry.query_selector("input, textarea")
            if not input_el or (input_el.input_value() or "").strip():
                break  # no field to fill, or already populated by native autofill
            input_el.fill(value)
            handled_paths.add(path)
            break

    # Everything else that's required and not already answered is a
    # per-posting custom question (or an autocomplete field like location,
    # or an EEO-style radio group) — surface it instead of guessing, unless
    # we've already got a saved answer for this exact prompt from a past
    # application (db/database.py's profile_answers table).
    unanswered = []
    auto_answered = []
    for entry in entries:
        path = entry.get_attribute("data-field-path") or ""
        if path in handled_paths:
            continue
        label_el = entry.query_selector(".ashby-application-form-question-title")
        if not label_el:
            continue
        is_required = "_required_" in (label_el.get_attribute("class") or "")
        if not is_required:
            continue
        label_text = (label_el.text_content() or "").strip()

        saved_answer = lookup_profile_answer(label_text)
        if saved_answer and _try_answer_entry(entry, saved_answer):
            auto_answered.append(f"{label_text}: {saved_answer}")
            continue

        unanswered.append(label_text[:150] or f"(unlabeled field: {path})")

    return {
        "platform": "ashby", "needs_review": unanswered,
        "auto_answered": auto_answered, "submitted": False,
    }


def _try_answer_entry(entry, answer: str) -> bool:
    """Applies a saved answer to one question entry — a plain text
    input/textarea takes `.fill()` directly; Ashby's Yes/No questions
    render as a pair of plain `<button>` elements (not a real <select> or
    radio input), so the only real way to "answer" one is clicking
    whichever button's own text matches the saved answer (a fuzzy
    startswith/contains check, since a saved answer like "No." should
    still match a button labeled plain "No"). Returns False rather than
    guessing when nothing matches, same caution as every other handler's
    combobox/select fallback."""
    buttons = entry.query_selector_all("button")
    if buttons:
        answer_norm = answer.strip().rstrip(".").lower()
        for btn in buttons:
            btn_text = (btn.text_content() or "").strip().rstrip(".").lower()
            if btn_text and (btn_text == answer_norm or answer_norm.startswith(btn_text)):
                btn.click()
                return True
        return False

    field = entry.query_selector("input, textarea")
    if field:
        tag = (field.evaluate("e => e.tagName") or "").lower()
        if tag == "select":
            try:
                field.select_option(label=answer)
                return True
            except Exception:
                return False
        input_type = (field.get_attribute("type") or "").lower()
        if input_type in ("checkbox", "radio"):
            return False  # not confidently mappable from free-text saved answers
        field.fill(answer)
        return True

    return False
