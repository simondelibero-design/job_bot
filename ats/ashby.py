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

System fields confirmed stable across both postings tested: `#_systemfield_name`
(single full name field, not split first/last), `#_systemfield_email`,
`#phone`, `#_systemfield_resume` (file input). A `#_systemfield_location`
free-text-looking field is actually a JS autocomplete combobox
(`role="combobox"`, no plain value semantics) that needs a selected
suggestion, not just typed text — same caution ats/smartrecruiters.py
already applies to its City field — so this handler does not fill it, and
leaves it (using its own on-page question text) for manual review when
required. LinkedIn/Website/every other custom question use per-posting
numeric IDs (`question_<n>`) that are NOT stable across orgs, so LinkedIn
is located by matching "linkedin" in its question-title label text, not by
a hardcoded ID.

An invisible reCAPTCHA (`size=invisible` anchor iframe, sitekey embedded
in the page) is present on the form but doesn't render any visible
challenge and doesn't block reaching or filling any field — it only fires
on submit, which this project never clicks, so it isn't flagged here
(same "doesn't count against fillable" treatment as every other handler's
submit-time CAPTCHA).
"""
from playwright.sync_api import Page

# Stable across every Ashby org: plain system fields with fixed ids.
_SYSTEM_TEXT_FIELDS = {
    "_systemfield_name": "full_name",
    "_systemfield_email": "email",
    "phone": "phone",
}


def fill_application(page: Page, resume: dict) -> dict:
    """Fills known fields on a real Ashby job page (`jobs.ashbyhq.com/{org}/{id}`)
    or its `.../application` form directly. Returns
    {"platform": "ashby", "needs_review": [...]}.

    Bug found live 2026-08-27, running the real prepare_application()
    pipeline against a fresh queue job rather than a hand-driven test: the
    job URL discovery actually stores (and ats/apply.py navigates to) is
    the listing page, one click before the form — this function used to
    assume it was already on `.../application` (true only because the
    original verification script clicked through manually before calling
    this function, which the real pipeline never does). Now clicks
    "Apply for this Job" itself first if the form isn't already present."""
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

    for field_id, resume_key in _SYSTEM_TEXT_FIELDS.items():
        value = resume.get(resume_key)
        if not value:
            continue
        el = page.query_selector(f"#{field_id}")
        if el:
            el.fill(value)
            handled_paths.add(field_id)

    resume_pdf = resume.get("resume_pdf_path")
    resume_input = page.query_selector("#_systemfield_resume")
    if resume_input and resume_pdf:
        resume_input.set_input_files(resume_pdf)
        handled_paths.add("_systemfield_resume")

    # LinkedIn: real field id is a per-posting numeric question_<n>, so find
    # it by its question-title label text instead of guessing an id.
    linkedin_url = resume.get("linkedin_url")
    if linkedin_url:
        for entry in entries:
            label_el = entry.query_selector(".ashby-application-form-question-title")
            label_text = (label_el.text_content() or "").strip() if label_el else ""
            if "linkedin" in label_text.lower():
                input_el = entry.query_selector("input")
                if input_el:
                    input_el.fill(linkedin_url)
                    handled_paths.add(entry.get_attribute("data-field-path") or "")
                break

    # Everything else that's required and not already answered is a
    # per-posting custom question (or an autocomplete field like location,
    # or an EEO-style radio group) — surface it instead of guessing.
    unanswered = []
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
        unanswered.append(label_text[:150] or f"(unlabeled field: {path})")

    return {"platform": "ashby", "needs_review": unanswered, "submitted": False}
