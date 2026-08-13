import importlib

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
