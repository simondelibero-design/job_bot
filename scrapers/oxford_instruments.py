"""Oxford Instruments (cryogenics, scientific instrumentation) —
oxinst.com/careers -> jobs.oxinst.com.

oxinst.com/careers links to a separate career-site domain, jobs.oxinst.com,
running SAP SuccessFactors' "Jobs2Web" recruiting-marketing platform
(identified from `/platform/js/j2w/...` script paths and
`rmkcdn.successfactors.com`/`successfactors.com` asset hosts in the page
source — confirmed live 2026-08-26). See scrapers/_successfactors.py for
the shared fetch/paginate/filter logic and, importantly, for why this
helper does NOT trust the site's own `?q=` search parameter (confirmed
live: it silently ignores the query and returns a fixed subset instead of
filtering).

Verified live 2026-08-26: 89 total open postings across the full board
(paginated in pages of 25 via `&startrow=N`); "cryogenic" matched 3 real
postings after client-side filtering (Cryogenic Engineer roles); "engineer"
matched dozens (Test Engineer, Manufacturing Engineer, Field Service
Engineer, etc.) across Bristol/High Wycombe (UK), Ulm (DE), and other
sites worldwide.
"""
from scrapers._successfactors import fetch_successfactors_jobs

BASE_URL = "https://jobs.oxinst.com"
COMPANY = "Oxford Instruments"


def search_oxford_instruments(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_successfactors_jobs(BASE_URL, "oxford_instruments", COMPANY, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_oxford_instruments("cryogenic")
    print(f"Found {len(jobs)} jobs for 'cryogenic'")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])

    print()
    jobs = search_oxford_instruments("engineer")
    print(f"Found {len(jobs)} jobs for 'engineer'")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"])
