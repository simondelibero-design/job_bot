"""FDA ORISE research fellowships/internships — Oak Ridge Institute for
Science and Education (ORISE) opportunities at the U.S. Food and Drug
Administration, including CDRH (Center for Devices and Radiological
Health, the medical-device review center).

Why this exists despite scrapers/usajobs.py already covering the federal
government broadly: FDA's own site (fda.gov/about-fda/jobs-fda/scientific-
internships-fellowships-trainees-and-non-us-citizens, confirmed live
2026-08-26) is explicit that its Student/Fellowship/Senior-Scientist
programs — including the ORISE Research Participation Program — are a
*separate* hiring track from competitive-service federal employment. These
are non-employee research appointments (stipend-based, fixed-term, run by
ORAU/ORISE under a DOE contract, not OPM), so they never appear in
USAJobs.gov's index at all. Confirmed live: a USAJobs search for "medical
device reviewer" returns 0 results (see scrapers/usajobs.py), while this
module's live pull returned 84 open FDA ORISE opportunities the same day,
roughly a third of them CDRH medical-device postings (e.g. "FDA
Interventional Radiological Imaging and Visualization (IRIS) Fellowship",
"FDA Methodological Evaluation of Validation Approaches for AI/ML-Based
Predictive Medical Devices for Regulatory Settings"). Regular FDA staff
*employee* jobs (including CDRH staff roles) ARE on USAJobs already and
don't need this module — this only fills the ORISE-fellowship gap.

Note on eligibility: most listings are Postdoctoral/Graduate, but some are
open to Undergraduate/Post-Bachelor's applicants too (checked live — e.g.
"FDA Medical Acoustics Research Opportunity" lists "Post-Bachelor's" and
"Undergraduate Students" among its AcademicLevels) — so this isn't purely a
PhD-only feed. `search_fda_orise()` doesn't filter by academic level; that's
left to matcher/scorer.py same as everywhere else.

Data source: FDA's own ORISE program page (https://orise.orau.gov/fda/) is
a plain, static, no-bot-detection USWDS site (confirmed live: plain
`requests` GET returns full 200 HTML, no CAPTCHA/JS-challenge/login wall —
same tier as scrapers/aps.py). Its "Current Research Opportunities" page
doesn't embed the listing rows in the HTML itself, though — a small script
(assets/js/positions.min.js) reveals the *real* backend: a public JSONP/
JSON endpoint run by Zintellect (ORISE's shared application-management
platform, used across every ORISE-partner agency, not FDA-specific):
    GET https://www.zintellect.com/Public/Opportunity/ORISECatalog
        ?Organization=U.S.+Food+and+Drug+Administration
This is the exact same request the live page's own DataTables widget
makes client-side — reusing it here is not reverse-engineering a private
API, it's calling the public endpoint the page already calls in the
browser. Confirmed live with a plain browser User-Agent, no auth, no
cookies, no CAPTCHA: clean 200 JSON, 84 current FDA rows. robots.txt was
checked on both hosts before building this: orise.orau.gov disallows a
handful of unrelated paths (/connections/, /growth-sector/, etc.) but
explicitly lists /fda/sitemap.xml as crawlable and doesn't disallow /fda/
at all; zintellect.com has no robots.txt (404) — no crawling restriction
applies to either host used here.

Checked whether NIST/NRC/FCC have the same kind of ORISE portal FDA has
(https://orise.orau.gov/nist/, /nrc/, /fcc/) — all three 302-redirect to
ORISE's generic 404 page, i.e. none of them run a dedicated ORISE program
the way FDA (and DOE, EPA, CDC, USDA, etc.) do. NIST does have a separate,
real, non-USAJobs postdoc channel (the NRC — National Research Council,
i.e. National Academies, not Nuclear Regulatory Commission —
Research Associateship Program, https://ofell.nas.edu/raplab10/opportunity/
opportunities.aspx?LabCode=50, 688 listings, plain scrapable HTML, no bot
wall), but every opportunity there is restricted to Postdoctoral
applicants only — not a fit for Simon's current B.S.-candidate stage, so
no scraper was built for it. See HANDOFF.md for the full writeup of that
investigation.

The `Description` field is always null on this endpoint's list view (only
populated on the individual opportunity's detail page, which would need a
second request per listing) — so `search_fda_orise()`'s keyword filter can
only match against Title/Program/ReferenceCode, not a full description.
That's a real limitation worth knowing about if a keyword doesn't surface
something you'd expect.
"""
import json

import requests

CATALOG_URL = "https://www.zintellect.com/Public/Opportunity/ORISECatalog"
ORGANIZATION = "U.S. Food and Drug Administration"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _fetch_catalog() -> list[dict]:
    resp = requests.get(CATALOG_URL, headers=HEADERS, params={"Organization": ORGANIZATION}, timeout=20)
    resp.raise_for_status()
    # Plain JSON when called without a `callback` param, but defensively
    # strip a JSONP wrapper in case that ever changes.
    text = resp.text.strip()
    if text.startswith("(") and text.endswith(");"):
        text = text[1:-2]
    elif text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    data = json.loads(text)
    return data.get("data", [])


def _extract_job(item: dict, keyword: str) -> dict | None:
    reference_code = item.get("ReferenceCode")
    title = item.get("Title", "")
    if not reference_code or not title:
        return None

    return {
        "source": "fda_orise",
        "source_job_id": reference_code,
        "title": title,
        "company": item.get("Program") or ORGANIZATION,
        "location": item.get("Location"),
        "salary": None,  # stipend amounts aren't exposed on this endpoint
        "job_type": "Fellowship",
        "url": item.get("OpportunityUrl"),
        "snippet": f"{item.get('AcademicLevelText', '')} — apply at {item.get('ApplyUrl', '')}".strip(" —"),
        "search_keyword": keyword,
    }


def search_fda_orise(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — nearly every FDA ORISE opportunity
    is at one of a handful of fixed FDA sites (White Oak/Silver Spring, MD;
    Jefferson, AR), not a geocoded search, same as scrapers/aps.py.

    `keyword` filters client-side against title only (see module docstring
    for why — the API's Description field is always null on the list view).
    Pass an empty string/None to get every current FDA opportunity
    unfiltered.
    """
    items = _fetch_catalog()
    results = []
    for item in items:
        if keyword and keyword.lower() not in item.get("Title", "").lower():
            continue
        job = _extract_job(item, keyword)
        if job:
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_fda_orise("device")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["company"], "-", j["location"])
        print("   ", j["url"])
