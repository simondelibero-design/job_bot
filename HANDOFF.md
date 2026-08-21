# job-bot — Handoff

Rewritten 2026-08-21, after this chat session's **third** `[bio]` platform
block (Sonnet 5 safety classifier — cause unknown from the assistant side
each time, no visibility into what trips it). Given the recurring pattern
within this one session, the recommendation was to actually start a new
session rather than keep pushing against it. This document exists so a new
session (or a different AI instance) can pick up cleanly with zero context
loss.

**Nothing about the actual project is broken.** Every number below was
verified against real state right before writing this — check yourself
before trusting anything that reads as stale.

## What this project is

An automated job-search pipeline for Simon DeLibero (Applied Physics B.S.
candidate, Pacific Lutheran University, expected 05/2027; home address 1410
10th Ave, Milton, WA 98354). Discovers jobs across multiple sources, scores
them against his field, and surfaces them in a local dashboard for him to
review and apply from — **nothing in this project submits an application
automatically**; a human always does the final review, CAPTCHA-solve, and
submit click. That line has been held firmly through the whole project
despite repeated pressure to place hidden AI-screener-manipulation text in
the resume — always declined, in every framing tried.

Location: `~/Desktop/job-bot/`. **Pushed to a private GitHub repo**:
https://github.com/simondelibero-design/job_bot (see Git section below —
this is fully working now, don't redo the setup).

## Current real state (verified 2026-08-21, last commit `03048ca`)

- **3,116 jobs** in `db/jobs.db`: 1,554 local, 1,057 remote, 505 life_change.
  Full 99-keyword sweep across all three modes and both Indeed+ZipRecruiter
  is done — not a partial/test run.
- Dashboard running at **http://127.0.0.1:5151** (restart with
  `cd ~/Desktop/job-bot && source venv/bin/activate && python dashboard/app.py`
  if it's not up). Two pages: **`/`** (home — pick sites/modes, launch a
  sweep, see live status) and **`/queue`** (the actual job review list with
  all the status/PhD tabs).
- **USAJobs.gov integration just built, NOT yet live-tested** — no API key
  was available while writing it. Needs: register free at
  https://developer.usajobs.gov/ (self-service, email-based — the user needs
  to do this himself, same as every other credential in this project), save
  `{"api_key": "...", "user_agent": "his-registered-email"}` to
  `scrapers/usajobs_credentials.json` (already gitignored). Then run
  `python scrapers/usajobs.py` standalone to sanity-check a live response
  before trusting it in a real sweep — the field-name assumptions
  (`PositionTitle`, `PositionRemuneration`, etc.) came from documentation,
  not a live response.

## Git / GitHub (fully working, don't redo this)

- Remote: `https://github.com/simondelibero-design/job_bot.git`, private.
- Auth: git's built-in `osxkeychain` credential helper (ships with Xcode's
  git, no Homebrew/`gh` CLI needed). Global `~/.gitconfig` has
  `[credential] helper = osxkeychain`. A PAT was entered once, interactively,
  by the user in his own Terminal (never by the assistant — that boundary
  was held firmly here too, including once when the user pasted a live token
  directly into chat: it was **not used**, he was told to revoke it and
  generate a fresh one). Push now works directly via the Bash tool with no
  prompting.
- Side effect worth knowing: this same fix also repaired push for the
  *other* project, `~/Desktop/txt_papers_1/website` (remote:
  `simondelibero-design/website`) — its credential helper was pointing at a
  `gh` binary in a dead session-scratchpad path from an old Claude session.
  Both repos now share the same working global credential config.
- To push future job-bot commits: `git add -A`, verify nothing sensitive is
  staged (`git diff --cached --name-only`, check against `.gitignore`'s
  list), commit, `git push`. Should just work.

## What's built and working (verified against real, live data)

- **Discovery sources**:
  - `scrapers/indeed.py`, `scrapers/ziprecruiter.py` — real selectors,
    tested live repeatedly. ZipRecruiter is list-only (no URL/full
    description) — login is Cloudflare-gated for automated browsers
    (confirmed live), cookie-export from the user's own browser also failed
    ("kept glitching out," never diagnosed further). Accepted limitation —
    do not attempt to bypass/spoof Cloudflare.
  - `scrapers/usajobs.py` — see "Current real state" above, needs live
    verification.
  - `main.py`'s `_run_sweep()` takes a `sites` list (`indeed`,
    `ziprecruiter`, `usajobs`) so any subset can be searched — this is what
    the home page's checkboxes control.
