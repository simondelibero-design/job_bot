"""USAJobs.gov — the official federal government jobs board. Unlike Indeed/
ZipRecruiter, this has a real public REST API, so no browser automation or
bot-detection dance here.

Requires a free API key: register at https://developer.usajobs.gov/ with
your email — self-service, no approval wait. Save the result as
scrapers/usajobs_credentials.json (gitignored, same pattern as the
ZipRecruiter session files):
    {"api_key": "your-authorization-key", "user_agent": "your@email.com"}
The user_agent must be the email you registered with — USAJobs requires it
verbatim as a request header, not a browser string.

Verified live 2026-08-26 against a real key (NIST/NRC/FCC/FDA agency-
coverage investigation, see HANDOFF.md Session 5): clean 200s, real current
postings, MatchedObjectDescriptor's field names match what's assumed below.
"""
import json
import re
from pathlib import Path

import requests

BASE_URL = "https://data.usajobs.gov/api/search"
CREDENTIALS_PATH = Path(__file__).parent / "usajobs_credentials.json"


def _load_credentials() -> dict:
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError(
            f"No USAJobs credentials at {CREDENTIALS_PATH}. Register a free API key at "
            "https://developer.usajobs.gov/ and save {\"api_key\": \"...\", \"user_agent\": \"your@email.com\"} there."
        )
    return json.loads(CREDENTIALS_PATH.read_text())


def _format_salary(remuneration: list[dict]) -> str | None:
    if not remuneration:
        return None
    r = remuneration[0]
    lo, hi = r.get("MinimumRange"), r.get("MaximumRange")
    interval = (r.get("RateIntervalCode") or "").lower()
    suffix = "an hour" if "hour" in interval else "a year" if "year" in interval else interval
    if lo and hi:
        return f"${lo} - ${hi} {suffix}".strip()
    if lo:
        return f"${lo} {suffix}".strip()
    return None


def _extract_job(descriptor: dict, keyword: str) -> dict | None:
    position_id = descriptor.get("PositionID")
    if not position_id:
        return None

    locations = descriptor.get("PositionLocation") or [{}]
    location_str = locations[0].get("LocationName") if locations else None

    return {
        "source": "usajobs",
        "source_job_id": position_id,
        "title": descriptor.get("PositionTitle", ""),
        "company": descriptor.get("OrganizationName") or descriptor.get("DepartmentName"),
        "location": location_str,
        "salary": _format_salary(descriptor.get("PositionRemuneration")),
        "job_type": descriptor.get("PositionOfferingType", [{}])[0].get("Name")
        if descriptor.get("PositionOfferingType") else None,
        "url": descriptor.get("PositionURI") or descriptor.get("ApplyURI", [None])[0],
        "snippet": descriptor.get("UserArea", {}).get("Details", {}).get("JobSummary", "")
        if isinstance(descriptor.get("UserArea"), dict) else "",
        "search_keyword": keyword,
    }


def _to_city_state(location: str) -> str:
    """USAJobs' LocationName silently returns zero results for a full
    street address (confirmed live 2026-08-26: "1410 10th Ave, Milton, WA
    98354" -> 0 results, "Milton, WA" -> 6, same keyword/radius) — it wants
    just "City, State" or a ZIP. If `location` looks like a full mailing
    address (a street segment before the city), collapse it to the last
    two comma-separated segments and strip any trailing ZIP. Locations that
    are already just "City, State" (or anything without a leading street
    number) pass through unchanged."""
    parts = [p.strip() for p in location.split(",")]
    if len(parts) < 3:
        return location
    city, state_zip = parts[-2], parts[-1]
    state = re.sub(r"\s*\d{5}(-\d{4})?$", "", state_zip).strip()
    return f"{city}, {state}"


def search_usajobs(keyword: str, location: str, radius_miles: int, results_per_page: int = 25) -> list[dict]:
    creds = _load_credentials()
    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": creds["user_agent"],
        "Authorization-Key": creds["api_key"],
    }
    params = {
        "Keyword": keyword,
        "ResultsPerPage": results_per_page,
    }
    # USAJobs treats "Remote" / "United States" as free-text location names
    # it likely won't geocode meaningfully — omit LocationName/Radius for
    # those so it searches nationwide instead of erroring or returning zero
    # results on an unresolvable place name.
    if location and location.lower() not in ("remote", "united states"):
        params["LocationName"] = _to_city_state(location)
        params["Radius"] = radius_miles

    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("SearchResult", {}).get("SearchResultItems", [])
    results = []
    for item in items:
        descriptor = item.get("MatchedObjectDescriptor", {})
        job = _extract_job(descriptor, keyword)
        if job:
            results.append(job)
    return results


if __name__ == "__main__":
    jobs = search_usajobs("physicist", "Tacoma, WA", 45)
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:5]:
        print(j["title"], "-", j["company"], "-", j["location"], "-", j["salary"])
