"""Converts a Cookie-Editor JSON export into Playwright's storage_state
format, so search_ziprecruiter() can reuse a session you logged into
yourself in your own regular browser. Never touches your password — this
only ever handles already-issued session cookies.

Usage: python scrapers/convert_cookies.py [raw_export.json]
Defaults to ziprecruiter_cookies_raw.json in this directory, writes
ziprecruiter_auth.json next to it.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_INPUT = HERE / "ziprecruiter_cookies_raw.json"
OUTPUT = HERE / "ziprecruiter_auth.json"

SAME_SITE_MAP = {
    "no_restriction": "None",
    "unspecified": "Lax",
    "lax": "Lax",
    "strict": "Strict",
    "none": "None",
}


def convert(raw_cookies: list[dict]) -> dict:
    cookies = []
    for c in raw_cookies:
        same_site = SAME_SITE_MAP.get(str(c.get("sameSite", "")).lower(), "Lax")
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".ziprecruiter.com"),
            "path": c.get("path", "/"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", True),
            "sameSite": same_site,
        }
        expires = c.get("expirationDate")
        cookie["expires"] = expires if expires else -1
        cookies.append(cookie)
    return {"cookies": cookies, "origins": []}


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if not input_path.exists():
        print(f"No file at {input_path}. Export cookies from Cookie-Editor and save them there first.")
        sys.exit(1)

    raw = json.loads(input_path.read_text())
    if isinstance(raw, dict) and "cookies" in raw:
        raw = raw["cookies"]

    state = convert(raw)
    OUTPUT.write_text(json.dumps(state, indent=2))
    print(f"Wrote {len(state['cookies'])} cookies to {OUTPUT}")


if __name__ == "__main__":
    main()