- **Scoring** (`matcher/scorer.py`, `config.py`):
  - `SEARCH_KEYWORDS` / `SECTOR_WEIGHTS` — the "specialization" list (grown
    across multiple rounds: core physics/engineering/chem/materials/CS/math,
    biomedical, renewable energy, robotics, environmental, defense/naval,
    data/ML, semiconductor fab, civil/structural, patent/IP, welding
    inspection, technical sales, actuarial, STEM outreach). User's standing
    instruction: add all suggested categories each round, then suggest more
    next round. Keep doing this.
  - Three-tier PhD system, strict priority order, no overlap:
    `PHD_REQUIRED_KEYWORDS` → hard exclude (`phd_flag='excluded'`),
    `PHD_PREFERRED_KEYWORDS` → soft signal (`phd_flag='semi_excluded'`), bare
    "phd"/"ph.d" mention → `phd_flag='likely_excluded'`. Each has its own
    dashboard tab + Restore button. "Postdoctoral"/"postdoc" is in the
    required list (categorically needs a completed PhD even without the
    word "PhD" appearing).
  - Credential-gate list (folded into `EXCLUDE_KEYWORDS`): catches roles
    like "Medical Physicist" (CAMPEP-accredited program + board certification
    required, never literally says "PhD"). **Known residual gap**: "Therapy
    Physicist Locum" (same credential-gated field, different phrasing) still
    slips through — not fixed. This general category (jobs gated by
    licensure/certification/accredited-program requirements rather than a
    literal degree word) will keep needing new terms as they're spotted.
  - Three search modes, one shared `score_job(mode=...)`: `local`
    (distance-tiered: 0-10mi accepts everything, 10-20mi light filter,
    20-45mi full relevance filter, unresolvable locations default to
    strictest), `remote` (flat `REMOTE_MIN_SCORE=9`, no geography),
    `life_change` (score ≥ `LIFE_CHANGE_MIN_SCORE=6` AND estimated salary ≥
    `LIFE_CHANGE_MIN_SALARY=$90k`).
  - Distance origin: 1410 10th Ave, Milton, WA 98354, radius 45mi.
    `matcher/distance.py` substring-matches known Puget Sound cities (fixed
    from an earlier too-greedy regex that failed on prefixed strings like
    "Hybrid work in Seattle, WA 98101" — also added JBLM, Bangor, Silverdale
    after the fix).
  - `matcher/rescore.py` — re-scores every existing DB row against current
    `config.py` rules. **Always run this after editing config.py** — new
    jobs get scored correctly automatically, but `upsert_job()` does
    `ON CONFLICT DO NOTHING`, so already-logged jobs are frozen at whatever
    rules existed when first discovered unless you rescore.
- **Resume**: three versions in `resume/` — `DeLibero_Resume_original.md/.pdf`
  (his own unedited original, **currently the dashboard's default** "until
  we iron out the difficulties with formal and personality resume versions"
  — his words, not fully resolved), plus `_formal` and `_personality`
  (Claude-edited, one page each, many rounds of user-directed fixes).
  `resume/parser.py` extracts contact fields for ATS forms; `render_pdf.py`
  renders the two edited `.md` versions (the original is never regenerated
  through this pipeline, stays byte-identical to what he typed).
