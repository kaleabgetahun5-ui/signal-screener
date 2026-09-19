"""Integration tests for founder_discovery_pipeline.py: run() (discovery
only, never touches `companies`) and promote_approved() (only ever acts on
rows already marked 'approved'). All external calls mocked — no live
network, no live Claude calls. Mirrors tests/test_founder_pipeline_caching.py's
mocking style."""

import importlib
from unittest.mock import patch

import signal_screener.config as config


def _reload(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    importlib.reload(importlib.import_module("signal_screener.db"))
    importlib.reload(importlib.import_module("signal_screener.founder_pipeline"))
    return importlib.reload(importlib.import_module("signal_screener.founder_discovery_pipeline"))


def _fake_constituents():
    from signal_screener.sources.sp500_universe import SP500Constituent

    return [
        SP500Constituent(ticker="FOUNDCO", company_name="Founder Co", sector="Technology", headquarters="Nowhere, USA", cik="0000000001"),
        SP500Constituent(ticker="NOFOUND", company_name="No Founder Co", sector="Industrials", headquarters="Somewhere, USA", cik="0000000002"),
        SP500Constituent(ticker="NOFILING", company_name="No Filing Co", sector="Industrials", headquarters="Elsewhere, USA", cik="0000000003"),
        SP500Constituent(ticker="UNVERIFIED", company_name="Unverified Co", sector="Industrials", headquarters="Anywhere, USA", cik="0000000004"),
    ]


def _fake_filing(ticker, company_name):
    from signal_screener.filings.sec_edgar import FilingRef

    return FilingRef(
        company_name=company_name,
        form="DEF 14A",
        filing_date="2026-04-01",
        accession_number="0001-26-000001",
        document_url=f"https://www.sec.gov/fake-{ticker}.htm",
        exchange="NASDAQ",
        sector="Technology",
    )


def test_run_discovers_only_the_company_with_a_qualifying_founder(tmp_path, monkeypatch):
    fdp = _reload(tmp_path, monkeypatch)
    from signal_screener.matching.ticker_verify import VerificationResult
    from signal_screener.summarize.founder_discovery_extraction import FounderDetection

    def fake_verify(ticker, name):
        verified = ticker != "UNVERIFIED"
        return VerificationResult(
            verified=verified,
            source="yahoo_finance_search",
            checked_date="2026-09-15",
            reason="ok" if verified else "no listing found",
        )

    def fake_get_filing(ticker):
        if ticker == "NOFILING":
            return None
        return _fake_filing(ticker, {"FOUNDCO": "Founder Co", "NOFOUND": "No Founder Co"}[ticker])

    def fake_extract_mentions(text, max_chars=6000):
        return "Jane Founder is our founder and CEO." if "FOUNDCO" in text else None

    def fake_detect(*, company_name, report_excerpt):
        if company_name == "Founder Co":
            return FounderDetection(
                founder_detected=True,
                founder_name="Jane Founder",
                current_title="Chief Executive Officer",
                ownership_pct_numeric=12.5,
                ownership_stake="12.5%",
                supporting_quote="Jane Founder is our founder and CEO.",
                reasoning="Excerpt names Jane Founder as founder and CEO.",
                generated_at="2026-09-15T00:00:00+00:00",
            )
        return FounderDetection(
            founder_detected=False,
            founder_name=None,
            current_title=None,
            ownership_pct_numeric=None,
            ownership_stake="not disclosed in this excerpt",
            supporting_quote=None,
            reasoning="no qualifying founder",
            generated_at="2026-09-15T00:00:00+00:00",
        )

    with patch.object(
        fdp, "fetch_sp500_constituents", return_value=_fake_constituents()
    ), patch.object(fdp, "verify_ticker", side_effect=fake_verify), patch.object(
        fdp, "get_latest_annual_filing", side_effect=fake_get_filing
    ), patch.object(
        fdp, "fetch_filing_text", side_effect=lambda url: f"filler text {url.split('fake-')[1]}"
    ), patch.object(
        fdp, "extract_founder_mention_excerpts", side_effect=fake_extract_mentions
    ), patch.object(fdp, "detect_founder_leadership", side_effect=fake_detect):
        summary = fdp.run()

    assert summary.newly_discovered == ["FOUNDCO"]
    assert summary.ticker_unverified == 1
    assert summary.no_filing == 1
    # NOFOUND: verified, has a filing, but its filing text never triggers the
    # founder-mention prefilter in this test's fake_extract_mentions.
    assert summary.no_founder_mention == 1

    db = importlib.import_module("signal_screener.db")
    with db.connect() as conn:
        row = db.get_founder_candidate(conn, "FOUNDCO")
        assert row is not None
        assert row["status"] == "pending"
        assert row["founder_name"] == "Jane Founder"
        assert row["ownership_pct"] == 12.5

        # Discovery must never write to companies — that's the entire point
        # of the approval gate.
        assert conn.execute("SELECT COUNT(*) c FROM companies").fetchone()["c"] == 0


def test_run_skips_tickers_already_known(tmp_path, monkeypatch):
    """A ticker already in companies (e.g. one of the existing 9) or already
    a founder_candidates row from a prior run must never be re-processed —
    keeps re-runs incremental and keeps discovery from ever touching an
    existing screened company."""
    fdp = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.models import Company

    db.init_db()
    with db.connect() as conn:
        db.upsert_company(conn, Company(ticker="FOUNDCO", company_name="Founder Co", ticker_verified=True))

    with patch.object(
        fdp, "fetch_sp500_constituents", return_value=_fake_constituents()
    ), patch.object(fdp, "verify_ticker") as mock_verify:
        summary = fdp.run(limit=0)

    # limit=0 alone would already stop new processing, but the key
    # assertion is that FOUNDCO (already a real company) is counted as
    # already_known rather than ever reaching verify_ticker.
    mock_verify.assert_not_called()
    assert summary.already_known >= 1


def test_promote_approved_only_touches_approved_rows(tmp_path, monkeypatch):
    fdp = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.matching.ticker_verify import VerificationResult
    from signal_screener.summarize.founder_extraction import FounderExtraction

    db.init_db()
    with db.connect() as conn:
        db.insert_founder_candidate(
            conn,
            _candidate("APPROVED", status="pending"),
        )
        db.set_founder_candidate_status(conn, "APPROVED", "approved", "2026-09-16")
        db.insert_founder_candidate(conn, _candidate("PENDING", status="pending"))
        db.insert_founder_candidate(conn, _candidate("REJECTED", status="pending"))
        db.set_founder_candidate_status(conn, "REJECTED", "rejected", "2026-09-16")

    verification = VerificationResult(
        verified=True, source="yahoo_finance_search", checked_date="2026-09-16", reason="ok"
    )
    filing = _fake_filing("APPROVED", "Discovered Co")
    extraction = FounderExtraction(
        leadership_status="Jane Founder is Chief Executive Officer",
        ownership_stake="12.5%",
        ownership_pct_numeric=12.5,
        founder_tier="Founder-CEO",
        transition_date=None,
        network_effect="An established network effect.",
        network_effect_strength="Established",
        generated_at="2026-09-16T00:00:00+00:00",
    )

    with patch.object(fdp, "verify_ticker", return_value=verification), patch.object(
        fdp, "get_latest_annual_filing", return_value=filing
    ), patch.object(fdp, "fetch_filing_text", return_value="raw filing text"), patch.object(
        fdp, "extract_leadership_excerpt", return_value="Jane Founder, CEO, owns 12.5%."
    ), patch.object(fdp, "extract_founder_status", return_value=extraction), patch.object(
        fdp.valuation, "get_session_and_crumb", return_value=None
    ), patch.object(fdp.backtest, "get_current_price", return_value=None):
        summary = fdp.promote_approved()

    assert summary.promoted == ["APPROVED"]

    with db.connect() as conn:
        # Only the approved candidate becomes a real company.
        company_tickers = {r["ticker"] for r in conn.execute("SELECT ticker FROM companies")}
        assert company_tickers == {"APPROVED"}

        promoted_row = db.get_founder_candidate(conn, "APPROVED")
        assert promoted_row["status"] == "promoted"

        pending_row = db.get_founder_candidate(conn, "PENDING")
        assert pending_row["status"] == "pending"

        rejected_row = db.get_founder_candidate(conn, "REJECTED")
        assert rejected_row["status"] == "rejected"

        company_row = conn.execute("SELECT * FROM companies WHERE ticker = 'APPROVED'").fetchone()
        assert company_row["founder_tier"] == "Founder-CEO"
        assert company_row["listing_type"] == "primary"
        assert company_row["network_effect_strength"] == "Established"


def _candidate(ticker, *, status="pending"):
    from signal_screener.models import FounderCandidate

    return FounderCandidate(
        ticker=ticker,
        company_name="Discovered Co",
        founder_name="Jane Founder",
        current_title="Chief Executive Officer",
        ownership_pct=12.5,
        ownership_stake_text="12.5%",
        source_citation="DEF 14A:https://www.sec.gov/fake.htm",
        source_excerpt="Jane Founder is our founder and CEO, owning 12.5%.",
        discovered_at="2026-09-15",
        country="Nowhere, USA",
        exchange="NASDAQ",
        sector="Technology",
        status=status,
    )
