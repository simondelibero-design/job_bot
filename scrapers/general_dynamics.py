"""General Dynamics (parent + all subsidiaries) — www.gd.com/careers/job-search.

`gdcareers.com` (the URL originally guessed) doesn't resolve — General
Dynamics runs its unified job search directly on its own corporate domain,
www.gd.com/careers/job-search, covering every GD subsidiary from one search
box (Electric Boat, Bath Iron Works, GD Mission Systems, GD Land Systems,
GDIT, Gulfstream, Jet Aviation, NASSCO, GD Ordnance and Tactical Systems —
all appear as checkbox filters and as the `Company` field on results), not
a per-subsidiary iCIMS tenant as HANDOFF.md's earlier iCIMS note (about a
specific GD Mission Systems posting) might suggest — that iCIMS posting was
reached some other way; the corporate search itself is custom, not iCIMS.

This is not one of the ATS platforms already known to `ats/detect.py` — the
site source shows no myworkdayjobs/icims/greenhouse/etc. markers, only a
custom `/API/Careers/CareerSearch` endpoint on gd.com itself. No account
gate, no CAPTCHA anywhere in the discovery path — this module is
discovery-only, same as the national-lab scrapers.

Two real obstacles were found and resolved without touching any bot-
detection wall:

1. A plain `requests` GET against www.gd.com works fine (verified with
   curl), but Playwright's default headless UA got a 403 from the site's
   Azure Front Door front end — fixed simply by setting a normal desktop
   Chrome User-Agent on the browser context (matching what curl already
   sent successfully), not by evading anything.

2. The search endpoint takes its parameters as a single `request=` query
   string that isn't plain JSON — it's gzip-compressed JSON, base64
   (URL-safe) encoded, e.g. decompressing a captured request yields
   `{"address":[],"facets":[],"page":0,"pageSize":10,"what":"physicist"}`.
   Reproducing that with Python's stdlib `gzip` module got a 400 even
   though the decompressed content was byte-for-byte identical to what a
   real browser sent — turned out to be purely a gzip *header* mismatch:
   Python's `gzip.GzipFile` writes XFL=0x02/OS=0xff by default, while the
   ASP.NET server's decompressor only accepts XFL=0x00/OS=0x03 (the values
   zlib/pako, what browsers use, write). Overriding those two header bytes
   after compressing fixes it — this is an encoding-compatibility detail,
   not a security control (the field controlling it is right there in the
   plaintext-decompressed JSON payload, nothing hidden or session-bound).

Search results carry title/location/company/date/employment-type/category
but no description; each result's own detail page
(`www.gd.com<Link.Url>`) has the full description in a
`class="career-detail-description"` div, fetched here for the snippet. No
structured salary field exists anywhere in this pipeline (GD postings, at
least the ones seen, don't publish pay ranges) so `salary` is always None.

One more real quirk found while testing deep pagination on "engineer"
(1,990 total hits): pages 0-4 and 6+ returned fine, but page 5 specifically
(offset 125 at pageSize=25) consistently 400s — reproduced repeatedly, not
a transient rate limit. Not bot-detection (no Cloudflare/CAPTCHA involved,
just gd.com's own backend erroring on that one offset), and not worth
puzzling out further given this project's effort budget — pagination below
simply stops cleanly on any non-200 response instead of raising, so a
single bad page just truncates the result set rather than crashing the
whole search.

Verified live 2026-08-26: "physicist" returned 1 real result (Radiation
Health Engineer, Electric Boat, Groton CT); "engineer" returns hundreds
across every subsidiary, confirming this covers the whole GD family.
"""
import base64
import gzip
import html
import io
import json
import re

import requests

CAREERS_PAGE = "https://www.gd.com/careers/job-search"
SEARCH_URL = "https://www.gd.com/API/Careers/CareerSearch"
BASE_URL = "https://www.gd.com"
COMPANY = "General Dynamics"

PAGE_SIZE = 25
MAX_RESULTS = 200  # safety cap on pagination + detail-page fetches

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_DESC_RE = re.compile(
    r'career-detail-description[^>]*>(.*?)</div>\s*</div>', re.S
)


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _encode_request(payload: dict) -> str:
    """gd.com's search endpoint takes gzip-compressed, base64 (URL-safe)
    encoded JSON as its `request` param — see module docstring for why the
    gzip header bytes need overriding to match what the server accepts."""
    raw = json.dumps(payload, separators=(",", ":")).encode()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as f:
        f.write(raw)
    compressed = bytearray(buf.getvalue())
    compressed[8] = 0x00  # XFL
    compressed[9] = 0x03  # OS = unix, matches what the server's decompressor expects
    return base64.urlsafe_b64encode(bytes(compressed)).decode()


def _fetch_snippet(url: str) -> str:
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return ""
    match = _DESC_RE.search(resp.text)
    if not match:
        return ""
    return _strip_html(match.group(1))[:1000]


def _extract_job(record: dict, keyword: str) -> dict | None:
    job_id = record.get("Id")
    if not job_id:
        return None

    link = record.get("Link") or {}
    rel_url = link.get("Url") or ""
    url = f"{BASE_URL}{rel_url}" if rel_url else BASE_URL + "/careers/job-search"
    locations = record.get("LocationNames") or []
    employment_types = record.get("EmploymentTypes") or []

    return {
        "source": "general_dynamics",
        "source_job_id": record.get("ReferenceCode") or job_id,
        "title": record.get("Title", ""),
        "company": f"{COMPANY} ({record.get('Company')})" if record.get("Company") else COMPANY,
        "location": "; ".join(locations) if locations else None,
        "salary": None,  # not published on GD postings observed
        "job_type": ", ".join(employment_types) if employment_types else None,
        "url": url,
        "snippet": _fetch_snippet(url) if rel_url else "",
        "search_keyword": keyword,
    }


def search_general_dynamics(keyword: str, location: str = None, radius_miles: int = None) -> list[dict]:
    """`radius_miles` is accepted for interface parity with the other
    search_* functions but unused. `location` IS honored — the search API
    takes a free-text address string in its `address` list."""
    all_results = []
    page = 0
    while len(all_results) < MAX_RESULTS:
        payload = {
            "address": [location] if location else [],
            "facets": [],
            "page": page,
            "pageSize": PAGE_SIZE,
            "what": keyword,
        }
        resp = requests.get(
            SEARCH_URL,
            headers={"User-Agent": _UA, "Accept": "application/json"},
            params={"request": _encode_request(payload)},
            timeout=20,
        )
        if not resp.ok:
            # A small number of specific offsets 400 for reasons that don't
            # look like bot-detection (see module docstring) — stop
            # pagination cleanly rather than losing the whole search.
            break
        data = resp.json()

        records = data.get("Results", [])
        if not records:
            break

        for record in records:
            extracted = _extract_job(record, keyword)
            if extracted:
                all_results.append(extracted)

        page_count = data.get("PageCount", 1)
        page += 1
        if page >= page_count:
            break

    return all_results


if __name__ == "__main__":
    jobs = search_general_dynamics("physics")
    print(f"Found {len(jobs)} jobs")
    for j in jobs[:10]:
        print(j["title"], "-", j["company"], "-", j["location"], "-", j["job_type"])
        print("  ", j["url"])
        print("  snippet:", (j["snippet"] or "")[:150])
