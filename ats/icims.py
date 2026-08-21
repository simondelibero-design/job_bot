"""iCIMS (*.icims.com) application filler — NOT IMPLEMENTED.

Same situation as Workday: iCIMS postings are heavily tenant-customized,
often multi-page, and sometimes require account creation before the
application form even appears. Needs live inspection against real target
postings before a generic filler can be written honestly.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    return {
        "platform": "icims",
        "needs_review": ["iCIMS not yet supported — requires manual application"],
        "submitted": False,
    }
