"""Shared helper for companies hosted on Lever's public postings API.

Lever exposes a real public JSON API for any company's board, no auth:
    GET https://api.lever.co/v0/postings/{company}?mode=json
(or https://api.eu.lever.co/v0/postings/{company}?mode=json for companies
on Lever's EU-hosted instance — see scrapers/quantinuum.py, which needed
that host and predates this shared helper).

Confirmed live 2026-08-26 for rigetti/atomcomputing (both on the default
US host, unlike Quantinuum): no free-text/keyword search parameter exists
on this API — `?query=...` is silently ignored — so filtering happens
client-side against the job title, same as Greenhouse's public API
(scrapers/_greenhouse.py). No structured salary field on either board
checked here; `salaryRange` appears on some postings (see
scrapers/quantinuum.py's `_format_salary`) but not consistently enough to
assume for a new company without checking — left as None here unless a
future caller checks and adds it.
"""
import requests

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _extract_job(posting: dict, source: str, company_name: str, keyword: str) -> dict | None:
    posting_id = posting.get("id")
    if not posting_id:
        return None

    categories = posting.get("categories") or {}

    return {
        "source": source,
        "source_job_id": posting_id,
        "title": posting.get("text", ""),
        "company": company_name,
        "location": categories.get("location"),
        "salary": None,  # no salary field confirmed on this board — see module docstring
        "job_type": categories.get("commitment"),
        "url": posting.get("hostedUrl"),
        "snippet": (posting.get("descriptionBodyPlain") or "").strip()[:1000],
        "search_keyword": keyword,
    }


def fetch_lever_jobs(company_slug: str, source: str, company_name: str, keyword: str,
                      location: str = None, eu_hosted: bool = False, limit: int = 50) -> list[dict]:
    """Fetch and keyword/location-filter a single company's Lever board.

    `location`, if given, is a client-side case-insensitive substring match
    against Lever's `categories.location` string — no geocoding, same as
    quantinuum.py.
    """
    host = "api.eu.lever.co" if eu_hosted else "api.lever.co"
    resp = requests.get(f"https://{host}/v0/postings/{company_slug}", headers=HEADERS,
                         params={"mode": "json"}, timeout=20)
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
        job = _extract_job(posting, source, company_name, keyword)
        if job:
            results.append(job)
        if len(results) >= limit:
            break
    return results
