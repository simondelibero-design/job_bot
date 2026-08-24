# job-bot — Handoff

Originally rewritten 2026-08-21 after a prior chat session hit three `[bio]`
platform blocks and recommended starting fresh. A follow-up session on
2026-08-24 picked this up cleanly and made real progress — see "Session 2"
below for what changed. This document exists so any session (or a
different AI instance) can pick up cleanly with zero context loss.

**Nothing about the actual project is broken.** Every number below was
verified against real state right before writing this — check yourself
before trusting anything that reads as stale.

## Session 2 (2026-08-24): ATS platform research resolved, PNNL added

Picked up item 2 and item 3 from the to-do list below. Live-inspected six
ATS platforms against real, current job postings (not documentation) to
settle exactly which ones are automatable:

- **Workday** — confirmed, definitively: every path through "Start Your
  Application" (Autofill with Resume, Apply Manually, *and* Use My Last
  Application — checked all three) leads to a mandatory "Create
  Account/Sign In" step before any application field appears. This is
  Workday's own shared account UI (`data-automation-id="createAccountSubmitButton"`),
  not a tenant customization, so it's universal. `ats/workday.py` now
  detects this gate live (clicks Apply → Apply Manually, checks for the
  account-creation selectors) and hands off honestly instead of guessing.
- **iCIMS** — confirmed against a live General Dynamics Mission Systems
  posting. Content loads inside a same-origin iframe; the first step is an
  email-capture gate (`#email`) that's also hCaptcha-protected on this
  tenant. `ats/icims.py` now finds the iframe, pre-fills the email (safe —
  just typing text), and flags the GDPR checkbox + hCaptcha for the human
  rather than touching either.
- **JazzHR** (`*.applytojob.com`) — **fully automatable, real handler
  built** (`ats/jazzhr.py`). No account gate. Verified against a live
  Labelmaster/American Labelmark posting: standard `resumator-*`-prefixed
  field IDs (name/email/phone/address/resume) are platform-wide, not
  per-tenant. Custom questions, EEOC voluntary self-ID, and the "Human
  Check" reCAPTCHA (which only blocks final submit, which this project
  never does anyway) are surfaced for human review.
