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
from db.database import set_application_status

HANDLERS = {
    "greenhouse": fill_greenhouse,
    "lever": fill_lever,
    "workday": fill_workday,
    "icims": fill_icims,
}


def prepare_application(job_id: int, job_url: str, resume: dict, headless: bool = True) -> dict:
    platform = detect_platform(job_url)
    handler = HANDLERS.get(platform)

    if handler is None:
        set_application_status(job_id, "needs_review", notes=f"Unknown ATS platform for {job_url}")
        return {"platform": "unknown", "needs_review": ["Unrecognized ATS — apply manually"]}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
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
    platform = detect_platform(job_url)
    handler = HANDLERS.get(platform)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

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
