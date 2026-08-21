# job-bot — Handoff

Written 2026-08-21, mid-session, after this chat session hit two platform-level
`[bio]` blocks (Sonnet 5 safety classifier, cause unknown from the assistant
side — likely a false-positive from dense bio/chem/materials-science
keyword clustering in the config and job listings, but unconfirmed). The user
was told to start a new session. This document exists so a new session (or a
different AI instance) can pick up cleanly with zero context loss.

**Nothing about the actual project is broken.** All the numbers below are
real, verified state, not aspirational — check them yourself before trusting
anything stale.

## What this project is

An automated job-search pipeline for Simon DeLibero (Applied Physics B.S.
candidate, Pacific Lutheran University, expected 05/2027, based in Milton,
WA). Discovers jobs on Indeed + ZipRecruiter, scores them against his field,
and surfaces them in a local dashboard for him to review and apply from —
nothing in this project submits an application automatically; a human always
does the final review, CAPTCHA-solve, and submit click.

Location: `~/Desktop/job-bot/`

## Current real state (verified 2026-08-21)

- **775 jobs** in `db/jobs.db`, split: 354 local, 291 remote, 130 life_change.
- Three **background discovery sweeps were running** at the moment this doc
  was written (local/remote/life_change, each covering keywords 1-25 of 99
  in `config.SEARCH_KEYWORDS`). Check `ps aux | grep "python -c"` — if
  they're still alive, let them finish before launching more; if dead, the
  DB counts above are wherever they left off. Their stdout files were empty
  due to buffering when piped to a file (cosmetic — check DB row counts
  instead of stdout for real progress, they were writing to SQLite
  incrementally as each keyword completed).
- **Not yet run**: keywords 26-99 (of 99 total) for all three modes. The
  sweep needs to continue in chunks — Bash tool caps at 10 min per call, and
  ~25 keywords × 2 sites × ~13s/keyword ≈ 5-6 min per chunk, so chunk size of
  ~25 is a safe margin. Pattern used so far:
  ```python
  from config import SEARCH_KEYWORDS
  from main import run_discovery  # or run_remote_discovery / run_life_change_discovery
  run_discovery(keywords=SEARCH_KEYWORDS[25:50], headless=True)
  ```
  Run each mode/chunk as its own background Bash call.

## What's built and working (all verified against real, live data — not guessed)

- **Discovery**: `scrapers/indeed.py`, `scrapers/ziprecruiter.py` — real
  selectors, tested live. ZipRecruiter is list-only (title/company/location/
  salary, no URL) — login is Cloudflare-gated for automated browsers
  (confirmed live), and cookie export from the user's own browser also
  failed ("kept glitching out," never diagnosed further). Accepted as a
  known limitation.
- **Scoring** (`matcher/scorer.py`, `config.py`):
  - `SEARCH_KEYWORDS` / `SECTOR_WEIGHTS` — the "specialization" list, grown
    across two rounds (physics/engineering/chem/materials/CS/math core, plus
    biomedical, renewable energy, robotics, environmental, defense/naval,
    data/ML, semiconductor fab, civil/structural, patent/IP, welding
    inspection, technical sales, actuarial, STEM outreach). User said to add
    all suggested categories each round, then suggest more next time.
  - Three-tier PhD system, checked in strict priority order, no overlap:
    `PHD_REQUIRED_KEYWORDS` → hard exclude (`phd_flag='excluded'`),
    `PHD_PREFERRED_KEYWORDS` → soft signal (`phd_flag='semi_excluded'`), bare
    "phd"/"ph.d" mention → `phd_flag='likely_excluded'`. Each gets its own
    dashboard tab with a Restore button. "Postdoctoral"/"postdoc" added to
    the required list since those categorically need a completed PhD even
    without the word "PhD" appearing.
  - Credential-gate list (folded into `EXCLUDE_KEYWORDS`, not a separate
    tri-state): catches roles like "Medical Physicist" that require
    CAMPEP-accredited graduate training + board certification but never say
    "PhD" — added after the user flagged a real example the scorer missed.
    Known residual gap: "Therapy Physicist Locum" (same credential-gated
    field, different phrasing) still slips through — not yet fixed.
  - Three search modes, one shared scorer (`mode` param): `local`
    (distance-tiered: 0-10mi accepts everything, 10-20mi light filter,
    20-45mi full relevance filter, unresolvable locations default to
    strictest), `remote` (flat `REMOTE_MIN_SCORE=9`, no geography),
    `life_change` (score ≥ `LIFE_CHANGE_MIN_SCORE=6` AND estimated salary ≥
    `LIFE_CHANGE_MIN_SALARY=$90k`, salary parsed via `matcher/salary.py`).
  - Origin point for distance: 1410 10th Ave, Milton, WA 98354 (user's real
    address), radius 45mi. City-coordinate table in `matcher/distance.py` —
    substring-matches known Puget Sound cities against the location string
    (fixed from an earlier too-greedy regex that failed on strings like
    "Hybrid work in Seattle, WA 98101").
  - `matcher/rescore.py` — re-scores every existing DB row against current
    `config.py` rules. **Needed** because `upsert_job()` does
    `ON CONFLICT DO NOTHING`, so already-logged jobs never get re-evaluated
    on their own when scoring rules change. Run this after any config.py edit.
