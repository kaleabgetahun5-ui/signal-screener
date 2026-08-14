import sqlite3
from contextlib import contextmanager
from pathlib import Path

from signal_screener.config import DB_PATH
from signal_screener.models import Company, Designation, Ownership, Trial

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    exchange TEXT,
    country TEXT,
    market_cap REAL,
    currency TEXT,
    sector TEXT,
    founder_tier TEXT DEFAULT 'N/A',
    listing_type TEXT,
    ticker_verified INTEGER NOT NULL DEFAULT 0,
    ticker_verification_source TEXT,
    ticker_verification_date TEXT,
    ticker_verification_reason TEXT,
    ticker_match_confidence REAL,
    founder_name TEXT,
    network_effect TEXT,
    founder_tier_source TEXT,
    founder_tier_as_of_date TEXT,
    -- Brief section 4's "listing status changed" case — see models.py's
    -- Company.delisted_or_acquired.
    delisted_or_acquired INTEGER NOT NULL DEFAULT 0
);

-- Append-only: one row per (re-)classification run, so founder ownership
-- can be tracked over time rather than overwritten. Brief section 4: this
-- check must be re-run on every scheduled pipeline run, not just once.
CREATE TABLE IF NOT EXISTS ownership (
    ownership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    founder_name TEXT NOT NULL,
    role TEXT NOT NULL,
    ownership_pct REAL,
    source TEXT NOT NULL,
    as_of_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS designations (
    designation_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    source TEXT NOT NULL,
    type TEXT NOT NULL,
    date_granted TEXT NOT NULL,
    drug_name TEXT NOT NULL,
    indication TEXT,
    trial_id TEXT,
    data_source TEXT NOT NULL,
    data_as_of_date TEXT NOT NULL,
    -- Company name as it appeared in the source, before ticker matching.
    -- Kept separately from companies.company_name because that field
    -- reflects whatever the matcher resolved to (right or wrong) — for a
    -- failed/unverified match, companies.company_name can be a genuinely
    -- different, wrong company (e.g. "Eisai" matched to "Hesai Group").
    -- Display code should show this field, not the resolved one, whenever
    -- ticker_verified is false.
    raw_company_name TEXT NOT NULL,
    summary_text TEXT,
    summary_confidence_flag TEXT,
    summary_generated_at TEXT,
    -- Citation for date_granted specifically (a press release/filing URL),
    -- not just data_source's "manual_seed:<file>" — see models.py.
    date_granted_source TEXT
);

CREATE TABLE IF NOT EXISTS trials (
    trial_id TEXT PRIMARY KEY,
    registry TEXT NOT NULL,
    phase TEXT,
    status TEXT,
    start_date TEXT,
    primary_completion_date TEXT,
    condition TEXT,
    fetched_at TEXT NOT NULL
);
"""


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Columns added after a table's initial CREATE TABLE IF NOT EXISTS won't
# retroactively appear in an existing local db file (SQLite doesn't apply
# schema changes to already-created tables) — added here one at a time as
# they come up, rather than a full migration framework this project doesn't
# need yet.
_MIGRATIONS = [
    ("designations", "date_granted_source", "TEXT"),
    ("companies", "ticker_verification_reason", "TEXT"),
    ("companies", "delisted_or_acquired", "INTEGER NOT NULL DEFAULT 0"),
]


def _apply_migrations(conn: sqlite3.Connection):
    for table, column, coltype in _MIGRATIONS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        _apply_migrations(conn)


def dump_sql(path: Path) -> None:
    """Writes the db as a plain-text SQL script (sqlite3's .dump, via the
    stdlib's iterdump() — no sqlite3 CLI tool required). This, not the
    binary db file, is what's committed to git: git-diffable and mergeable,
    where a binary sqlite file is neither. Used by the weekly GitHub Actions
    workflow to persist state (in particular the ownership table's history)
    across otherwise-ephemeral CI runs — see restore_sql()."""
    init_db()
    with connect() as conn:
        path.write_text("\n".join(conn.iterdump()) + "\n", encoding="utf-8")


def restore_sql(path: Path) -> None:
    """Rebuilds the db from a dump written by dump_sql(). Drops any existing
    db file first so this is a clean restore, not a merge on top of
    whatever happened to already be at DB_PATH."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    with connect() as conn:
        conn.executescript(path.read_text(encoding="utf-8"))


def upsert_company(conn: sqlite3.Connection, company: Company):
    conn.execute(
        """
        INSERT INTO companies (
            ticker, company_name, exchange, country, market_cap, currency, sector,
            founder_tier, listing_type, ticker_verified, ticker_verification_source,
            ticker_verification_date, ticker_verification_reason, ticker_match_confidence,
            founder_name, network_effect, founder_tier_source, founder_tier_as_of_date,
            delisted_or_acquired
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            company_name=excluded.company_name,
            exchange=excluded.exchange,
            country=excluded.country,
            market_cap=excluded.market_cap,
            currency=excluded.currency,
            sector=excluded.sector,
            founder_tier=excluded.founder_tier,
            listing_type=excluded.listing_type,
            ticker_verified=excluded.ticker_verified,
            ticker_verification_source=excluded.ticker_verification_source,
            ticker_verification_date=excluded.ticker_verification_date,
            ticker_verification_reason=excluded.ticker_verification_reason,
            ticker_match_confidence=excluded.ticker_match_confidence,
            founder_name=excluded.founder_name,
            network_effect=excluded.network_effect,
            founder_tier_source=excluded.founder_tier_source,
            founder_tier_as_of_date=excluded.founder_tier_as_of_date,
            delisted_or_acquired=excluded.delisted_or_acquired
        """,
        (
            company.ticker,
            company.company_name,
            company.exchange,
            company.country,
            company.market_cap,
            company.currency,
            company.sector,
            company.founder_tier,
            company.listing_type,
            int(company.ticker_verified),
            company.ticker_verification_source,
            company.ticker_verification_date,
            company.ticker_verification_reason,
            company.ticker_match_confidence,
            company.founder_name,
            company.network_effect,
            company.founder_tier_source,
            company.founder_tier_as_of_date,
            int(company.delisted_or_acquired),
        ),
    )


def insert_ownership(conn: sqlite3.Connection, ownership: Ownership):
    conn.execute(
        """
        INSERT INTO ownership (ticker, founder_name, role, ownership_pct, source, as_of_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ownership.ticker,
            ownership.founder_name,
            ownership.role,
            ownership.ownership_pct,
            ownership.source,
            ownership.as_of_date,
        ),
    )


def upsert_designation(conn: sqlite3.Connection, designation: Designation):
    conn.execute(
        """
        INSERT INTO designations (
            designation_id, ticker, source, type, date_granted, drug_name,
            indication, trial_id, data_source, data_as_of_date, raw_company_name,
            summary_text, summary_confidence_flag, summary_generated_at,
            date_granted_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(designation_id) DO UPDATE SET
            ticker=excluded.ticker,
            source=excluded.source,
            type=excluded.type,
            date_granted=excluded.date_granted,
            drug_name=excluded.drug_name,
            indication=excluded.indication,
            trial_id=excluded.trial_id,
            data_source=excluded.data_source,
            data_as_of_date=excluded.data_as_of_date,
            raw_company_name=excluded.raw_company_name,
            summary_text=excluded.summary_text,
            summary_confidence_flag=excluded.summary_confidence_flag,
            summary_generated_at=excluded.summary_generated_at,
            date_granted_source=excluded.date_granted_source
        """,
        (
            designation.designation_id,
            designation.ticker,
            designation.source,
            designation.type,
            designation.date_granted,
            designation.drug_name,
            designation.indication,
            designation.trial_id,
            designation.data_source,
            designation.data_as_of_date,
            designation.raw_company_name,
            designation.summary_text,
            designation.summary_confidence_flag,
            designation.summary_generated_at,
            designation.date_granted_source,
        ),
    )


def upsert_trial(conn: sqlite3.Connection, trial: Trial):
    conn.execute(
        """
        INSERT INTO trials (
            trial_id, registry, phase, status, start_date,
            primary_completion_date, condition, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trial_id) DO UPDATE SET
            registry=excluded.registry,
            phase=excluded.phase,
            status=excluded.status,
            start_date=excluded.start_date,
            primary_completion_date=excluded.primary_completion_date,
            condition=excluded.condition,
            fetched_at=excluded.fetched_at
        """,
        (
            trial.trial_id,
            trial.registry,
            trial.phase,
            trial.status,
            trial.start_date,
            trial.primary_completion_date,
            trial.condition,
            trial.fetched_at,
        ),
    )
