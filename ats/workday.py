"""Workday (*.myworkdayjobs.com) application filler — NOT IMPLEMENTED.

Unlike Greenhouse/Lever, Workday isn't a shared hosted form with stable
field names — every company runs its own Workday tenant with a customized
multi-step wizard (account creation, resume parse-and-review, work history
re-entry, custom screening questions, all as separate pages/steps). There's
no generic selector set that works across tenants the way there was for
Greenhouse/Lever.

Building this for real means picking specific target companies' Workday
postings and inspecting each flow live (same process used for Indeed,
ZipRecruiter, Greenhouse, and Lever), then writing per-step handlers. Not
done yet — do that once we have real target postings from a discovery run
that land on Workday.
"""
from playwright.sync_api import Page


def fill_application(page: Page, resume: dict) -> dict:
    return {
        "platform": "workday",
        "needs_review": ["Workday not yet supported — requires manual application"],
        "submitted": False,
    }