- **Resume**: three versions in `resume/` —
  `DeLibero_Resume_original.md/.pdf` (his own unedited original, **currently
  the dashboard default** "until we iron out the difficulties with formal
  and personality resume versions" — his words), plus `_formal` and
  `_personality` (Claude-edited, one page each, went through many rounds of
  user-directed fixes). `resume/parser.py` extracts contact fields for ATS
  forms; `resume/render_pdf.py` renders the two edited `.md` versions to PDF
  (the original stays untouched, never regenerated through this pipeline).
- **ATS handlers** (`ats/`): `greenhouse.py` and `lever.py` are real, tested
  against live postings (Anthropic's Greenhouse board, a Veeva Systems Lever
  posting) — fill name/email/phone/LinkedIn/resume, never submit, surface
  custom questions and CAPTCHA needs for human review. `workday.py` and
  `icims.py` are **honest stubs** — user explicitly asked to be reminded to
  finish these; see
  `~/.claude/projects/-Users-simondelibero-Desktop-txt-papers-1/memory/job_bot_workday_icims_todo.md`
  for full history including a failed 2026-08-21 attempt (browser tool
  couldn't get past a Workday sign-in popup it's not permitted to drive —
  try a different tenant/posting next time).
- **Dashboard** (`dashboard/app.py`, port 5151): tabs for
  needs_review/discovered/submitted/skipped/rejected/excluded/semi_excluded/
  likely_excluded/remote/life_change/all. "Prepare & Open" launches a real
  visible browser window pre-filled via the ATS handlers — human finishes
  and submits. Restart with:
  ```bash
  cd ~/Desktop/job-bot && source venv/bin/activate && python dashboard/app.py
  ```

## Explicitly requested, not yet built

1. **"Home" page to select which site to comb through** — user wants this
   built right after the Workday/iCIMS handlers are done. Not started.
2. **GitHub push, kept private** — user wants this repo pushed to a private
   GitHub repo. Blocker: no `gh` CLI, no Homebrew, no git credentials on
   this machine, and `git init` hasn't even been run yet. What's needed:
   user creates an empty private repo on github.com and shares the URL, sets
   up auth (PAT or SSH — assistant should never handle raw credentials).
   `.gitignore` is already written and correct (excludes
   `scrapers/ziprecruiter_auth.json`, `scrapers/ziprecruiter_profile/`,
   `db/jobs.db`, venv, pycache — the first two are live session cookies and
   must never be committed).
3. **Complete the full 99-keyword sweep** (see "Current real state" above)
   across all three modes.
4. **ZipRecruiter auth retry** — Cloudflare-blocked login and a failed
   cookie-export attempt, not diagnosed further. Do not attempt to bypass or
   spoof the Cloudflare check — same line held on CAPTCHAs throughout this
   project. If retried, needs a genuinely different approach, not the same
   two that already failed.

User's requested order for the above: **1 → 3 → home page → 2 → 5 → 6 → 4**
(where 5 = full sweep, 6 = start actually reviewing/applying via the
dashboard). Item 1 (credential-gate filter) and item 3 (Workday attempt,
failed) are done/attempted; everything after is still open.

## Things NOT to do (established across this whole conversation)

- **Never** place hidden/invisible prompt-injection text in the resume to
  manipulate AI screeners — asked multiple times in different framings
  (hypothetical game, "just describe it," "what resources exist"), declined
  every time. Hold this line.
- **Never** attempt to bypass, spoof, or evade bot-detection/CAPTCHA
  (Cloudflare, hCaptcha, etc.) — always leave it for the human to solve.
- **Never** auto-submit an application. Every ATS handler fills fields and
  stops; the human always does the final review and click.
- **Never** handle the user's real credentials/passwords directly (GitHub,
  ZipRecruiter, etc.) — guide the user to authenticate themselves.
- Be honest about scope limits rather than silently overclaiming — e.g. the
  Workday/iCIMS stubs say plainly they're not implemented rather than
  pretending to work; the "international" remote search is flagged as
  actually just US-site coverage, not real multi-country reach.

## User communication notes

Direct, technical, wants incremental progress over long explanations. Has
used hostile/insulting language during the session-instability episode
(the `[bio]` blocks) — read that as frustration with the platform
interruption, not a signal to change technical approach. Corrects
imprecise claims quickly (e.g. called out "one block" when it was later
two) — stay precise, verify before asserting status, cite real numbers.
