"""Runs one or more discovery sweeps as a detached background process,
launched by the dashboard's home page. Writes a lock file while running so
the home page can show sweep status and avoid launching overlapping runs
against the same sites.

Usage: python dashboard/run_sweep_bg.py --modes local,remote --sites indeed,ziprecruiter
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config import SEARCH_KEYWORDS  # noqa: E402
from main import run_discovery, run_life_change_discovery, run_remote_discovery  # noqa: E402

LOCK_PATH = Path(__file__).parent / ".sweep_lock.json"

MODE_FUNCS = {
    "local": run_discovery,
    "remote": run_remote_discovery,
    "life_change": run_life_change_discovery,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", required=True, help="comma-separated: local,remote,life_change")
    parser.add_argument("--sites", required=True, help="comma-separated: indeed,ziprecruiter")
    args = parser.parse_args()

    modes = args.modes.split(",")
    sites = args.sites.split(",")

    LOCK_PATH.write_text(json.dumps({
        "status": "running", "modes": modes, "sites": sites,
        "started_at": time.time(), "current_mode": None,
    }))

    try:
        for mode in modes:
            state = json.loads(LOCK_PATH.read_text())
            state["current_mode"] = mode
            LOCK_PATH.write_text(json.dumps(state))
            MODE_FUNCS[mode](keywords=SEARCH_KEYWORDS, headless=True, sites=sites)
    except Exception:
        LOCK_PATH.write_text(json.dumps({
            "status": "error", "modes": modes, "sites": sites,
            "finished_at": time.time(), "error": traceback.format_exc(),
        }))
        return

    LOCK_PATH.write_text(json.dumps({
        "status": "done", "modes": modes, "sites": sites, "finished_at": time.time(),
    }))


if __name__ == "__main__":
    main()
