"""Hamamatsu Corporation (Hamamatsu Photonics' US subsidiary) —
hamamatsu.com/us/en/our-company/hamamatsu-careers.html.

The careers page's "Job board" section embeds a **JazzHR** widget script
(`<script src="https://app.jazz.co/widgets/basic/create/hamamatsucorporation">`,
found by grepping the page HTML for "job board"/"iframe" near the "A
complete listing of open jobs can be found on our job board" text).
JazzHR (`*.applytojob.com`) is already a known platform in this codebase —
`ats/detect.py` recognizes it and `ats/jazzhr.py` can fill its application
form — but no discovery scraper existed for it yet.

Unlike a typical JazzHR embed, this widget script itself is a plain,
public, unauthenticated GET that returns the full job-listing HTML as a
JS string literal (not a JSON endpoint, and not something requiring a
browser to execute) — confirmed live 2026-08-26:

    GET https://app.jazz.co/widgets/basic/create/hamamatsucorporation
        -> HTTP 200, a .js file containing
           `<div class="resumator-job-title ...">Applications Engineer</div>
            <div class="resumator-job-location ...">...`
           for every open posting, plus each posting's real
           `hamamatsucorporation.applytojob.com/apply/<code>/<slug>` URL.

This is regex-parsed the same way nlight.py parses its server-rendered
HTML rather than executed as JS — the content is already there in the
response body, not injected client-side afterward.

The individual `/apply/<code>/<slug>` job pages ARE a JS-rendered React app
(confirmed live: no server-rendered description text anywhere in the raw
HTML, unlike the widget response itself) — fetching a real description
would require a browser, which isn't worth it for the ~5-job board this
company runs. `snippet` is left as an empty string here, an honest gap
(matching how other scrapers here return None/"" for fields their source
genuinely doesn't expose without stepping outside this project's
plain-`requests` constraint), rather than firing up Playwright for a page
this small.

No department, salary, or employment-type field is exposed anywhere in
the widget response, so `job_type` and `salary` are always None.

Verified live 2026-08-26: 5 real postings (Applications Engineer,
Market Research Analyst I, Sales Engineer, Senior Human Resources
Generalist, Test Engineer) — small board, all in Bridgewater NJ /
Remote / multiple states.
"""
import re

import requests

WIDGET_URL = "https://app.jazz.co/widgets/basic/create/hamamatsucorporation"
COMPANY = "Hamamatsu Corporation"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_JOB_RE = re.compile(
    r'resumator-job-title[^>]*">([^<]+)</div>'
    r'<div class="resumator-job-info[^>]*>'
    r'<span class="resumator-job-location[^>]*>Location:\s*</span>([^<]*)</div>'
    r'.*?href="(https://hamamatsucorporation\.applytojob\.com/apply/([A-Za-z0-9]+)/[^"?]+)',
    re.S,
)


def search_hamamatsu(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions but unused — this JazzHR widget has no search
    or location-filter param, just a static listing, so filtering happens
    client-side against the title."""
    resp = requests.get(WIDGET_URL, headers={"User-Agent": _UA}, timeout=20)
    resp.raise_for_status()

    keyword_lower = keyword.lower()
    location_lower = location.lower() if location else None

    results = []
    for title, loc, url, code in _JOB_RE.findall(resp.text):
        title = title.strip()
        loc = loc.strip() or None
        if keyword_lower not in title.lower():
            continue
        if location_lower and (not loc or location_lower not in loc.lower()):
            continue
        results.append({
            "source": "hamamatsu",
            "source_job_id": code,
            "title": title,
            "company": COMPANY,
            "location": loc,
            "salary": None,  # no compensation field anywhere in this widget's response
            "job_type": None,  # no employment-type field either
            "url": url,
            "snippet": "",  # detail pages are JS-rendered — see module docstring
            "search_keyword": keyword,
        })
    return results


if __name__ == "__main__":
    jobs = search_hamamatsu("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs:
        print(j["title"], "-", j["location"], "-", j["url"])
