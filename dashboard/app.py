"""Local review dashboard: browse discovered/scored jobs, launch a real
pre-filled browser window for one (via ats/apply.py), and mark outcomes.
Nothing here submits an application — that's always a human action in the
opened browser window.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

sys.path.append(str(Path(__file__).parent.parent))
from config import DEFAULT_DISTANCE_SETTINGS, SETTINGS_PATH, load_distance_settings  # noqa: E402
from db.database import get_conn, restore_job, set_application_status  # noqa: E402

ROOT = Path(__file__).parent.parent
RESUME_DIR = ROOT / "resume"
SWEEP_LOCK_PATH = Path(__file__).parent / ".sweep_lock.json"
VALID_SITES = ["indeed", "ziprecruiter", "usajobs", "pnnl", "anl", "fnal", "aps", "llnl", "lanl", "bnl", "slac", "ornl", "snl"]
VALID_MODES = ["local", "remote", "life_change"]
STATUS_TABS = [
    "needs_review", "discovered", "submitted", "skipped", "rejected",
    "excluded", "semi_excluded", "likely_excluded", "remote", "life_change", "all",
]
PHD_TABS = {"excluded", "semi_excluded", "likely_excluded"}
MODE_TABS = {"remote", "life_change"}
# Default until the formal/personality versions' issues are fully ironed
# out — this is your own originally-typed resume, untouched.
DEFAULT_RESUME = "DeLibero_Resume_original"

app = Flask(__name__)


def available_resumes():
    return sorted(p.stem for p in RESUME_DIR.glob("*.md"))


def sweep_status():
    if not SWEEP_LOCK_PATH.exists():
        return None
    try:
        return json.loads(SWEEP_LOCK_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


@app.route("/")
def home():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
        by_mode = {r["search_mode"] or "local": r["c"] for r in conn.execute(
            "SELECT search_mode, COUNT(*) c FROM jobs GROUP BY search_mode"
        )}
        queued = conn.execute(
            "SELECT COUNT(*) c FROM jobs JOIN applications ON applications.job_id = jobs.id "
            "WHERE jobs.excluded = 0"
        ).fetchone()["c"]

    return render_template(
        "home.html",
        total=total,
        by_mode=by_mode,
        queued=queued,
        sites=VALID_SITES,
        modes=VALID_MODES,
        sweep=sweep_status(),
        distance=load_distance_settings(),
    )


@app.route("/settings/distance", methods=["POST"])
def save_distance_settings():
    settings = {}
    for key, default in DEFAULT_DISTANCE_SETTINGS.items():
        try:
            value = int(request.form.get(key, default))
        except (TypeError, ValueError):
            value = default
        if key == "distance_weight_percent":
            settings[key] = min(100, max(0, value))  # 0 = distance has no effect on ranking
        else:
            settings[key] = max(1, value)  # no zero/negative-mile tiers

    SETTINGS_PATH.write_text(json.dumps(settings, indent=2))

    # Existing DB rows were scored under the old tiers/radius and won't
    # reflect this change on their own (upsert_job does ON CONFLICT DO
    # NOTHING) — rescore now so the queue reflects the new settings
    # immediately instead of only affecting jobs discovered from here on.
    subprocess.Popen(
        [sys.executable, str(ROOT / "matcher" / "rescore.py")],
        cwd=str(ROOT),
    )
    return redirect(url_for("home"))


@app.route("/run-sweep", methods=["POST"])
def run_sweep():
    current = sweep_status()
    if current and current.get("status") == "running":
        return redirect(url_for("home"))  # already running — don't stack another one

    selected_sites = request.form.getlist("sites") or VALID_SITES
    selected_modes = request.form.getlist("modes") or VALID_MODES

    subprocess.Popen(
        [
            sys.executable, str(Path(__file__).parent / "run_sweep_bg.py"),
            "--modes", ",".join(selected_modes),
            "--sites", ",".join(selected_sites),
        ],
        cwd=str(ROOT),
    )
    return redirect(url_for("home"))


@app.route("/queue")
def queue():
    status_filter = request.args.get("status", "needs_review")
    with get_conn() as conn:
        query = (
            "SELECT jobs.*, applications.status AS app_status, "
            "applications.ats_platform, applications.notes "
            "FROM jobs JOIN applications ON applications.job_id = jobs.id "
        )
        params = ()
        if status_filter == "excluded":
            query += "WHERE jobs.excluded = 1 AND (jobs.phd_flag = 'excluded' OR jobs.phd_flag IS NULL) "
        elif status_filter in ("semi_excluded", "likely_excluded"):
            query += "WHERE jobs.phd_flag = ? "
            params = (status_filter,)
        elif status_filter in MODE_TABS:
            # excluded=0 still applies here — a remote/life_change job that
            # didn't clear its own high-selectivity/salary bar is correctly
            # hidden, same as any other excluded job.
            query += "WHERE jobs.excluded = 0 AND jobs.search_mode = ? "
            params = (status_filter,)
        else:
            query += "WHERE jobs.excluded = 0 AND (jobs.search_mode IS NULL OR jobs.search_mode = 'local') "
            if status_filter != "all":
                query += "AND applications.status = ? "
                params = (status_filter,)
        query += "ORDER BY jobs.priority_score DESC, jobs.discovered_at DESC LIMIT 200"
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        for row in rows:
            try:
                row["matched_keywords"] = json.loads(row.get("matched_keywords") or "[]")
            except (TypeError, ValueError):
                row["matched_keywords"] = []

    return render_template(
        "index.html",
        jobs=rows,
        status_filter=status_filter,
        tabs=STATUS_TABS,
        phd_tabs=PHD_TABS,
        resumes=available_resumes(),
        default_resume=DEFAULT_RESUME,
    )


def _launch_prepare(job_id: int, resume_stem: str) -> bool:
    """Launches ats/apply.py as a detached subprocess for one job — a real,
    visible browser window opens independently and stays open until the
    user closes it. Returns False (and marks the job needs_review with a
    note) if there's no URL to open at all."""
    resume_path = RESUME_DIR / f"{resume_stem}.md"

    with get_conn() as conn:
        row = conn.execute("SELECT url FROM jobs WHERE id = ?", (job_id,)).fetchone()

    if not row or not row["url"]:
        set_application_status(job_id, "needs_review", notes="No URL on file — find/apply manually")
        return False

    subprocess.Popen(
        [sys.executable, str(ROOT / "ats" / "apply.py"), str(job_id), row["url"], str(resume_path)],
        cwd=str(ROOT),
    )
    return True


