-- Additive migration: no writes to objekte, kalkulation or rating.
CREATE TABLE IF NOT EXISTS qa_schema(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS qa_sync(adapter TEXT PRIMARY KEY, cursor TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS qa_messages(
 id INTEGER PRIMARY KEY, adapter TEXT NOT NULL, message_id TEXT NOT NULL,
 received_at TEXT NOT NULL, sender TEXT, subject TEXT, is_test INTEGER NOT NULL,
 UNIQUE(adapter,message_id));
CREATE TABLE IF NOT EXISTS qa_listings(
 id INTEGER PRIMARY KEY, portal TEXT NOT NULL, portal_id TEXT NOT NULL,
 canonical_url TEXT NOT NULL UNIQUE, UNIQUE(portal,portal_id));
CREATE TABLE IF NOT EXISTS qa_urls(url TEXT PRIMARY KEY, listing_id INTEGER NOT NULL REFERENCES qa_listings(id));
CREATE TABLE IF NOT EXISTS qa_observations(
 id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL REFERENCES qa_messages(id),
 listing_id INTEGER NOT NULL REFERENCES qa_listings(id), evidence_json TEXT NOT NULL,
 profile_json TEXT, UNIQUE(message_id,listing_id));
CREATE TABLE IF NOT EXISTS qa_analyses(
 id TEXT PRIMARY KEY, listing_id INTEGER NOT NULL REFERENCES qa_listings(id),
 observation_id INTEGER NOT NULL REFERENCES qa_observations(id), revision INTEGER NOT NULL,
 fingerprint TEXT NOT NULL, result_json TEXT NOT NULL, analyzed_at TEXT NOT NULL,
 analysis_status TEXT NOT NULL, pdf_status TEXT NOT NULL DEFAULT 'ausstehend',
 delivery_status TEXT NOT NULL DEFAULT 'nicht_verbunden', pdf_name TEXT, delivery_receipt TEXT,
 UNIQUE(listing_id,revision));
CREATE TABLE IF NOT EXISTS qa_jobs(
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('analysis','pdf','send')),
 target TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'ready', attempts INTEGER NOT NULL DEFAULT 0,
 next_run REAL NOT NULL DEFAULT 0, lease_until REAL, lease_token TEXT, error TEXT,
 result_id TEXT REFERENCES qa_analyses(id), UNIQUE(kind,target));
CREATE INDEX IF NOT EXISTS qa_jobs_due ON qa_jobs(state,next_run,lease_until);
CREATE TABLE IF NOT EXISTS qa_runtime(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
