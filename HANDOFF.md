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

## Current real state (verified 2026-08-24, commit `6daa6ac`)

- **3,264 jobs** in `db/jobs.db`: 1,554 local, 1,205 remote, 505 life_change.
  The 1,057→1,205 remote bump is real postings from smoke-testing each new
  national-lab/APS scraper end-to-end (1-2 keyword tests each, not full
  sweeps) — everything else is the original full 99-keyword Indeed+
  ZipRecruiter sweep from 2026-08-21, not a partial/test run. A real full
  sweep with all sources enabled hasn't been run yet — worth doing to get
  proper multi-keyword coverage from all the new sources rather than just
  the 1-2 keywords each got smoke-tested with.
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
  - `scrapers/pnnl.py`, `scrapers/anl.py`, `scrapers/fnal.py`,
    `scrapers/bnl.py`, `scrapers/llnl.py`, `scrapers/lanl.py`,
    `scrapers/slac.py`, `scrapers/ornl.py`, `scrapers/snl.py`,
    `scrapers/aps.py` — **all real, live-tested, working** (2026-08-24,
    see "Session 2" above for what each one found and why). All but one
    are plain public JSON-API or unauthenticated-HTML scrapers, no
    Playwright/browser automation needed; `scrapers/snl.py` (Sandia) is
    the one exception — its ATS has neither an API nor scrapeable static
    HTML, so it's a genuine Playwright scraper, same tier as `indeed.py`.
    No bot-detection fought or bypassed anywhere across any of these. All
    ignore `location`/`radius_miles` (each is a single employer's postings
    or a non-geographic board) — accepted only for interface parity with
    the other `search_*` functions.
  - `main.py`'s `_run_sweep()` takes a `sites` list (`indeed`,
    `ziprecruiter`, `usajobs`, `pnnl`, `anl`, `fnal`, `aps`, `llnl`,
    `lanl`, `bnl`, `slac`, `ornl`, `snl`) so any subset can be searched —
    this is what the home page's checkboxes control.
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
- **ATS handlers** (`ats/`), 13 platforms recognized in `ats/detect.py` /
  `ats/apply.py` (up from 8 — the 5 new ones cover the national-lab/APS
  discovery sources added earlier this session, "in-fill" work done at the
  user's request, Session 2 continued):
  - **Real, fillable handlers** (verified live end-to-end through the actual
    Playwright pipeline, no account/CAPTCHA gate blocks reaching the form):
    `greenhouse.py`, `lever.py`, `jazzhr.py` (`*.applytojob.com`),
    `aps.py` (apsphysicsjobs.com — first/last/email/resume fill directly
    into an in-page form, no redirect out to the employer's own site; the
    required "covering message" field is left for the human, same
    reasoning as not answering custom questions generically). Each fills
    name/email/phone/resume/etc., never submits, surfaces custom
    questions/CAPTCHA/voluntary self-ID for human review.
  - **Partial-fill handlers** (a real gate exists, but the one safe field
    in front of it — email — gets pre-filled): `icims.py` (email step also
    hCaptcha-gated on the tenant tested), `slac.py`
    (careersearch.stanford.edu — a lighter "Let's get started" email +
    required-T&C-checkbox gate than Workday's, live inside its own iframe;
    the checkbox and a hidden honeypot field are both deliberately left
    untouched — the honeypot exists specifically to catch bots that fill
    every field they find).
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
    `workday.py`, `taleo.py`, `successfactors.py`, `ornl.py` (a
    SuccessFactors-style sign-in gate, but on a hostname —
    career-hcm20.ns2cloud.com — `ats/detect.py`'s `successfactors` pattern
    doesn't match, hence its own module), `snl.py` (Sandia — *two*
    compounding blockers: no stable per-posting URL exists at all in its
    PeopleSoft Fluid ATS, on top of the same account-creation wall).
  - **Bot-wall gate-detector** (not an account-creation gate, a request
    that gets rejected outright): `lanl.py` — every LANL posting's "Apply"
    link routes to a completely different system (jobsp1.lanl.gov, Oracle
    iRecruitment) than the one `scrapers/lanl.py` discovers postings from,
    and that system returns "Request Rejected" to a plain navigation — an
    F5-style bot wall, confirmed live, not fought or spoofed.
  - See "Session 2" above for what was actually tested and why on the
    original 8; the 5 new ones follow the identical live-verify-first
    methodology.
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
4. ~~**National Labs section**~~ — **All 9 done, Session 2 (2026-08-24),
   parallelized across 5 background agents + this session.** DOE national
   labs are contractor-operated, so USAJobs.gov doesn't cover them; each
   needed its own source, same process as Indeed/ZipRecruiter/Greenhouse/
   Lever before. All of the below are wired into `main.py` (`VALID_SITES`,
   `_run_sweep`) and `dashboard/app.py`'s `VALID_SITES` (checkboxes render
   dynamically from that list — no template edits needed), and each was
   independently re-verified and live-tested through `main.py`'s real
   `_run_sweep()` (not just standalone) before being committed:
   - **PNNL** (`scrapers/pnnl.py`) — public JSON API at careers.pnnl.gov
     (`/api/jobs`). Apply URLs route through `careers-pnnl.icims.com`, so
     `ats/icims.py` already covers the application side.
   - **Argonne/ANL** (`scrapers/anl.py`) and **Fermilab/FNAL**
     (`scrapers/fnal.py`) — both run on Workday. **Notable, broadly
     reusable finding**: Workday's *application* flow requires account
     creation (`ats/workday.py`), but Workday's job-*search* API (the
     "CXS" endpoint, `/wday/cxs/<tenant>/<site>/jobs`) is public and needs
     no login at all — it's what Workday's own search UI calls
     client-side. This likely applies to any Workday-hosted employer, not
     just these two labs.
   - **Brookhaven/BNL** (`scrapers/bnl.py`) — a third Workday tenant, same
     CXS-API pattern (this one 400s above `limit=20`, so it paginates).
   - **Livermore/LLNL** (`scrapers/llnl.py`) — public SmartRecruiters
     postings API (`api.smartrecruiters.com`), no auth for search even
     though `ats/smartrecruiters.py` found the *apply* flow blocked by
     SmartRecruiters' own bot detection — a similar split to Workday's.
   - **Los Alamos/LANL** (`scrapers/lanl.py`) — has two separate career
     surfaces. `jobs.lanl.gov` (Oracle iRecruitment) is genuinely
     bot-walled (an F5 JS challenge, no content without executing it) and
     is skipped entirely, same "don't fight it" call as ZipRecruiter's
     Cloudflare block. A separate, modern front end at `lanl.jobs` has no
     such wall and its own public JSON API — that's what's scraped.
   - **SLAC** (`scrapers/slac.py`) — unlike the other contractor-run labs,
     SLAC is operated directly by Stanford, so it runs on Oracle Fusion
     Cloud Recruiting via Stanford's own infrastructure
     (careersearch.stanford.edu) — a structurally different, but still
     public/unauthenticated, REST API.
   - **Oak Ridge/ORNL** (`scrapers/ornl.py`) — runs SAP SuccessFactors
     "Jobs2Web," which server-renders full HTML with no JS execution
     needed — a plain `requests` + regex scraper, no API but no wall
     either.
   - **Sandia/SNL** (`scrapers/snl.py`) — the one lab with no usable API
     *and* no clean static HTML: it's Oracle PeopleSoft Fluid HCM
     "Candidate Gateway," whose search returns a proprietary `text/xml`
     partial-page-update protocol, not REST/JSON, with content filled in
     by client-side JS after a stateful POST handshake. But there's no
     bot-detection wall, so this is a genuine Playwright scraper (like
     `indeed.py`) that drives the real search box and clicks through each
     result's detail view via the built-in "Next Job" button — the only
     one of the 8 labs needing a browser rather than a plain HTTP request.
     Documented, honest limitation: PeopleSoft Fluid exposes no stable
     per-posting URL at all (confirmed live — a guessed direct-link scheme
     returns "not authorized"), so every result's `url` points at the
     general search app rather than a specific posting; a human re-searches
     by Job ID there.
   - Only Sandia publishes structured salary data (via its detail page's
     "Salary Range" section, when the posting includes one) — every other
     lab honestly reports `salary: None` rather than regex-guessing a
     number out of free-text descriptions.
5. ~~**NSF section**~~ — **Done, Session 2.** Researched and correctly
   concluded no scraper is warranted: NSF-funded opportunities (distinct
   from direct NSF employment, which USAJobs already covers) are posted
   individually by each university/PI with no NSF-run aggregator worth
   scraping — verified live against nsf.gov's actual funding/postdoc pages
   rather than assumed. Don't revisit this without new information.
6. ~~**APS jobs board section**~~ — **Done, Session 2.** Real job board at
   apsphysicsjobs.com (careers.aps.org redirects there), run on the Madgex
   platform — verified live, not assumed. No JSON API, but plain
   server-rendered HTML with no bot-detection, so `scrapers/aps.py` does a
   plain `requests` GET + parse. Live-tested through `_run_sweep()`, wired
   in. Notably international in scope (CERN, etc.) — a first for this
   project, everything else is US-only. Known limitation: no working
   pagination was found (several common param names tried, all no-ops),
   so only the first ~10 results per keyword are returned — still useful
   signal given APS/Physics World Jobs is a low-volume board.

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
