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
from scrapers.indeed import search_indeed
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


def _run_sweep(keywords: list[str], location_query: str, radius: int, mode: str,
                headless: bool) -> int:
    total_found = 0
    for keyword in keywords:
        print(f"[{mode}][indeed] searching: {keyword}")
        try:
            indeed_jobs = search_indeed(keyword, location_query, radius, headless=headless)
        except Exception as e:
            print(f"  indeed search failed for '{keyword}': {e}")
            indeed_jobs = []

        print(f"[{mode}][ziprecruiter] searching: {keyword}")
        try:
            zip_jobs = search_ziprecruiter(
                keyword, location_query, radius, headless=headless, **_zip_auth_kwargs(),
            )
        except Exception as e:
            print(f"  ziprecruiter search failed for '{keyword}': {e}")
            zip_jobs = []

        for job in indeed_jobs + zip_jobs:
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


def run_discovery(keywords=None, headless: bool = True):
    """Local sweep: distance-tiered around home base."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    total = _run_sweep(keywords, LOCATION["query"], LOCATION["radius_miles"], "local", headless)
    print(f"\n[local] Done. {total} listings processed this run.")


def run_remote_discovery(keywords=None, headless: bool = True):
    """Nationwide/US-remote sweep, high-selectivity (REMOTE_MIN_SCORE)."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    # radius is meaningless for "Remote" as a location, but pass a large
    # value rather than 0 — untested whether either site would interpret
    # radius=0 as "exact point only" and over-narrow results.
    total = _run_sweep(keywords, "Remote", 100, "remote", headless)
    print(f"\n[remote] Done. {total} listings processed this run.")


def run_life_change_discovery(keywords=None, headless: bool = True):
    """Nationwide relocation-open sweep, filtered on relevance + pay."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    total = _run_sweep(keywords, "United States", 100, "life_change", headless)
    print(f"\n[life_change] Done. {total} listings processed this run.")


if __name__ == "__main__":
    run_discovery()
    print("\nTop scoring jobs so far:")
    for j in top_jobs(limit=15):
        print(f"  [{j['score']:>4}] {j['title']} — {j['company']} ({j['source']}) — {j['application_status']}")
