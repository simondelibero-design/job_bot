"""One-time ZipRecruiter login: opens a real, visible browser window to a
persistent Chromium profile. You log in yourself in that window — this
script never sees or touches your password, it just opens the page and
waits. Playwright writes cookies/session data to the profile directory on
disk continuously as you use the browser, so once you're logged in and
close the window, search_ziprecruiter() can reuse that same profile
directory to browse authenticated.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).parent / "ziprecruiter_profile"


def main():
    PROFILE_DIR.mkdir(exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.ziprecruiter.com/login", wait_until="domcontentloaded")
        print(f"Browser open. Log into ZipRecruiter, then just close the window when done.")
        print(f"Session will be saved to: {PROFILE_DIR}")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        context.close()
        print("Done — session saved.")


if __name__ == "__main__":
    main()
