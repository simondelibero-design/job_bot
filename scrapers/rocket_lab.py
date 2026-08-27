"""Rocket Lab USA, Inc. — rocketlabusa.com/careers/ (301s to
rocketlabcorp.com/careers/).

Both rocketlabusa.com/careers/ and rocketlabcorp.com/careers/ sit behind a
genuine **Cloudflare "Just a moment..." managed challenge**
(`cf-mitigated: challenge` response header, JS interstitial, `<title>Just a
moment...</title>` body — confirmed live 2026-08-26 with a plain `curl`,
normal desktop UA, no cookies) — a real bot-detection wall. Per this
project's standing rule, that wall was left untouched: no header spoofing,
no session warm-up, no proxy tricks, nothing.

Instead of giving up on the company, a WebSearch for Rocket Lab's job
listings turned up individual posting URLs at `rocketlabcorp.com/careers/
positions/<slug>-<numeric-id>/`, which look like a Greenhouse-embedded
board's URL shape. That's a hint about the *marketing site's* embed, not
proof of a separate reachable API by itself — so it was verified
independently: `GET https://boards-api.greenhouse.io/v1/boards/rocketlab/
jobs` (a completely different origin from the Cloudflare-gated
rocketlab{usa,corp}.com domains — Greenhouse's own `boards-api.
greenhouse.io`, same public host used by scrapers/anduril.py, waymo.py,
etc.) returns HTTP 200 with 430 real current postings ("Additive
Manufacturing Engineer I/II" in Long Beach, CA; "Apprentice Aerospace
Technician" in Auckland, NZ; postings across Middle River MD and other
real Rocket Lab sites) — confirming `board_token` = "rocketlab" and that
this is a genuine, ungated, standalone public API, not a way of reaching
through the Cloudflare-protected site. See scrapers/_greenhouse.py for the
shared fetch/filter logic and what the public Greenhouse API does/doesn't
expose (no salary or job_type fields).
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "rocketlab"
COMPANY_NAME = "Rocket Lab USA, Inc."


def search_rocket_lab(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "rocket_lab", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_rocket_lab("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
