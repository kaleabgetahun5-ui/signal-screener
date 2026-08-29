import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from signal_screener.config import DB_PATH
from signal_screener.models import Company, Designation, Ownership, Trial


def now_iso() -> str:
    """UTC timestamp with time-of-day precision, used everywhere a
    diffable timestamp is needed (first_seen_at, site_state.last_generated_at)
    — not date.today()'s date-only granularity, which can't distinguish
    "added this morning" from "site generated this evening, same day.\""""
    return datetime.now(timezone.utc).isoformat()


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
    -- "Established" | "Emerging" | "None identified" — see models.py's
    -- Company.network_effect_strength.
    network_effect_strength TEXT,
    founder_tier_source TEXT,
    founder_tier_as_of_date TEXT,
    -- Brief section 4's "listing status changed" case — see models.py's
    -- Company.delisted_or_acquired.
    delisted_or_acquired INTEGER NOT NULL DEFAULT 0,
    -- Set once, on first insert, by upsert_company() — never touched by a
    -- later update/re-verification. Brief section 8/roadmap step 5's "what's
    -- new since last time" diff (site.py) is entirely driven off this: a row
    -- is "new" iff first_seen_at is after the previous site generation.
    -- NULL for rows that existed before this column was added (migrated,
    -- not backfilled) — deliberately: we don't actually know when those
    -- were first seen, so they must never show up as "new."
    first_seen_at TEXT,
    -- Valuation snapshot (valuation.py) — see models.py's Company for the
    -- "never fabricated, re-fetched fresh every run" contract these share
    -- with market_cap/currency above.
    trailing_pe REAL,
    forward_pe REAL,
    fifty_two_week_low REAL,
    fifty_two_week_high REAL,
    beta REAL,
    dividend_yield_pct REAL,
    valuation_as_of_date TEXT,
    valuation_source TEXT,
    -- IPO backtest (backtest.py) — see models.py's Company for the same
    -- "never fabricated, re-fetched fresh every run" contract; currency
    -- above is reused (a stock only ever trades in one currency).
    ipo_date TEXT,
    ipo_price REAL,
    backtest_current_price REAL,
    sp500_price_at_ipo REAL,
    sp500_current_price REAL,
    backtest_as_of_date TEXT,
    backtest_source TEXT
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
    date_granted_source TEXT,
    -- See companies.first_seen_at above — same semantics.
    first_seen_at TEXT
);

-- Singleton (id is always 1, enforced below) — the timestamp of the most
-- recent generate-site run, read *before* being overwritten so the
-- "new since last visit" section (site.py) has something to diff against.
CREATE TABLE IF NOT EXISTS site_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_generated_at TEXT
);

-- Brief section 2's schema, exactly: note_id, entry_id, date_written,
-- note_text. entry_id is a designation_id or a ticker — the two ID spaces
-- never collide (designation_ids are 16-char lowercase hex hashes, tickers
-- are short uppercase symbols), so one column serves both without an
-- entry_type discriminator, matching the brief's minimal schema as given.
CREATE TABLE IF NOT EXISTS user_notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL,
    date_written TEXT NOT NULL,
    note_text TEXT NOT NULL
);

