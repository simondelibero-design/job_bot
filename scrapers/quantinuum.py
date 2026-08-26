"""Quantinuum (quantinuum.com) — major quantum computing company (the
Honeywell Quantum Solutions / Cambridge Quantum merger). Runs its careers
page on Lever, which has a real public JSON API — no auth, no browser
automation, no bot-detection dance. Same tier as usajobs.py.

Finding the right slug took one extra step. Quantinuum's careers page
(quantinuum.com/careers) embeds a Lever apply link, but it's NOT on Lever's
default `jobs.lever.co` / `api.lever.co` domain — confirmed live 2026-08-26
by grepping the page HTML for "lever.co":
    href="https://jobs.eu.lever.co/quantinuum"
That's Lever's *EU-hosted* instance (companies can choose EU vs US data
residency on Lever). The obvious guess, `api.lever.co/v0/postings/quantinuum`,
404s ({"ok":false,"error":"Document not found"}) because that document lives
on the other host. The working endpoint is:
    GET https://api.eu.lever.co/v0/postings/quantinuum?mode=json
Confirmed live 2026-08-26: HTTP 200, 91 postings, no auth needed. If this
board ever moves back to the standard US host, swap API_BASE below.

Lever's public postings API has no free-text/keyword search parameter —
confirmed live by requesting `?query=physicist`, which came back with the
same 91 postings as an unfiltered request. It does support exact-match
category filters (e.g. `location=`), but nothing radius-based or fuzzy. So
this scraper fetches the full posting list in one request and filters
client-side on `keyword` against the job title (case-insensitive substring)
— cheap here since Quantinuum's whole board is under 100 postings. If the
board grows enough that this stops being cheap, Lever does paginate large
boards via `skip`, but wasn't needed to get a complete, correct result at
this size.

`location`, if given, is also just a client-side case-insensitive substring
match against Lever's own `categories.location` string (e.g. "US Broomfield,
CO", "UK Cambridge") — not a geocoded radius search, since Lever's API
doesn't do geocoding either. `radius_miles` is accepted for interface parity
with the other search_* functions but has no effect.

Salary: most postings (72/91 in the live 2026-08-26 check) carry a
`salaryRange` (min/max/currency/interval — USD, per-year or per-month
depending on role); the rest have no `salaryRange` at all, and `salary` is
None for those, matching what a human sees on the page.
"""
import requests

COMPANY = "quantinuum"
API_BASE = f"https://api.eu.lever.co/v0/postings/{COMPANY}"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _format_salary(salary_range: dict | None) -> str | None:
    if not salary_range:
        return None
    lo, hi, currency = salary_range.get("min"), salary_range.get("max"), salary_range.get("currency", "")
    interval_raw = salary_range.get("interval") or ""
    suffix = "a year" if "year" in interval_raw else "a month" if "month" in interval_raw else interval_raw
    symbol = "$" if currency == "USD" else f"{currency} " if currency else ""
    if lo and hi:
        return f"{symbol}{lo:,} - {symbol}{hi:,} {suffix}".strip()
    if lo:
        return f"{symbol}{lo:,} {suffix}".strip()
    return None


def _extract_job(posting: dict, keyword: str) -> dict | None:
    posting_id = posting.get("id")
    if not posting_id:
        return None

    categories = posting.get("categories") or {}

    return {
        "source": "quantinuum",
        "source_job_id": posting_id,
        "title": posting.get("text", ""),
        "company": "Quantinuum",
        "location": categories.get("location"),
        "salary": _format_salary(posting.get("salaryRange")),
        "job_type": categories.get("commitment"),
        "url": posting.get("hostedUrl"),
        "snippet": (posting.get("descriptionBodyPlain") or "").strip()[:1000],
        "search_keyword": keyword,
    }


def search_quantinuum(keyword: str, location: str = None, radius_miles: int = None,
                       limit: int = 50) -> list[dict]:
    """`location`/`radius_miles` are accepted for interface parity with the
    other search_* functions; see module docstring for how (and how little)
    they actually filter here — Lever's public API has no keyword search or
    geocoded radius search, so both `keyword` and `location` are applied
    client-side against the full posting list.
    """
    resp = requests.get(API_BASE, headers=HEADERS, params={"mode": "json"}, timeout=20)
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
        job = _extract_job(posting, keyword)
        if job:
            results.append(job)
        if len(results) >= limit:
            break
    return results


if __name__ == "__main__":
    jobs = search_quantinuum("physicist")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["salary"], "-", j["url"])

    print()
    jobs = search_quantinuum("quantum")
    print(f"Found {len(jobs)} jobs for 'quantum'")
    for j in jobs[:5]:
        print(j["title"], "-", j["location"], "-", j["salary"])
