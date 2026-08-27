"""MicroVision, Inc. (NASDAQ: MVIS) — jobs.lever.co/microvision.

This module exists because of what it found while investigating **Luminar
Technologies** (LIDAR/autonomous-vehicle sensors, formerly NASDAQ: LAZR),
which this project was originally asked to add as its own scraper. Luminar
no longer exists as an independent, hiring company:

  - Luminar filed for Chapter 11 bankruptcy. MicroVision won a Section 363
    bankruptcy-court auction for Luminar's lidar business — the Iris/Halo
    lidar sensor IP, inventory, "key engineering and operations talent,"
    and certain commercial contracts — for $33.2M cash, with the sale
    completing February 3, 2026 (per MicroVision's own investor-relations
    press release and multiple trade-press reports, e.g. WardsAuto,
    checked live 2026-08-26). Luminar as a standalone employer is gone;
    its lidar engineering team was folded into MicroVision.
  - This is confirmed independently by DNS/redirect behavior, not just the
    press release: `www.luminartech.com/careers` still exists but
    308-redirects straight to `microvision.com/careers` (confirmed live
    with Playwright 2026-08-26) — i.e. Luminar's own legacy careers domain
    now points at MicroVision, not a stale/unrelated domain. (Separately,
    `luminar.com` — a plausible-looking guess for Luminar Technologies —
    turned out on inspection to be an unrelated engagement-ring/jewelry
    brand with no connection to the lidar company; disregarded.)
  - `microvision.com/careers` 404s directly (a stale internal link) but its
    real content lives at `microvision.com/about/careers`, confirmed live
    with Playwright, which links out to `https://jobs.lever.co/microvision`
    — a real, public, unauthenticated **Lever** board (`ats/detect.py`
    already knows this platform; see also scrapers/_lever.py).
  - The board's own content confirms this really is the ex-Luminar lidar
    team, not just a name match: 10 of 11 live postings (2026-08-26) are in
    Orlando, FL — Luminar's former headquarters — in roles like "Staff
    Optical Engineer," "Sr. RTL Engineer," and "Senior Electrical
    Engineer," i.e. exactly the hardware/photonics engineering work a lidar
    sensor maker does, not generic MicroVision corporate roles.

Net effect: there is no "Luminar" scraper to build — the company doesn't
hire under that name anymore — but its successor lidar business is a
genuine, fully accessible discovery source, so this scraper covers that
instead, labeled honestly as MicroVision (not mislabeled as Luminar).

Confirmed live 2026-08-26: `GET https://api.lever.co/v0/postings/microvision
?mode=json` returns HTTP 200, no auth, 11 real current postings. Like
Quantinuum/Atom Computing (see scrapers/_lever.py), Lever's public API has
no working keyword search (`?query=...` style params are silently ignored
on this class of board), so this fetches the full list and filters
client-side on the job title. The whole board is small enough (order of
tens of postings) that this is cheap, same as quantinuum.py.

Unlike quantinuum.py, this tenant's `descriptionBodyPlain`/`descriptionPlain`
fields are empty on every posting checked — so `snippet` is built by
stripping HTML from the raw `description` field instead (same technique as
northrop_grumman.py/ipg_photonics.py use for their own HTML description
fields). No posting checked carries a `salaryRange`, so `salary` is always
None here, same honest-gap treatment as those other boards. `job_type` uses
Lever's `categories.commitment` (e.g. "Full Time"); `workplaceType`
(on-site/hybrid/remote) is available per-posting but not a `search_*`
standard field, so it isn't surfaced separately.

Verified live 2026-08-26: 11 total postings, all at MicroVision's Orlando,
FL site except one Chantilly, VA sales role and one Program Manager (also
Orlando); `search_microvision("engineer")` matched 9 by title (Customer
Quality Resident Engineer, Senior Electrical Engineer, Senior Electrical
Engineering Technician, Sr Systems Test Engineer, Sr. RTL Engineer, Sr.
Staff Electrical Engineer, Staff Electrical Engineer, Staff Optical
Engineer, Staff RTL Engineer) — actually run, not estimated.
"""
import html
import re

import requests

COMPANY_SLUG = "microvision"
COMPANY_NAME = "MicroVision, Inc."
API_BASE = f"https://api.lever.co/v0/postings/{COMPANY_SLUG}"
CAREERS_PAGE = "https://microvision.com/about/careers"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _extract_job(posting: dict, keyword: str) -> dict | None:
    posting_id = posting.get("id")
    if not posting_id:
        return None

    categories = posting.get("categories") or {}

    return {
        "source": "microvision",
        "source_job_id": posting_id,
        "title": posting.get("text", ""),
        "company": COMPANY_NAME,
        "location": categories.get("location"),
        "salary": None,  # no salaryRange populated on any posting checked — see module docstring
        "job_type": categories.get("commitment"),
        "url": posting.get("hostedUrl"),
        "snippet": _strip_html(posting.get("description", ""))[:1000],
        "search_keyword": keyword,
    }


def search_microvision(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused (Lever's public API doesn't geocode).
    `location`, if given, is a client-side case-insensitive substring match
    against Lever's `categories.location` string, same as quantinuum.py.
    """
    resp = requests.get(API_BASE, headers=HEADERS, params={"mode": "json"}, timeout=20)
    resp.raise_for_status()
    postings = resp.json()

    keyword_lower = keyword.lower()
    location_lower = location.lower() if location else None

    results = []
    for posting in postings:
        title = posting.get("text", "")
        if keyword_lower not in title.lower():
            continue
        if location_lower:
            posting_location = ((posting.get("categories") or {}).get("location") or "").lower()
            if location_lower not in posting_location:
                continue
        job = _extract_job(posting, keyword)
        if job:
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_microvision("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["salary"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