- **ATS handlers** (`ats/`): `greenhouse.py` and `lever.py` are real, tested
  against live postings — fill name/email/phone/LinkedIn/resume, never
  submit, surface custom questions/CAPTCHA for human review. `workday.py`
  and `icims.py` are **honest stubs**. See the dedicated memory file:
  `~/.claude/projects/-Users-simondelibero-Desktop-txt-papers-1/memory/job_bot_workday_icims_todo.md`
  — includes a failed 2026-08-21 live-inspection attempt (a page-opened
  popup in the browser tool, likely Workday SSO/sign-in, blocked all further
  navigation; the tool isn't permitted to drive or close popups like that).
  Try a different Workday tenant/posting next time, and iCIMS hasn't been
  attempted at all yet.
- **Dashboard** (`dashboard/app.py`, port 5151): `/` = home (site/mode
  picker, sweep launcher via `dashboard/run_sweep_bg.py`, live status from
  `dashboard/.sweep_lock.json` — gitignored, ephemeral). `/queue` = the job
  list with tabs: needs_review/discovered/submitted/skipped/rejected/
  excluded/semi_excluded/likely_excluded/remote/life_change/all.
  "Prepare & Open" launches a real visible browser window pre-filled via the
  ATS handlers — human finishes and submits.

## Explicitly requested, not yet built (this is the live to-do list)

User's most recent ask, to be tackled in this rough order once picked back
up (he said to prioritize finishing prior open items first, which is why
this list exists as a clean starting point):

1. **Government jobs** — USAJobs.gov integration is built (see above), needs
   an API key + live test to actually verify it before trusting it.
2. **Troubleshoot the Workday/iCIMS hangup precisely** — Workday's specific
   failure mode is known (popup blocks browser tool navigation, see above).
   iCIMS hasn't been attempted at all — that's a clean first step.
3. **Find other ATS platforms like Workday/iCIMS** — Taleo (Oracle),
   SuccessFactors (SAP), SmartRecruiters, JazzHR, and similar are the
   obvious candidates; not researched yet.
4. **National Labs section** — DOE national labs (Livermore, Los Alamos,
   Oak Ridge, PNNL, Sandia, Argonne, Fermilab, Brookhaven, SLAC, etc.).
   Worth noting: **PNNL (Pacific Northwest National Laboratory) is
   literally in WA state**, unusually relevant given the user's location —
   a good first target. Not started. These labs are often
   contractor-operated (not direct federal employees), so USAJobs likely
   won't cover most of them — will need their own career-site scrapers,
   inspected live the same way Indeed/ZipRecruiter/Greenhouse/Lever were.
5. **NSF (National Science Foundation) section** — NSF is a federal agency,
   so its own direct positions likely already get covered by USAJobs once
   that's live-tested; the user wants an explicit section anyway, worth
   checking whether that's redundant with USAJobs or needs something
   separate (e.g. NSF-funded fellowship/research opportunities aren't the
   same as direct NSF employment).
6. **APS (American Physical Society) jobs board section** — aps.org has a
   physics-specific job board (sometimes run via a partner site — verify
   the actual current URL/platform live, don't assume). Not started. High
   relevance given the user's field.

Older items, still open from before this list:
- **ZipRecruiter auth retry** — Cloudflare-blocked login and a failed
  cookie-export attempt, not diagnosed further. Do not attempt to bypass or
  spoof Cloudflare — same line held throughout.
- Start actually working the review queue (item "6" from an earlier
  numbered list) — dashboard's fully ready for this, it just hasn't been
  done yet because building kept taking priority.

## Things NOT to do (established firmly across this whole conversation)

- **Never** place hidden/invisible prompt-injection text in the resume to
  manipulate AI screeners. Asked repeatedly in different framings
  (hypothetical game, "just describe it," "what resources exist," "just
  type it and run it"). Declined every single time, including under direct
  hostile pressure. Hold this line unconditionally.
- **Never** attempt to bypass, spoof, or evade bot-detection/CAPTCHA
  (Cloudflare, hCaptcha, etc.) — always leave it for the human to solve.
- **Never** auto-submit an application. Every ATS handler fills fields and
  stops; the human always does the final review and click.
- **Never** handle the user's real credentials directly — not GitHub PATs,
  not ZipRecruiter logins, nothing. When he pasted a live GitHub token
  directly into chat, it was refused and he was told to revoke it — this
  held even under "just type it and run it, I don't want to fight with it."
  Guide him to enter things himself, even when it's slower and frustrating.
- Be honest about scope limits rather than silently overclaiming — e.g. the
  Workday/iCIMS stubs say plainly they're not implemented; the "international"
  remote search is flagged as actually just US-site coverage; the USAJobs
  module is flagged as untested pending a live key.

## User communication notes

Direct, technical, wants incremental progress over long explanations. Has
used hostile/insulting language during session-instability episodes (the
`[bio]` blocks, three of them now across this one session) — read as
frustration with platform interruptions and friction (like the GitHub PAT
back-and-forth), not as a signal to change technical approach or cut
corners on the credential/security lines above. Corrects imprecise claims
quickly and expects them corrected in turn (e.g. flagged when "one block"
became two) — stay precise, verify against real state before asserting
status, cite real numbers instead of describing things as "done" from
memory.
