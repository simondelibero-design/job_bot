"""Atom Computing (quantum computing) — jobs.lever.co/atomcomputing.

Originally fingerprinted as a Greenhouse board (wrong guess); its real
careers page links to Lever instead, confirmed live 2026-08-26:
api.lever.co/v0/postings/atomcomputing returns HTTP 200 with 25 real
current postings, on Lever's default US host (not the EU host Quantinuum
needs). See scrapers/_lever.py for the shared fetch/filter logic.
"""
from scrapers._lever import fetch_lever_jobs

COMPANY_SLUG = "atomcomputing"
COMPANY_NAME = "Atom Computing"


def search_atomcomputing(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_lever_jobs(COMPANY_SLUG, "atomcomputing", COMPANY_NAME, keyword, location)


if __name__ == "__main__":
    jobs = search_atomcomputing("quantum")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
