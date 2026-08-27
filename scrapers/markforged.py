"""Markforged (additive manufacturing / industrial 3D printing) —
markforged.com/careers (redirects to markforged.com/about/careers).

The careers page embeds real Greenhouse job-board links
(`greenhouse.io/markforged`, confirmed live 2026-08-26 by grepping the page
HTML), so this is the same public, unauthenticated Greenhouse board API
already used by ionq.py/psiquantum.py/rigetti.py's neighbors — see
scrapers/_greenhouse.py for the shared fetch/filter logic and its
documented gaps (no salary field, no employment-type field, no server-side
keyword search on this API).

Verified live 2026-08-26: board_token "markforged" returns 2 real current
postings (Product Marketing Manager and Senior Supply Chain Planner, both
Waltham, MA) — a small board, so most keyword searches will legitimately
return few or zero results; that's the real state of Markforged's board,
not a broken scraper.
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "markforged"
COMPANY = "Markforged"


def search_markforged(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "markforged", COMPANY, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_markforged("manager")
    print(f"Found {len(jobs)} jobs for 'manager'")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])

    print()
    jobs = search_markforged("engineer")
    print(f"Found {len(jobs)} jobs for 'engineer'")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"])
