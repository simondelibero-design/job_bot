"""Los Alamos National Laboratory (LANL) application filler.

scrapers/lanl.py discovers postings from lanl.jobs (a clean, scrapeable
front end), but every posting's "Apply" link routes to a completely
different system: jobsp1.lanl.gov, running Oracle iRecruitment. Live-
verified 2026-08-24: a plain navigation there returns "Request Rejected" —
an F5-style bot-detection wall (the same one scrapers/lanl.py's docstring
already documented from the discovery side, now confirmed from the apply
side too). This isn't an account-creation gate to detect and stop before —
it's a wall that blocks the page from loading at all.

Per this project's standing rule, bot-detection walls are never fought or
spoofed (same call as ZipRecruiter's Cloudflare block, or SmartRecruiters'
detection of Playwright automation). This handler doesn't attempt
navigation past the lanl.jobs posting page at all — it reports the wall
immediately rather than wasting a request tripping it.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    return {
        "platform": "lanl",
        "needs_review": [
            "LANL's apply flow (jobsp1.lanl.gov, Oracle iRecruitment) is "
            "behind a bot-detection wall that returns 'Request Rejected' to "
            "automated requests — confirmed live, not a guess. Apply "
            "manually from the posting page's 'Apply' link."
        ],
        "submitted": False,
    }
