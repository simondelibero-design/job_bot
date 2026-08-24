"""Discovery runs: search Indeed + ZipRecruiter, score results, and log them
to the database. Three sweeps, all using the same growing SEARCH_KEYWORDS
("specialization") list:
  - run_discovery():            local, distance-tiered around home base
  - run_remote_discovery():     nationwide/US-remote-tagged postings, high-selectivity
  - run_life_change_discovery(): nationwide relocation-open, salary-filtered

Honesty note on "international": Indeed/ZipRecruiter here are both the .com
(US) sites. Searching "Remote" surfaces some globally-open remote roles, but
this isn't real international job-board coverage — that would need querying
country-specific Indeed domains (indeed.co.uk, indeed.de, etc.), which isn't
built yet.

No applying happens here — that's the dashboard's job.
"""
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from config import LOCATION, SEARCH_KEYWORDS
from db.database import init_db, upsert_job, top_jobs
from matcher.scorer import score_job
from scrapers.anl import search_anl
from scrapers.aps import search_aps
from scrapers.fnal import search_fnal
from scrapers.indeed import search_indeed
from scrapers.lanl import search_lanl
from scrapers.llnl import search_llnl
from scrapers.pnnl import search_pnnl
from scrapers.usajobs import search_usajobs
from scrapers.ziprecruiter import search_ziprecruiter

# ZipRecruiter auth: either a persistent browser profile from
# scrapers/ziprecruiter_login.py, or cookies exported from your own regular
# browser and converted with scrapers/convert_cookies.py. Cookies is the
# current path (login is Cloudflare-gated for automated browsers).
ZIPRECRUITER_PROFILE_DIR = Path(__file__).parent / "scrapers" / "ziprecruiter_profile"
ZIPRECRUITER_COOKIES_PATH = Path(__file__).parent / "scrapers" / "ziprecruiter_auth.json"


def _zip_auth_kwargs() -> dict:
    return {
        "profile_dir": str(ZIPRECRUITER_PROFILE_DIR) if ZIPRECRUITER_PROFILE_DIR.exists() else None,
        "storage_state_path": str(ZIPRECRUITER_COOKIES_PATH) if ZIPRECRUITER_COOKIES_PATH.exists() else None,
    }


VALID_SITES = {"indeed", "ziprecruiter", "usajobs", "pnnl", "anl", "fnal", "aps", "llnl", "lanl"}


def _run_sweep(keywords: list[str], location_query: str, radius: int, mode: str,
                headless: bool, sites: list[str] | None = None) -> int:
    sites = set(sites) if sites else VALID_SITES
    unknown = sites - VALID_SITES
    if unknown:
        raise ValueError(f"Unknown site(s): {unknown}. Valid: {VALID_SITES}")

    total_found = 0
    for keyword in keywords:
        found_this_keyword = []

        if "indeed" in sites:
            print(f"[{mode}][indeed] searching: {keyword}")
            try:
                found_this_keyword += search_indeed(keyword, location_query, radius, headless=headless)
            except Exception as e:
                print(f"  indeed search failed for '{keyword}': {e}")

        if "ziprecruiter" in sites:
            print(f"[{mode}][ziprecruiter] searching: {keyword}")
            try:
                found_this_keyword += search_ziprecruiter(
                    keyword, location_query, radius, headless=headless, **_zip_auth_kwargs(),
                )
            except Exception as e:
                print(f"  ziprecruiter search failed for '{keyword}': {e}")

        if "usajobs" in sites:
            print(f"[{mode}][usajobs] searching: {keyword}")
            try:
                found_this_keyword += search_usajobs(keyword, location_query, radius)
            except Exception as e:
                print(f"  usajobs search failed for '{keyword}': {e}")

        if "pnnl" in sites:
            print(f"[{mode}][pnnl] searching: {keyword}")
            try:
                found_this_keyword += search_pnnl(keyword)
            except Exception as e:
                print(f"  pnnl search failed for '{keyword}': {e}")

        if "anl" in sites:
            print(f"[{mode}][anl] searching: {keyword}")
            try:
                found_this_keyword += search_anl(keyword)
            except Exception as e:
                print(f"  anl search failed for '{keyword}': {e}")

        if "fnal" in sites:
            print(f"[{mode}][fnal] searching: {keyword}")
            try:
                found_this_keyword += search_fnal(keyword)
            except Exception as e:
                print(f"  fnal search failed for '{keyword}': {e}")

        if "aps" in sites:
            print(f"[{mode}][aps] searching: {keyword}")
            try:
                found_this_keyword += search_aps(keyword)
            except Exception as e:
                print(f"  aps search failed for '{keyword}': {e}")

        if "llnl" in sites:
            print(f"[{mode}][llnl] searching: {keyword}")
            try:
                found_this_keyword += search_llnl(keyword)
            except Exception as e:
                print(f"  llnl search failed for '{keyword}': {e}")

        if "lanl" in sites:
            print(f"[{mode}][lanl] searching: {keyword}")
            try:
                found_this_keyword += search_lanl(keyword)
            except Exception as e:
                print(f"  lanl search failed for '{keyword}': {e}")

        for job in found_this_keyword:
            result = score_job(
                job["title"], job.get("snippet", ""), job.get("location"),
                mode=mode, salary=job.get("salary"),
            )
            job.update(result)
            job["search_mode"] = mode
            upsert_job(job)
            total_found += 1

        time.sleep(3)  # space out requests between keywords

    return total_found


def run_discovery(keywords=None, headless: bool = True, sites: list[str] | None = None):
    """Local sweep: distance-tiered around home base."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    total = _run_sweep(keywords, LOCATION["query"], LOCATION["radius_miles"], "local", headless, sites)
    print(f"\n[local] Done. {total} listings processed this run.")


def run_remote_discovery(keywords=None, headless: bool = True, sites: list[str] | None = None):
    """Nationwide/US-remote sweep, high-selectivity (REMOTE_MIN_SCORE)."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    # radius is meaningless for "Remote" as a location, but pass a large
    # value rather than 0 — untested whether either site would interpret
    # radius=0 as "exact point only" and over-narrow results.
    total = _run_sweep(keywords, "Remote", 100, "remote", headless, sites)
    print(f"\n[remote] Done. {total} listings processed this run.")


def run_life_change_discovery(keywords=None, headless: bool = True, sites: list[str] | None = None):
    """Nationwide relocation-open sweep, filtered on relevance + pay."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    total = _run_sweep(keywords, "United States", 100, "life_change", headless, sites)
    print(f"\n[life_change] Done. {total} listings processed this run.")


if __name__ == "__main__":
    run_discovery()
    print("\nTop scoring jobs so far:")
    for j in top_jobs(limit=15):
        print(f"  [{j['score']:>4}] {j['title']} — {j['company']} ({j['source']}) — {j['application_status']}")
