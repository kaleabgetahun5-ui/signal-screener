import sqlite3
from contextlib import contextmanager

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
    ticker_match_confidence REAL,
    founder_name TEXT,
    network_effect TEXT,
    founder_tier_source TEXT,
    founder_tier_as_of_date TEXT
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
    summary_generated_at TEXT
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


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_company(conn: sqlite3.Connection, company: Company):
    conn.execute(
        """
        INSERT INTO companies (
            ticker, company_name, exchange, country, market_cap, currency, sector,
            founder_tier, listing_type, ticker_verified, ticker_verification_source,
            ticker_verification_date, ticker_match_confidence, founder_name,
            network_effect, founder_tier_source, founder_tier_as_of_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ticker_match_confidence=excluded.ticker_match_confidence,
            founder_name=excluded.founder_name,
            network_effect=excluded.network_effect,
            founder_tier_source=excluded.founder_tier_source,
            founder_tier_as_of_date=excluded.founder_tier_as_of_date
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
            company.ticker_match_confidence,
            company.founder_name,
            company.network_effect,
            company.founder_tier_source,
            company.founder_tier_as_of_date,
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
            summary_text, summary_confidence_flag, summary_generated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            summary_generated_at=excluded.summary_generated_at
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
