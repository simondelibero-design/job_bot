"""TAE Technologies (fusion energy, + Life Sciences and Power Solutions
business units) — tae.com/careers -> recruiting2.ultipro.com/TRI1021TRIAE.

tae.com/careers links to three separate job boards, one per TAE business
unit, all on the same **UltiPro / UKG Pro Recruiting** tenant (an ATS not
previously used by any scraper in this codebase), found by grepping the
careers page HTML for `ultipro.com`:
  - Fusion Opportunities:         JobBoard/05964d7e-3712-439c-afd8-1fd295da8aa3
  - Life Sciences Opportunities:  JobBoard/49386e5d-f909-4648-8335-415ce97e3f15
  - Power Solutions Opportunities: JobBoard/b6cbf108-69a6-4d98-bddc-0a0869ef7e6d
All three are queried here and merged, same "cover every subsidiary"
approach as scrapers/general_dynamics.py, since TAE's own site presents
them as one company across three job boards, not three separate employers.

Each board's page embeds a plain `<input name="__RequestVerificationToken"
type="hidden" value="...">` anti-forgery token (standard ASP.NET CSRF
handling, no login, no CAPTCHA, no interactive challenge — same category
of thing as the `x-csrf-token` handling in scrapers/northrop_grumman.py),
which its own frontend JS sends back as an `x-requestverificationtoken`
header on the real search call it fires. Confirmed live 2026-08-26 by
driving one board once with Playwright (this project's own script, not the
shared browser tool) and recording the XHR traffic a real page load fires:

    GET  {board_url}/                                   — mints the CSRF
         token + session cookies, same as any normal page load
    POST {board_url}/JobBoardView/LoadSearchResults
         {"opportunitySearch": {"Top": N, "Skip": 0, "QueryString": "<kw>",
           "OrderBy": [...], "Filters": []}, "matchCriteria": {...}}
         headers: x-requestverificationtoken: <token>,
                  x-requested-with: XMLHttpRequest

Then reproduced with plain `requests` (session cookies + token, no
Playwright needed for the actual scrape) and confirmed identical live
results. `QueryString` is a real server-side search across all three
boards (confirmed live: "engineer" returns 34 combined results, including
some — e.g. "Senior Scientist - Plasma Diagnostics" — whose title doesn't
literally contain the word, implying it matches against description text
too, not just the title), unlike the client-side-only filtering needed for
Greenhouse/Lever/Ashby.

Each result carries a `BriefDescription` (used as the snippet — there's no
extra detail-page JSON endpoint; `OpportunityDetail` is an HTML page, not
an API), `FullTime` (mapped to job_type), and structured `Locations`
(city/state/country). No salary/compensation field exists anywhere in this
API's schema, so `salary` is always None. The job URL is built from the
confirmed-live `OpportunityDetailLink` binding pattern:
`{board_url}/OpportunityDetail?opportunityId={Id}`.

Verified live 2026-08-26: unfiltered totals were 5 (Fusion), 26 (Life
Sciences), 6 (Power Solutions) postings.
"""
import re

import requests

TENANT_BASE = "https://recruiting2.ultipro.com/TRI1021TRIAE/JobBoard"
COMPANY = "TAE Technologies"
BOARDS = {
    "Fusion": "05964d7e-3712-439c-afd8-1fd295da8aa3",
    "Life Sciences": "49386e5d-f909-4648-8335-415ce97e3f15",
    "Power Solutions": "b6cbf108-69a6-4d98-bddc-0a0869ef7e6d",
}

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TOKEN_RE = re.compile(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"')

_PAGE_SIZE = 50
_MAX_RESULTS = 100  # safety cap per board


def _new_session_and_token(board_url: str) -> tuple[requests.Session, str]:
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})
    resp = session.get(f"{board_url}/?q=&o=postedDateDesc", timeout=20)
    resp.raise_for_status()
    match = _TOKEN_RE.search(resp.text)
    if not match:
        raise RuntimeError(f"tae: couldn't find CSRF token at {board_url}")
    return session, match.group(1)


def _extract_job(opp: dict, board_name: str, board_url: str, keyword: str) -> dict | None:
    opp_id = opp.get("Id")
    if not opp_id:
        return None

    locations = opp.get("Locations") or []
    location_names = []
    for loc in locations:
        addr = loc.get("Address") or {}
        city = addr.get("City")
        state = (addr.get("State") or {}).get("Code")
        if city and state:
            location_names.append(f"{city}, {state}")
        elif loc.get("LocalizedDescription"):
            location_names.append(loc["LocalizedDescription"])

    return {
        "source": "tae",
        "source_job_id": opp.get("RequisitionNumber") or opp_id,
        "title": f"{opp.get('Title', '')} ({board_name})",
        "company": COMPANY,
        "location": "; ".join(location_names) if location_names else None,
        "salary": None,  # no compensation field anywhere in this API's schema
        "job_type": "Full-time" if opp.get("FullTime") else "Part-time",
        "url": f"{board_url}/OpportunityDetail?opportunityId={opp_id}",
        "snippet": (opp.get("BriefDescription") or "").strip()[:1000],
        "search_keyword": keyword,
    }


def _search_board(board_name: str, board_guid: str, keyword: str) -> list[dict]:
    board_url = f"{TENANT_BASE}/{board_guid}"
    session, token = _new_session_and_token(board_url)

    payload = {
        "opportunitySearch": {
            "Top": _PAGE_SIZE,
            "Skip": 0,
            "QueryString": keyword,
            "OrderBy": [{"Value": "postedDateDesc", "PropertyName": "PostedDate", "Ascending": False}],
            "Filters": [],
        },
        "matchCriteria": {
            "PreferredJobs": [], "Educations": [], "LicenseAndCertifications": [],
            "Skills": [], "hasNoLicenses": False, "SkippedSkills": [],
        },
    }
    resp = session.post(
        f"{board_url}/JobBoardView/LoadSearchResults",
        headers={
            "x-requestverificationtoken": token,
            "x-requested-with": "XMLHttpRequest",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    opportunities = resp.json().get("opportunities", [])

    results = []
    for opp in opportunities[:_MAX_RESULTS]:
        extracted = _extract_job(opp, board_name, board_url, keyword)
        if extracted:
            results.append(extracted)
    return results


def search_tae(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location`, if given, is a client-side
    case-insensitive substring match against the assembled location string
    — no geocoding. `keyword` IS honored server-side via UltiPro's own
    `QueryString` full-text search, unlike the client-side-only filtering
    Greenhouse/Lever/Ashby's public APIs need."""
    all_results = []
    for board_name, board_guid in BOARDS.items():
        try:
            all_results.extend(_search_board(board_name, board_guid, keyword))
        except requests.RequestException:
            continue  # one board failing shouldn't sink the other two

    if location:
        location_lower = location.lower()
        all_results = [r for r in all_results if r["location"] and location_lower in r["location"].lower()]

    return all_results


if __name__ == "__main__":
    jobs = search_tae("engineer")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:120])
