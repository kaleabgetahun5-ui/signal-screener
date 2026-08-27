import importlib

import signal_screener.config as config


def test_build_digest_runs_against_empty_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "empty.db")
    importlib.reload(importlib.import_module("signal_screener.db"))
    digest = importlib.reload(importlib.import_module("signal_screener.digest"))

    result = digest.build_digest()
    assert "Weekly Digest" in result.subject
    assert "No biotech designations on file yet." in result.body
    assert "No founder-led companies on file yet." in result.body
    assert "not investment advice" in result.body
    assert "Your watchlist is empty" in result.body


def test_watchlist_section_shows_only_starred_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))
    digest = importlib.reload(importlib.import_module("signal_screener.digest"))
    from signal_screener.models import Company, Designation

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="TEST", company_name="Test Co", ticker_verified=True))
        db.upsert_designation(
            conn,
            Designation(
                designation_id="abc123",
                ticker="TEST",
                source="FDA",
                type="Breakthrough Therapy",
                date_granted="2026-01-01",
                drug_name="Starred Drug",
                indication="Test indication",
                trial_id=None,
                data_source="unit_test",
                data_as_of_date="2026-01-01",
                raw_company_name="Test Co",
            ),
        )
        db.upsert_company(
            conn,
            Company(
                ticker="OTHR",
                company_name="Other Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
            ),
        )
        db.add_to_watchlist(conn, "abc123", "2026-08-27")

    result = digest.build_digest()
    watchlist_section, _, rest = result.body.partition("BIOTECH SIGNALS")
    assert "Starred Drug" in watchlist_section
    assert "Other Co" not in watchlist_section
    # Both still appear in their own full sections further down.
    assert "Starred Drug" in rest
    assert "Other Co" in rest


def test_watchlist_section_separates_arbitrary_ticker_from_screened_entries(
    tmp_path, monkeypatch
):
    """A self-added ticker must appear under its own clearly-labeled
    subsection, tagged [SELF-ADDED — NOT SCREENED] rather than the
    [Founder-CEO]/[High signal]-style tag a screened entry gets, and
    never inside the main BIOTECH SIGNALS/FOUNDER-LED COMPANIES sections
    (it has no row there — it was never screened)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    db = importlib.reload(importlib.import_module("signal_screener.db"))
    digest = importlib.reload(importlib.import_module("signal_screener.digest"))
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(
            conn,
            Company(
                ticker="OTHR",
                company_name="Screened Co",
                ticker_verified=True,
                listing_type="ADR",
                founder_tier="Founder-CEO",
            ),
        )
        db.add_to_watchlist(conn, "OTHR", "2026-08-27")
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

    result = digest.build_digest()
    assert "SELF-ADDED — NOT SCREENED" in result.body
    assert "not screened by this pipeline" in result.body

    watchlist_section, _, rest = result.body.partition("BIOTECH SIGNALS")
    assert "Apple Inc." in watchlist_section
    assert "Apple Inc." not in rest


def test_send_digest_raises_without_config(monkeypatch):
    import signal_screener.digest as digest

    monkeypatch.setattr(digest, "SMTP_USERNAME", None)
    monkeypatch.setattr(digest, "SMTP_PASSWORD", None)
    monkeypatch.setattr(digest, "DIGEST_TO_EMAIL", None)

    try:
        digest.send_digest(digest.Digest(subject="x", body="y"))
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "SMTP_USERNAME" in str(e)
