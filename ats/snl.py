"""Sandia National Laboratories (SNL) application filler.

Two separate, compounding reasons this can't be automated further, both
confirmed live 2026-08-24 (not assumed):

1. No stable per-posting URL exists at all. Sandia's Oracle PeopleSoft
   Fluid HCM "Candidate Gateway" (cg.sandia.gov) never changes the browser
   URL as you navigate search results and job details — see
   scrapers/snl.py's docstring for the full explanation. Every SNL job's
   `url` in this project's DB is therefore the same generic search-app
   link, not a link to a specific posting, so there's no page to land on
   and fill in the first place.
2. Even from a specific posting (reached by hand, searching by Job ID),
   clicking "Apply for Job" opens a "Sign In" modal requiring a PeopleSoft
   account ("Are you a new user? Register Now") before any application
   field appears — the same account-creation family as Workday/Taleo/
   SuccessFactors/ORNL.

Creating accounts is off-limits for automation here, and there's no
specific posting to reach anyway, so this reports both limitations
honestly rather than pretending either doesn't exist.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    return {
        "platform": "snl",
        "needs_review": [
            "Sandia's career site has no stable per-posting link (Oracle "
            "PeopleSoft Fluid keeps everything on one search-app URL) and "
            "requires signing in or creating an account before applying to "
            "anything. Go to sandia.gov/careers, search by the Job ID "
            "logged for this posting, and apply manually."
        ],
        "submitted": False,
    }