-- Roadmap step 6 / brief section 2 & 8: "the single most important
-- addition" — the brief's core columns (entry_id, entry_type, date_flagged,
-- flag_given, price_at_flag/3mo/6mo/12mo, notes_on_outcome) plus practical
-- additions the bare schema doesn't cover but the "source + as-of date on
-- everything" guardrail (section 6) requires: ticker (entry_id alone
-- doesn't carry one), price_source, and a real as-of date per checkpoint —
-- price_at_3mo means little without knowing exactly when it was captured,
-- which won't necessarily be exactly 3 months to the day even on a daily
-- check schedule (a due date landing on a weekend/market holiday still
-- gets picked up on the next trading day's check, not backdated).
-- entry_id is UNIQUE: one row per entry, created once at first qualifying
-- flag (see track_record.py) and never overwritten, even if the flag
-- itself changes on a later run — see that module's docstring.
CREATE TABLE IF NOT EXISTS tracked_outcomes (
    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL UNIQUE,
    entry_type TEXT NOT NULL,  -- "designation" | "founder_stock"
    ticker TEXT NOT NULL,
    date_flagged TEXT NOT NULL,
    flag_given TEXT NOT NULL,  -- "High signal" | "Moderate signal"
    price_source TEXT,
    price_at_flag REAL,
    price_at_flag_date TEXT,
    check_3mo_due TEXT NOT NULL,
    price_at_3mo REAL,
    price_at_3mo_date TEXT,
    check_6mo_due TEXT NOT NULL,
    price_at_6mo REAL,
    price_at_6mo_date TEXT,
    check_12mo_due TEXT NOT NULL,
    price_at_12mo REAL,
    price_at_12mo_date TEXT,
    notes_on_outcome TEXT
);

-- Personal watchlist (brief section 8's "your own read is the actual
-- differentiator" philosophy, applied to *which* entries matter to you,
-- not just notes on them — see user_notes above for the latter). Same
-- entry_id addressing scheme as user_notes/tracked_outcomes for a
-- 'pipeline' entry: a designation_id or a ticker already in companies/
-- designations. Added/removed via signal-screener watchlist-add /
-- watchlist-remove (CLI-only, same as add-note — brief section 9: no
-- accounts, no web form).
--
-- entry_kind = 'pipeline' | 'arbitrary'. A 'pipeline' entry_id must
-- already exist in companies/designations — cli.py's watchlist-add
-- rejects (not just warns on, per add-note's looser rule) one that
-- doesn't, since site.py/digest.py's watchlist section renders those
-- straight from those tables and a dangling entry_id would otherwise
-- just silently never appear anywhere.
--
-- An 'arbitrary' entry is a ticker with no row in companies at all — the
-- personal-watchlist equivalent of "I want to track this even though the
-- screener never flagged it." It's still never trusted blindly: cli.py
-- verifies it resolves to a real, currently listed security (matching/
-- ticker_verify.py's resolve_arbitrary_ticker, same Yahoo/SEC sources
-- pipeline tickers are checked against) before it's ever stored, and the
-- verification/company_name columns below exist because these entries
-- have no companies row to pull that display data from. NULL for
-- 'pipeline' entries, which already get it from companies/designations.
CREATE TABLE IF NOT EXISTS watchlist (
    entry_id TEXT PRIMARY KEY,
    added_at TEXT NOT NULL,
    entry_kind TEXT NOT NULL DEFAULT 'pipeline',
    company_name TEXT,
    verification_source TEXT,
    verification_date TEXT,
    verification_reason TEXT
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
    # No DEFAULT on purpose: existing rows become NULL, not "just seen" —
    # see the first_seen_at column comment on companies/designations above.
    ("companies", "first_seen_at", "TEXT"),
    ("designations", "first_seen_at", "TEXT"),
    ("companies", "network_effect_strength", "TEXT"),
    ("watchlist", "entry_kind", "TEXT NOT NULL DEFAULT 'pipeline'"),
    ("watchlist", "company_name", "TEXT"),
    ("watchlist", "verification_source", "TEXT"),
    ("watchlist", "verification_date", "TEXT"),
    ("watchlist", "verification_reason", "TEXT"),
    ("companies", "trailing_pe", "REAL"),
    ("companies", "forward_pe", "REAL"),
    ("companies", "fifty_two_week_low", "REAL"),
    ("companies", "fifty_two_week_high", "REAL"),
    ("companies", "beta", "REAL"),
    ("companies", "dividend_yield_pct", "REAL"),
    ("companies", "valuation_as_of_date", "TEXT"),
    ("companies", "valuation_source", "TEXT"),
    ("companies", "ipo_date", "TEXT"),
    ("companies", "ipo_price", "REAL"),
    ("companies", "backtest_current_price", "REAL"),
    ("companies", "sp500_price_at_ipo", "REAL"),
    ("companies", "sp500_current_price", "REAL"),
    ("companies", "backtest_as_of_date", "TEXT"),
    ("companies", "backtest_source", "TEXT"),
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
    where a binary sqlite file is neither. Used by the daily GitHub Actions
    workflow (.github/workflows/daily.yml) to persist state (in particular
    the ownership table's history) across otherwise-ephemeral CI runs —
    see restore_sql()."""
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
    # first_seen_at is bound below but deliberately absent from ON CONFLICT
    # DO UPDATE SET — that's the entire mechanism for "set once, on first
    # insert, never touched by a later update": on conflict, SQLite applies
    # only the columns listed there, so an existing row's first_seen_at is
    # left exactly as it was.
    conn.execute(
        """
        INSERT INTO companies (
            ticker, company_name, exchange, country, market_cap, currency, sector,
            founder_tier, listing_type, ticker_verified, ticker_verification_source,
            ticker_verification_date, ticker_verification_reason, ticker_match_confidence,
            founder_name, network_effect, network_effect_strength, founder_tier_source,
            founder_tier_as_of_date, delisted_or_acquired, first_seen_at,
            trailing_pe, forward_pe, fifty_two_week_low, fifty_two_week_high, beta,
            dividend_yield_pct, valuation_as_of_date, valuation_source,
            ipo_date, ipo_price, backtest_current_price, sp500_price_at_ipo,
            sp500_current_price, backtest_as_of_date, backtest_source
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
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
            network_effect_strength=excluded.network_effect_strength,
            founder_tier_source=excluded.founder_tier_source,
            founder_tier_as_of_date=excluded.founder_tier_as_of_date,
            delisted_or_acquired=excluded.delisted_or_acquired,
            trailing_pe=excluded.trailing_pe,
            forward_pe=excluded.forward_pe,
            fifty_two_week_low=excluded.fifty_two_week_low,
            fifty_two_week_high=excluded.fifty_two_week_high,
            beta=excluded.beta,
            dividend_yield_pct=excluded.dividend_yield_pct,
            valuation_as_of_date=excluded.valuation_as_of_date,
            valuation_source=excluded.valuation_source,
            ipo_date=excluded.ipo_date,
            ipo_price=excluded.ipo_price,
            backtest_current_price=excluded.backtest_current_price,
            sp500_price_at_ipo=excluded.sp500_price_at_ipo,
            sp500_current_price=excluded.sp500_current_price,
            backtest_as_of_date=excluded.backtest_as_of_date,
            backtest_source=excluded.backtest_source
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
            company.network_effect_strength,
            company.founder_tier_source,
            company.founder_tier_as_of_date,
            int(company.delisted_or_acquired),
            now_iso(),
            company.trailing_pe,
            company.forward_pe,
            company.fifty_two_week_low,
            company.fifty_two_week_high,
            company.beta,
            company.dividend_yield_pct,
            company.valuation_as_of_date,
            company.valuation_source,
            company.ipo_date,
            company.ipo_price,
            company.backtest_current_price,
            company.sp500_price_at_ipo,
            company.sp500_current_price,
            company.backtest_as_of_date,
            company.backtest_source,
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
    # first_seen_at: same "set once, never in ON CONFLICT DO UPDATE SET"
    # mechanism as upsert_company() above.
    conn.execute(
        """
        INSERT INTO designations (
            designation_id, ticker, source, type, date_granted, drug_name,
            indication, trial_id, data_source, data_as_of_date, raw_company_name,
            summary_text, summary_confidence_flag, summary_generated_at,
            date_granted_source, first_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            now_iso(),
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


def get_last_generated_at(conn: sqlite3.Connection) -> str | None:
    """The timestamp of the *previous* generate-site run, read before
    set_last_generated_at() overwrites it — this is what site.py's "new
    since last visit" section diffs first_seen_at against. None means
    generate-site has never run before (nothing to diff against yet)."""
    row = conn.execute("SELECT last_generated_at FROM site_state WHERE id = 1").fetchone()
    return row["last_generated_at"] if row else None


def set_last_generated_at(conn: sqlite3.Connection, timestamp: str) -> None:
    conn.execute(
        """
        INSERT INTO site_state (id, last_generated_at) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET last_generated_at=excluded.last_generated_at
        """,
        (timestamp,),
    )


def insert_user_note(conn: sqlite3.Connection, entry_id: str, note_text: str, date_written: str) -> None:
    conn.execute(
        "INSERT INTO user_notes (entry_id, date_written, note_text) VALUES (?, ?, ?)",
        (entry_id, date_written, note_text),
    )


def get_notes_for_entry(conn: sqlite3.Connection, entry_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM user_notes WHERE entry_id = ? ORDER BY date_written, note_id",
        (entry_id,),
    ).fetchall()


def add_to_watchlist(
    conn: sqlite3.Connection,
    entry_id: str,
    added_at: str,
    *,
    entry_kind: str = "pipeline",
    company_name: str | None = None,
    verification_source: str | None = None,
    verification_date: str | None = None,
    verification_reason: str | None = None,
) -> bool:
    """INSERT OR IGNORE: starring an already-starred entry is a no-op, not
    an error (entry_id is the primary key, so a second add would otherwise
    fail the insert). Returns True iff a row was actually added, so the
    CLI can tell the user whether this was already on their watchlist.

    The company_name/verification_* columns are only ever populated for
    entry_kind="arbitrary" — a 'pipeline' entry already has that data in
    companies/designations, so cli.py never passes them for one."""
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO watchlist (
            entry_id, added_at, entry_kind, company_name,
            verification_source, verification_date, verification_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            added_at,
            entry_kind,
            company_name,
            verification_source,
            verification_date,
            verification_reason,
        ),
    )
    return cur.rowcount > 0


def get_arbitrary_watchlist_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The self-added, never-screened-by-the-pipeline half of the
    watchlist — what site.py/digest.py render as a visually/textually
    distinct group from starred pipeline entries (see watchlist's schema
    comment)."""
    return conn.execute(
        "SELECT * FROM watchlist WHERE entry_kind = 'arbitrary' ORDER BY added_at, entry_id"
    ).fetchall()


def remove_from_watchlist(conn: sqlite3.Connection, entry_id: str) -> bool:
    """Returns True iff a row was actually removed, so the CLI can report
    an honest result rather than a silent no-op for a typo'd entry_id."""
    cur = conn.execute("DELETE FROM watchlist WHERE entry_id = ?", (entry_id,))
    return cur.rowcount > 0


def get_watchlist_entry_ids(conn: sqlite3.Connection) -> set[str]:
    """What site.py/digest.py filter their own already-fetched companies/
    designations rows against — a plain set, not a join, since entry_id
    points into two different tables depending on designation vs. ticker
    (same reason entry_id_exists() below checks both rather than
    joining). Scoped to entry_kind='pipeline': an 'arbitrary' entry has no
    row in companies/designations to match against anyway, and is instead
    rendered from get_arbitrary_watchlist_rows()."""
    return {
        row["entry_id"]
        for row in conn.execute("SELECT entry_id FROM watchlist WHERE entry_kind = 'pipeline'")
    }


def list_watchlist(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM watchlist ORDER BY added_at, entry_id").fetchall()


def entry_id_exists(conn: sqlite3.Connection, entry_id: str) -> bool:
    """Best-effort typo check for the add-note CLI command — entry_id isn't
    a foreign key (it points into two different tables depending on
    designation vs. ticker, see user_notes' schema comment), so nothing
    enforces it at the db level. Used to warn, not to block: a note for an
    entry_id that doesn't exist yet (e.g. added just before the next
    pipeline run) is still saved."""
    if conn.execute(
        "SELECT 1 FROM designations WHERE designation_id = ?", (entry_id,)
    ).fetchone():
        return True
    if conn.execute("SELECT 1 FROM companies WHERE ticker = ?", (entry_id,)).fetchone():
        return True
    return False


def tracked_outcome_exists(conn: sqlite3.Connection, entry_id: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM tracked_outcomes WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        is not None
    )


def insert_tracked_outcome(
    conn: sqlite3.Connection,
    *,
    entry_id: str,
    entry_type: str,
    ticker: str,
    date_flagged: str,
    flag_given: str,
    price_source: str | None,
    price_at_flag: float | None,
    price_at_flag_date: str | None,
    check_3mo_due: str,
    check_6mo_due: str,
    check_12mo_due: str,
    notes_on_outcome: str | None,
) -> None:
    """INSERT OR IGNORE, not upsert: entry_id is UNIQUE and track_record.py
    already checks tracked_outcome_exists() before calling this, but the
    OR IGNORE is defense-in-depth for the same "created once, never
    overwritten" invariant — see this table's schema comment."""
    conn.execute(
        """
        INSERT OR IGNORE INTO tracked_outcomes (
            entry_id, entry_type, ticker, date_flagged, flag_given,
            price_source, price_at_flag, price_at_flag_date,
            check_3mo_due, check_6mo_due, check_12mo_due, notes_on_outcome
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            entry_type,
            ticker,
            date_flagged,
            flag_given,
            price_source,
            price_at_flag,
            price_at_flag_date,
            check_3mo_due,
            check_6mo_due,
            check_12mo_due,
            notes_on_outcome,
        ),
    )


_VALID_CHECKPOINTS = ("3mo", "6mo", "12mo")


def get_due_outcome_checkpoints(
    conn: sqlite3.Connection, checkpoint: str, as_of_date: str
) -> list[sqlite3.Row]:
    """Rows whose checkpoint came due on or before as_of_date and haven't
    been recorded yet — what check_record_outcomes.py's checker acts on."""
    if checkpoint not in _VALID_CHECKPOINTS:
        raise ValueError(f"checkpoint must be one of {_VALID_CHECKPOINTS}, got {checkpoint!r}")
    return conn.execute(
        f"""
        SELECT outcome_id, ticker FROM tracked_outcomes
        WHERE check_{checkpoint}_due <= ? AND price_at_{checkpoint} IS NULL
        """,
        (as_of_date,),
    ).fetchall()


def record_outcome_checkpoint(
    conn: sqlite3.Connection, outcome_id: int, checkpoint: str, price: float, price_date: str
) -> None:
    if checkpoint not in _VALID_CHECKPOINTS:
        raise ValueError(f"checkpoint must be one of {_VALID_CHECKPOINTS}, got {checkpoint!r}")
    conn.execute(
        f"""
        UPDATE tracked_outcomes
        SET price_at_{checkpoint} = ?, price_at_{checkpoint}_date = ?
        WHERE outcome_id = ?
        """,
        (price, price_date, outcome_id),
    )