@app.route("/job/<int:job_id>/prepare", methods=["POST"])
def prepare(job_id):
    resume_stem = request.form.get("resume", DEFAULT_RESUME)
    _launch_prepare(job_id, resume_stem)
    return redirect(request.referrer or url_for("queue"))


@app.route("/queue/prepare-batch", methods=["POST"])
def prepare_batch():
    """Opens several pre-filled browser windows at once instead of one at a
    time — the review step (a human looking at each and clicking submit)
    still happens one window at a time, but you don't have to come back to
    the dashboard and click again between every single one."""
    resume_stem = request.form.get("resume", DEFAULT_RESUME)
    job_ids = [int(j) for j in request.form.getlist("job_ids")]

    # Stagger launches slightly — opening a dozen real Chromium windows in
    # the exact same instant is unnecessarily heavy; a beat between each
    # keeps it responsive without meaningfully slowing the batch down.
    for job_id in job_ids:
        _launch_prepare(job_id, resume_stem)
        time.sleep(0.4)

    return redirect(request.referrer or url_for("queue"))


@app.route("/job/<int:job_id>/action", methods=["POST"])
def action(job_id):
    action_name = request.form["action"]
    status_map = {
        "mark_submitted": "submitted",
        "skip": "skipped",
        "reject": "rejected",
        "requeue": "needs_review",
    }
    if action_name == "restore":
        restore_job(job_id)
    elif action_name in status_map:
        set_application_status(job_id, status_map[action_name])
    return redirect(request.referrer or url_for("queue"))


if __name__ == "__main__":
    app.run(debug=True, port=5151)
