import importlib

import pytest

import signal_screener.config as config


def test_schema_init_and_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))
    from signal_screener.models import Company, Designation

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(ticker="TEST", company_name="Test Co", ticker_verified=True),
        )
        db.upsert_designation(
            conn,
            Designation(
                designation_id="abc123",
                ticker="TEST",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2026-01-01",
                drug_name="Test Drug",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2026-01-01",
                raw_company_name="Test Co",
            ),
        )

    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM designations WHERE designation_id = ?", ("abc123",)
        ).fetchone()
        assert row["drug_name"] == "Test Drug"
        assert row["ticker"] == "TEST"


def test_dump_sql_and_restore_sql_roundtrip(tmp_path, monkeypatch):
    """The weekly GitHub Actions workflow persists state across otherwise-
    ephemeral runs by committing this dump, not the binary db file — a
    round trip through it must reproduce the exact same rows."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(ticker="TEST", company_name="Test Co", ticker_verified=True),
        )

    dump_path = tmp_path / "dump.sql"
    db.dump_sql(dump_path)
    assert "INSERT INTO" in dump_path.read_text(encoding="utf-8")

    db.DB_PATH.unlink()
    db.restore_sql(dump_path)

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE ticker = ?", ("TEST",)).fetchone()
        assert row["company_name"] == "Test Co"
        assert bool(row["ticker_verified"]) is True


def test_db_restore_sql_raises_on_missing_dump(tmp_path, monkeypatch):
    """restore_sql() itself doesn't guard a missing file — cli.py's
    db-restore command does that (prints a friendly message and starts
    fresh); calling restore_sql() directly on a missing path should fail
    loudly, not silently produce an empty db."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))

    with pytest.raises(FileNotFoundError):
        db.restore_sql(tmp_path / "does-not-exist.sql")


def test_first_seen_at_set_once_never_touched_by_update(tmp_path, monkeypatch):
    """Roadmap step 5's diff view is entirely driven off this: first_seen_at
    must be stamped on the first insert and then never move, no matter how
    many times the row is re-verified/re-upserted on later pipeline runs."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))
    from signal_screener.models import Company, Designation

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="TEST", company_name="Test Co"))
        db.upsert_designation(
            conn,
            Designation(
                designation_id="abc123",
                ticker="TEST",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2026-01-01",
                drug_name="Test Drug",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2026-01-01",
                raw_company_name="Test Co",
            ),
        )

    with db.connect() as conn:
        first_company_seen = conn.execute(
            "SELECT first_seen_at FROM companies WHERE ticker = 'TEST'"
        ).fetchone()["first_seen_at"]
        first_designation_seen = conn.execute(
            "SELECT first_seen_at FROM designations WHERE designation_id = 'abc123'"
        ).fetchone()["first_seen_at"]
    assert first_company_seen is not None
    assert first_designation_seen is not None

    # Re-upsert both, as a real pipeline run does on every re-verification —
    # everything else can change, first_seen_at must not.
    with db.connect() as conn:
        db.upsert_company(
            conn, Company(ticker="TEST", company_name="Test Co", ticker_verified=True)
        )
        db.upsert_designation(
            conn,
            Designation(
                designation_id="abc123",
                ticker="TEST",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2026-01-01",
                drug_name="Test Drug (updated)",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2026-01-02",
                raw_company_name="Test Co",
            ),
        )

    with db.connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE ticker = 'TEST'").fetchone()
        assert row["ticker_verified"] == 1
        assert row["first_seen_at"] == first_company_seen

        row = conn.execute("SELECT * FROM designations WHERE designation_id = 'abc123'").fetchone()
        assert row["drug_name"] == "Test Drug (updated)"
        assert row["first_seen_at"] == first_designation_seen


def test_site_state_get_set_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))

    db.init_db()
    with db.connect() as conn:
        assert db.get_last_generated_at(conn) is None

        db.set_last_generated_at(conn, "2026-08-13T12:00:00+00:00")

    with db.connect() as conn:
        assert db.get_last_generated_at(conn) == "2026-08-13T12:00:00+00:00"

        # Overwrites in place (singleton row), doesn't accumulate rows.
        db.set_last_generated_at(conn, "2026-08-14T09:30:00+00:00")

    with db.connect() as conn:
        assert db.get_last_generated_at(conn) == "2026-08-14T09:30:00+00:00"
        assert conn.execute("SELECT COUNT(*) AS n FROM site_state").fetchone()["n"] == 1


def test_user_notes_insert_get_and_entry_id_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="TEST", company_name="Test Co"))

        assert db.entry_id_exists(conn, "TEST") is True
        assert db.entry_id_exists(conn, "NOTATICKER") is False

        db.insert_user_note(conn, "TEST", "First note.", "2026-08-13")
        db.insert_user_note(conn, "TEST", "Second note.", "2026-08-14")

    with db.connect() as conn:
        notes = db.get_notes_for_entry(conn, "TEST")
        assert [n["note_text"] for n in notes] == ["First note.", "Second note."]
        assert db.get_notes_for_entry(conn, "NOTATICKER") == []


def test_watchlist_add_remove_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))

    db.init_db()
    with db.connect() as conn:
        assert db.get_watchlist_entry_ids(conn) == set()
        assert db.list_watchlist(conn) == []

        added = db.add_to_watchlist(conn, "TEST", "2026-08-27")
        assert added is True
        assert db.get_watchlist_entry_ids(conn) == {"TEST"}

        # Starring an already-starred entry is a no-op, not an error.
        added_again = db.add_to_watchlist(conn, "TEST", "2026-08-28")
        assert added_again is False

        db.add_to_watchlist(conn, "abc123", "2026-08-27")

    with db.connect() as conn:
        rows = db.list_watchlist(conn)
        assert [r["entry_id"] for r in rows] == ["TEST", "abc123"]

        removed = db.remove_from_watchlist(conn, "TEST")
        assert removed is True
        assert db.get_watchlist_entry_ids(conn) == {"abc123"}

        # Removing something not on the watchlist is reported, not silent.
        removed_again = db.remove_from_watchlist(conn, "TEST")
        assert removed_again is False


def test_watchlist_arbitrary_entries_stored_and_scoped_separately(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))

    db.init_db()
    with db.connect() as conn:
        db.add_to_watchlist(conn, "TEST", "2026-08-27")  # pipeline, default kind
        db.add_to_watchlist(
            conn,
            "AAPL",
            "2026-08-27",
            entry_kind="arbitrary",
            company_name="Apple Inc.",
            verification_source="yahoo_finance_search",
            verification_date="2026-08-27",
            verification_reason="resolved 'aapl' to 'AAPL' ('Apple Inc.')",
        )

    with db.connect() as conn:
        # Pipeline-only set used to filter companies/designations rows —
        # the arbitrary entry has no row there and must not appear here.
        assert db.get_watchlist_entry_ids(conn) == {"TEST"}

        arbitrary_rows = db.get_arbitrary_watchlist_rows(conn)
        assert len(arbitrary_rows) == 1
        assert arbitrary_rows[0]["entry_id"] == "AAPL"
        assert arbitrary_rows[0]["company_name"] == "Apple Inc."
        assert arbitrary_rows[0]["verification_source"] == "yahoo_finance_search"

        all_rows = db.list_watchlist(conn)
        kinds = {r["entry_id"]: r["entry_kind"] for r in all_rows}
        assert kinds == {"TEST": "pipeline", "AAPL": "arbitrary"}
