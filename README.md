# job-bot

Personal job-search automation for Simon: discovers listings on Indeed and
ZipRecruiter near Tacoma, WA, scores them against target sectors, and logs
everything to a local database. Applying is **not** wired up yet — this
phase only does discovery + scoring + logging.

## Setup

```bash
cd ~/Desktop/job-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run a discovery pass

```bash
source venv/bin/activate
python main.py
```

This searches every keyword in [config.py](config.py) on both sites, scores
each result, and stores it in `db/jobs.db` (SQLite, created on first run).
Re-running is safe — already-seen listings (`source` + `source_job_id`) are
skipped, not duplicated.

To check what's logged without re-scraping:

```bash
python -c "from db.database import top_jobs; [print(j['score'], j['title'], j['company']) for j in top_jobs(20)]"
```

## What's built so far

- **`config.py`** — search keywords, Tacoma/30mi location, sector scoring
  weights. Edit this to change what gets prioritized.
- **`scrapers/indeed.py`** — scrapes public Indeed search results (title,
  company, location, salary, job type, description snippet). No login
  required for this.
- **`scrapers/ziprecruiter.py`** — scrapes the ZipRecruiter results *list*
  only (title, company, location, salary). ZipRecruiter puts an
  account-creation wall in front of full job descriptions and apply links —
  see the caveat below.
- **`matcher/scorer.py`** — keyword-weighted scoring against
  `SECTOR_WEIGHTS`, with an exclude-list safety valve.
- **`db/`** — SQLite schema (`jobs`, `applications` tables) and helpers.
- **`main.py`** — orchestrates the above into one discovery run.

## ZipRecruiter login caveat

ZipRecruiter shows the results list without an account, but clicking into a
job (needed for the real URL, full description, and applying) triggers a
signup wall. This tool won't create that account or handle your password —
you need to:

1. Log into ZipRecruiter yourself in a normal browser.
2. Export the session so Playwright can reuse it (one-time):
   ```python
   from playwright.sync_api import sync_playwright
   with sync_playwright() as p:
       browser = p.chromium.launch(headless=False)
       page = browser.new_page()
       page.goto("https://www.ziprecruiter.com/login")
       input("Log in in the opened browser window, then press Enter here...")
       page.context.storage_state(path="ziprecruiter_auth.json")
       browser.close()
   ```
3. Point `main.py`'s `ZIPRECRUITER_STORAGE_STATE` at that file's path.

Until that's done, ZipRecruiter listings will have `url = None` and empty
descriptions/snippets in the log — they still get scored on title alone.

## What's built now (resume + ATS layer)

- **`resume/parser.py`** — parses `DeLibero_Resume_*.md` into the fields ATS
  forms need (name, email, phone, LinkedIn, categorized skills).
- **`ats/detect.py`** — identifies Greenhouse / Lever / Workday / iCIMS from
  a job URL.
- **`ats/greenhouse.py`**, **`ats/lever.py`** — fill the standard fields
  (name, email, phone, LinkedIn, resume upload) on real live postings,
  verified against actual Anthropic (Greenhouse) and Veeva (Lever) forms.
  Never submit. Anything they can't answer generically — per-posting custom
  questions, EEO dropdowns, hCaptcha — gets collected into `needs_review`
  and written to `applications.notes` instead of guessed at.
- **`ats/workday.py`**, **`ats/icims.py`** — stubs only. These platforms are
  heavily per-tenant customized (multi-step wizards, sometimes account
  creation required), so there's no generic form to fill the way Greenhouse/
  Lever have one — needs real target postings inspected live before writing
  handlers, same process used for the others.
- **`ats/apply.py`** — orchestrator: detects platform, runs the right
  handler, always leaves `applications.status = 'needs_review'`. Nothing in
  this project auto-submits.

## Not built yet

- **Dashboard** (`dashboard/`) — local web UI to review queued applications,
  see what each one still needs, approve/skip, and solve CAPTCHAs inline.
  Right now the `needs_review` queue only lives in the database.
- **Workday / iCIMS handlers** — see above, needs real postings to build against.
- **Scheduling** — periodic discovery runs instead of manual `python main.py`.

## Known fragility

Both sites' selectors were captured from live markup on 2026-08-18 and *will*
drift as the sites redesign — if a run suddenly returns 0 results, that's
the first thing to check (re-inspect the page, update the CSS selectors in
`scrapers/`). Also worth adding: request throttling is minimal right now
(a few seconds between searches); if you start seeing blocked/empty
responses, slow it down further before assuming the selectors broke.
