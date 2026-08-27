"""Oklo (advanced nuclear, fast fission microreactors) — oklo.com/careers ->
job-boards.greenhouse.io/oklo.

oklo.com itself sits behind a Cloudflare managed challenge (`cf-mitigated:
challenge` on every response, confirmed live 2026-08-26) — that wall was
left untouched, no headers spoofed or challenge solved, per this project's
firm rule against evading bot-detection. But Oklo's actual job data lives
on a separate, independently public host that Cloudflare never gates:
guessing the obvious `board_token` "oklo" against Greenhouse's own public
API resolved directly, no interaction with oklo.com required:

    GET https://boards-api.greenhouse.io/v1/boards/oklo/jobs

Confirmed genuinely Oklo's board, not a coincidental token collision, by
checking the response content (2026-08-26): every posting's
`company_name` reads "Oklo", and job descriptions reference "Oklo
Isotopes" by name (e.g. "Administrative Operations Assistant" supporting
"our Vice President, Oklo Isotopes"). 72 real current postings. A
same-guess against Ashby (jobs.ashbyhq.com/oklo, api.ashbyhq.com/posting-api/job-board/oklo)
was also tried in case Oklo used both — the API 404s and the page is
just Ashby's generic empty-org shell (`<title>Jobs</title>`, no
organization data), so Ashby was ruled out; Greenhouse is the only real
source. See scrapers/_greenhouse.py for the shared fetch/filter logic and
what the public Greenhouse API does/doesn't expose (no salary or job_type
fields).
"""
from scrapers._greenhouse import fetch_greenhouse_jobs

BOARD_TOKEN = "oklo"
COMPANY_NAME = "Oklo"


def search_oklo(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    return fetch_greenhouse_jobs(BOARD_TOKEN, "oklo", COMPANY_NAME, keyword, location, radius_miles)


if __name__ == "__main__":
    jobs = search_oklo("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["url"])
