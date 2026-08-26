"""Apply-fill orchestrator: given a job's URL, detects the ATS platform,
fills what it can, and always stops at 'needs_review' — nothing in this
project submits an application automatically. That's a deliberate design
choice (see conversation/README): CAPTCHAs, custom screening questions, and
the final submit click all require a human look before anything goes out.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright

from ats.detect import detect_platform
from ats.greenhouse import fill_application as fill_greenhouse
from ats.lever import fill_application as fill_lever
from ats.workday import fill_application as fill_workday
from ats.icims import fill_application as fill_icims
from ats.jazzhr import fill_application as fill_jazzhr
from ats.smartrecruiters import fill_application as fill_smartrecruiters
from ats.taleo import fill_application as fill_taleo
from ats.successfactors import fill_application as fill_successfactors
from ats.aps import fill_application as fill_aps
from ats.lanl import fill_application as fill_lanl
from ats.ornl import fill_application as fill_ornl
from ats.slac import fill_application as fill_slac
from ats.snl import fill_application as fill_snl
from db.database import set_application_status, update_job_url

HANDLERS = {
    "greenhouse": fill_greenhouse,
    "lever": fill_lever,
    "workday": fill_workday,
    "icims": fill_icims,
    "jazzhr": fill_jazzhr,
    "aps": fill_aps,
    "lanl": fill_lanl,
    "ornl": fill_ornl,
    "slac": fill_slac,
    "snl": fill_snl,
    "smartrecruiters": fill_smartrecruiters,
    "taleo": fill_taleo,
    "successfactors": fill_successfactors,
}


def _navigate_and_detect(page, job_id: int, job_url: str) -> str:
    """Navigates to job_url and detects the ATS platform from wherever the
    browser actually ends up (`page.url`) rather than the URL we started
    with. This matters for Indeed/ZipRecruiter jobs: their stored URL is a
    click-tracking redirect (e.g. Indeed's `/rc/clk?jk=...`), not the real
    application page, so detect_platform() against it always returns
    "unknown" even when the job is genuinely hosted on a recognized
    platform. Playwright's goto() already follows the HTTP redirect chain
    on its own — this just reads where it landed afterward. If that's a
    different URL than what we started with, persist it so future views
    (e.g. the dashboard's "Easy Apply Only" filter) see the real
    destination instead of the tracking link forever."""
    page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)
    resolved_url = page.url
    if resolved_url and resolved_url != job_url:
        update_job_url(job_id, resolved_url)
    return detect_platform(resolved_url)


def prepare_application(job_id: int, job_url: str, resume: dict, headless: bool = True) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        platform = _navigate_and_detect(page, job_id, job_url)
        handler = HANDLERS.get(platform)

        if handler is None:
            browser.close()
            set_application_status(job_id, "needs_review", notes=f"Unknown ATS platform for {job_url}")
            return {"platform": "unknown", "needs_review": ["Unrecognized ATS — apply manually"]}

        result = handler(page, resume)
        browser.close()

    notes = "; ".join(result["needs_review"]) if result["needs_review"] else "Auto-filled, ready to review"
    set_application_status(job_id, "needs_review", ats_platform=platform, notes=notes)
    return result


def prepare_and_open(job_id: int, job_url: str, resume: dict):
    """Opens a real, visible browser window with the application pre-filled
    and leaves it open until the user closes it themselves. Meant to be run
    as its own process (e.g. launched by the dashboard) — blocks on the
    browser window closing rather than on stdin, since a subprocess launched
    from a web server has no interactive terminal to read from. The human
    reviews, solves any CAPTCHA, answers custom questions, and clicks submit
    themselves; this script never does any of that."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        platform = _navigate_and_detect(page, job_id, job_url)
        handler = HANDLERS.get(platform)

        if handler:
            result = handler(page, resume)
            notes = "; ".join(result["needs_review"]) if result["needs_review"] else "Auto-filled, ready to review"
        else:
            notes = f"Unrecognized ATS platform — fill out manually ({job_url})"

        set_application_status(job_id, "needs_review", ats_platform=platform, notes=notes)

        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        browser.close()


if __name__ == "__main__":
    from resume.parser import parse_resume

    if len(sys.argv) < 3:
        print("Usage: python ats/apply.py <job_id> <job_application_url> [resume_md_path]")
        sys.exit(1)

    job_id_arg = int(sys.argv[1])
    url = sys.argv[2]
    resume_path = sys.argv[3] if len(sys.argv) > 3 else str(
        Path(__file__).parent.parent / "resume" / "DeLibero_Resume_formal.md"
    )
    resume_data = parse_resume(resume_path)
    prepare_and_open(job_id_arg, url, resume_data)