- **SmartRecruiters** (`jobs.smartrecruiters.com` "Easy Apply") — form
  structure verified against a live Intuitive posting (no account gate,
  standard fields, shadow-DOM rendering that Playwright's selector engine
  pierces fine). **But** driving the actual navigation through Playwright
  — both headless and headed — got blocked by SmartRecruiters' own bot
  detection ("Access is temporarily restricted... Automated (bot)
  activity") before the form ever loaded, the same category of wall as
  ZipRecruiter's Cloudflare block. `ats/smartrecruiters.py` fills the known
  fields *if* it reaches them, but checks for this block first and reports
  it honestly rather than silently returning an empty review list (an
  actual bug caught and fixed this session — an empty list would have made
  `ats/apply.py`'s orchestrator claim "Auto-filled, ready to review" even
  though nothing was touched). Whether it works at all in practice is
  unverified — every attempt this session got walled before reaching the
  form.
- **Taleo** (`*.taleo.net`) — confirmed blocked the same way as Workday:
  "Apply Online" leads straight to a Login/New User page before anything
  else, verified against a live Herman Miller/PMG posting. `ats/taleo.py`
  detects this and hands off.
- **SuccessFactors** (`*.successfactors.com`) — confirmed blocked the same
  way, verified live ("Career Opportunities: Sign In" / "Create an account
  to apply"). `ats/successfactors.py` detects this and hands off.

Same session also picked up item 4 (National Labs) and added PNNL as a
real discovery source — see that item under "Explicitly requested, not yet
built" below for the details (it has its own real public JSON API, no
scraping needed).

All six ATS platforms are wired into `ats/detect.py` (`PLATFORM_PATTERNS`) and
`ats/apply.py` (`HANDLERS`) — 8 platforms total now recognized, up from 4.
Every handler still follows the unbroken project rule: fill what's safely
fillable, never touch consent checkboxes or CAPTCHAs, never create
accounts, never submit.

**Smoke-tested after the fact, through the project's real Playwright
pipeline** (not just the browser tool used for initial inspection):
`jazzhr.py` genuinely fills real fields on a live posting — confirmed
working. `smartrecruiters.py` hit SmartRecruiters' own bot detection on
every attempt (headless and headed), which is what led to fixing the
empty-review-list bug noted above — its field-filling code is unverified
in practice pending a way past that wall (which, per the CAPTCHA/Cloudflare
rule, isn't something to force). `workday.py`/`icims.py`/`taleo.py`/
`successfactors.py` weren't re-run through the pipeline since they just
detect a gate and stop — the browser-tool verification of the gate itself
is the substance of what they do. Still worth a real dashboard "Prepare &
Open" click against a live queued job at some point, but the core logic
has been exercised.

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

## Current real state (verified 2026-08-24, commit `4ff4689`)

- **3,141 jobs** in `db/jobs.db`: 1,554 local, 1,082 remote, 505 life_change.
  The 1,057→1,082 remote bump is real PNNL postings from smoke-testing the
  new `scrapers/pnnl.py` end-to-end (2-keyword test, not a full sweep) —
  everything else is the original full 99-keyword Indeed+ZipRecruiter sweep
  from 2026-08-21, not a partial/test run.
- Dashboard running at **http://127.0.0.1:5151** (restart with
  `cd ~/Desktop/job-bot && source venv/bin/activate && python dashboard/app.py`
  if it's not up). Two pages: **`/`** (home — pick sites/modes, launch a
  sweep, see live status) and **`/queue`** (the actual job review list with
  all the status/PhD tabs).
- **USAJobs.gov integration built, still NOT live-tested** — no API key has
  been saved yet. `scrapers/save_usajobs_key.py` exists (untracked helper,
  found sitting in the repo 2026-08-24 — unclear which session added it)
  that prompts for the key interactively and writes
  `scrapers/usajobs_credentials.json` (gitignored) locally, never sending
  it anywhere else. User needs to: register free at
  https://developer.usajobs.gov/ (self-service, email-based), then run
  `python scrapers/save_usajobs_key.py` himself — same credential boundary
  as everywhere else in this project. Then run `python scrapers/usajobs.py`
  standalone to sanity-check a live response before trusting it in a real
  sweep — the field-name assumptions (`PositionTitle`,
  `PositionRemuneration`, etc.) still come from documentation, not a live
  response.

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
  - `scrapers/pnnl.py` — **real, live-tested, working** (2026-08-24). Public
    JSON API (`careers.pnnl.gov/api/jobs`), no browser automation. Ignores
    `location`/`radius_miles` (single-employer board, not a general
    search) — accepts them only for interface parity with the other
    `search_*` functions.
  - `main.py`'s `_run_sweep()` takes a `sites` list (`indeed`,
    `ziprecruiter`, `usajobs`, `pnnl`) so any subset can be searched — this
    is what the home page's checkboxes control.
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
- **ATS handlers** (`ats/`), 8 platforms recognized in `ats/detect.py` /
  `ats/apply.py`:
  - **Real, fillable handlers** (verified live end-to-end through the actual
    Playwright pipeline, no account/CAPTCHA gate blocks reaching the form):
    `greenhouse.py`, `lever.py`, `jazzhr.py` (`*.applytojob.com`). Each
    fills name/email/phone/resume/etc., never submits, surfaces custom
    questions/CAPTCHA/voluntary self-ID for human review.
  - **Field structure known, but bot-detection blocks automated access to
    it**: `smartrecruiters.py` (`jobs.smartrecruiters.com` Easy Apply) —
    the form itself has no account gate and is genuinely fillable when
    reached by a human, but SmartRecruiters' own bot detection walled off
    every Playwright-driven attempt (headless and headed) before the form
    loaded. Same category as ZipRecruiter's Cloudflare block — not
    something to bypass. The handler is defensive (detects the block,
    reports it honestly) but hasn't actually filled a real form yet.
  - **Honest gate-detectors** (account creation is structurally required
    before any application field appears, confirmed live, not guessed):
    `workday.py`, `icims.py` (email step also hCaptcha-gated on the tenant
    tested), `taleo.py`, `successfactors.py`. These detect the gate and
    hand off rather than attempting fields they can't reach — see
    "Session 2" above for what was actually tested and why.
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
2. ~~**Troubleshoot the Workday/iCIMS hangup precisely**~~ — **Done, Session
   2.** Both confirmed to have structural account/CAPTCHA gates, not tool
   glitches. See "Session 2" above.
3. ~~**Find other ATS platforms like Workday/iCIMS**~~ — **Done, Session 2.**
   JazzHR turned out fully automatable (real handler, smoke-tested
   end-to-end through Playwright — works). SmartRecruiters looked the same
   at first but its own bot detection blocks automated access to the form;
   handler is defensive but unverified in practice. Taleo and
   SuccessFactors are gated the same way as Workday (account creation
   required). See "Session 2" above.
4. **National Labs section** — DOE national labs (Livermore, Los Alamos,
   Oak Ridge, PNNL, Sandia, Argonne, Fermilab, Brookhaven, SLAC, etc.).
   **PNNL done, same Session 2**: `scrapers/pnnl.py` built and
   live-tested end-to-end through `main.py`'s real `_run_sweep()` — found,
   scored, and logged 25 real jobs to the DB on a two-keyword test. Turned
   out PNNL has a genuine public JSON API behind careers.pnnl.gov
   (`/api/jobs`, found via live network inspection, not documentation) —
   no browser automation needed, same tier as USAJobs.gov. Every posting's
   `apply_url` points to `careers-pnnl.icims.com`, so `ats/icims.py`
   already covers the application side once these reach that stage. Wired
   into `main.py` (`VALID_SITES`, `_run_sweep`) and the dashboard home page
   (`dashboard/app.py`'s `VALID_SITES` — the template renders checkboxes
   dynamically, so no template edit was needed).
   The other labs (Livermore, Los Alamos, Oak Ridge, Sandia, Argonne,
   Fermilab, Brookhaven, SLAC) are still untouched — worth checking each
   for a similar JSON API before assuming HTML scraping is needed; several
   are also contractor-operated the same way PNNL is (Battelle), so
   USAJobs.gov likely won't cover them either.
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
