"""Attaches to a live prepare_and_open() browser window over its CDP
remote-debugging port and pulls a screenshot — read-only observation, not
control. Lets the assistant actually see what's on screen in the real,
visible window the user is filling out, instead of only trusting the
database's needs_review entry or the user's own description of what they
see. Connecting a second CDP client to read page state doesn't take
keyboard/mouse control away from the user; only sending input would, and
this never does.

Usage: python ats/watch_window.py <job_id> [output_png_path]
"""
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright

from ats.apply import LIVE_VIEW_DIR


def watch(job_id: int, out_path: str) -> dict:
    state_path = LIVE_VIEW_DIR / f"{job_id}.json"
    if not state_path.exists():
        return {"ok": False, "error": f"No live window is currently open for job {job_id} "
                                        "(it may have already been closed, or never had a "
                                        "CDP port recorded — see ats/apply.py's "
                                        "_write_live_view_state for when that happens)."}

    state = json.loads(state_path.read_text())
    port = state["port"]

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=5000)
        except Exception as e:
            return {"ok": False, "error": f"Couldn't attach to port {port} — window is likely "
                                            f"already closed ({type(e).__name__}: {e})"}
        context = browser.contexts[0]
        # launch_persistent_context() starts with its own default blank tab
        # already open, separate from the one prepare_and_open() creates via
        # new_page() for the actual job — confirmed live 2026-08-27 that
        # `context.pages[0]` grabs that leftover blank tab instead. The real
        # page is whichever isn't blank; fall back to the last one opened
        # (new_page() appends) if every page is somehow still blank.
        real_pages = [p for p in context.pages if p.url not in ("about:blank", "")]
        page = real_pages[-1] if real_pages else (context.pages[-1] if context.pages else context.new_page())
        page.screenshot(path=out_path, full_page=True)
        result = {"ok": True, "url": page.url, "title": page.title(), "screenshot": out_path}
        browser.close()  # closes THIS CDP client only — connect_over_cdp never owns the browser process
        return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ats/watch_window.py <job_id> [output_png_path]")
        sys.exit(1)
    job_id_arg = int(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else f"/tmp/retiarius_watch_{job_id_arg}.png"
    print(json.dumps(watch(job_id_arg, out), indent=2))
