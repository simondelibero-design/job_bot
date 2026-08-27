"""Waymo (Alphabet's autonomous driving unit) — careers.withwaymo.com.

waymo.com/careers 301s to waymo.com/careers/, which 301s again to
**careers.withwaymo.com** — a custom-domain career site whose own JS asset
paths include `assets/sites/controllers/call_to_action/greenhouse/
education_controller...js`, i.e. the literal word "greenhouse" baked into
the site's own build output — a strong signal it's built on **Greenhouse's**
job-board platform even though the visible URL isn't `*.greenhouse.io`.
Confirmed live 2026-08-26: `GET https://boards-api.greenhouse.io/v1/boards/
waymo/jobs` returns HTTP 200 with 354 real current postings (e.g.
"Accountant", "AI Enablement Lead", all Mountain View/San Francisco, CA),
each `absolute_url` pointing back at `careers.withwaymo.com/jobs?gh_jid=...`
— confirming this is genuinely Waymo's board on Greenhouse's standard public
API, same tier as scrapers/anduril.py and scrapers/ionq.py. See
scrapers/_greenhouse.py for the shared fetch/filter logic and what the
public Greenhouse API does/doesn't expose (no salary or job_type fields).

Note: careers.withwaymo.com's own marketing/search pages sit behind an AWS
WAF JS challenge (`*.edge.sdk.awswaf.com/.../challenge.js`, found while
inspecting the site) — untouched here per this project's bot-detection
policy; irrelevant anyway since this scraper only talks to Greenhouse's
separate public API, never to careers.withwaymo.com's own pages.
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "waymo"
COMPANY_NAME = "Waymo"


def search_waymo(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "waymo", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_waymo("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
