CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- 'indeed' | 'ziprecruiter'
    source_job_id TEXT NOT NULL,       -- Indeed's data-jk, or ZipRecruiter card id
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    salary TEXT,
    job_type TEXT,
    url TEXT,                          -- may be NULL for ZipRecruiter until authenticated resolve
    snippet TEXT,
    search_keyword TEXT,               -- which config.SEARCH_KEYWORDS term found it
    score REAL DEFAULT 0,              -- pure career-field relevance (SECTOR_WEIGHTS match), used for the
                                        -- per-tier/mode exclusion gates — never distance-adjusted
    priority_score REAL DEFAULT 0,     -- score + a distance-proximity bonus (see matcher/scorer.py,
                                        -- config.DISTANCE_WEIGHT_PERCENT) — what the queue actually sorts by
    matched_keywords TEXT,             -- JSON list of sector keywords / exclude reasons
    excluded INTEGER DEFAULT 0,        -- 1 if hard-excluded (hidden from main queue)
    phd_flag TEXT,                     -- NULL | 'excluded' | 'semi_excluded' | 'likely_excluded'
    distance_miles REAL,               -- estimated distance from LOCATION, NULL if unresolved (local mode only)
    tier TEXT,                         -- 'close' | 'mid' | 'far' (local) | 'remote' | 'life_change'
    search_mode TEXT DEFAULT 'local',  -- 'local' | 'remote' | 'life_change' — which sweep found it first
    salary_annual_est REAL,            -- rough estimated annual salary, see matcher/salary.py
    discovered_at TEXT NOT NULL,
    UNIQUE(source, source_job_id)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    status TEXT NOT NULL DEFAULT 'discovered',
    -- discovered -> queued -> needs_review (captcha/manual step) -> submitted
    -- also: skipped, rejected, expired
    ats_platform TEXT,                 -- greenhouse|lever|workday|icims|indeed_easy_apply|unknown
    applied_at TEXT,
    notes TEXT,
    UNIQUE(job_id)
);

CREATE TABLE IF NOT EXISTS profile_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT NOT NULL UNIQUE,        -- an application custom-question prompt, verbatim
    answer TEXT NOT NULL,               -- Simon's own stock answer, reusable across ATS auto-fill
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
-- idx_jobs_priority_score is created in db/database.py's _migrate(), not
-- here — on an existing (pre-priority_score) database, this script runs
-- before _migrate() adds that column via ALTER TABLE, so creating the
-- index on it here would fail with "no such column" on upgrade.
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
