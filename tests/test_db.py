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
