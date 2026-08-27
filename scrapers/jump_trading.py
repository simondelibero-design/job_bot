"""Jump Trading — jumptrading.com/careers.

jumptrading.com/careers is a Webflow marketing page (301s to
/careers) that itself carries no job data — it links out to two separate
sub-pages, `/hr/experienced-candidates` and `/hr/students-new-grads`, each
of which embeds a Greenhouse job-board widget pointed at
`boards-api.greenhouse.io/v1/boards/jumptrading/jobs` (found by grepping
those pages' HTML, confirmed live 2026-08-26: HTTP 200, 109 real current
postings, e.g. "AI Research Scientist | Research & Development" in New
York/London/Singapore — clearly Jump's actual board). See
scrapers/_greenhouse.py for the shared fetch/filter logic and what the
public Greenhouse API does/doesn't expose (no salary or job_type fields).

One real trap avoided: the careers page's own "Join Our Talent Community"
link also points at a `job-boards.greenhouse.io` URL
(`/talent_community/jobs/7138319`) — that is NOT the jobs board, it's a
single Greenhouse-hosted resume-drop form (Jump's talent-community opt-in,
not an open requisition), reached from a totally different Greenhouse
board token (`talent_community`) than the real one. Confirmed by reading
the actual experienced/students pages' embedded widget config rather than
trusting the first greenhouse.io link found on the site.
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "jumptrading"
COMPANY_NAME = "Jump Trading"


def search_jump_trading(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "jump_trading", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    for kw in ("research", "physicist"):
        jobs = search_jump_trading(kw)
        print(f"\n=== {kw!r}: found {len(jobs)} jobs ===")
        for j in jobs[:5]:
            print(j["title"], "-", j["location"], "-", j["url"])
