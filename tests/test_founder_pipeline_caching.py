"""Integration tests for founder_pipeline.py's extraction caching:
extract_founder_status() should only be called again when the company
name + filing/board-page excerpt Claude actually sees has changed since
the stored classification — not unconditionally on every run. Mirrors
tests/test_pipeline.py's biotech-side twin."""

import importlib
from unittest.mock import patch

import signal_screener.config as config


def _reload(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    importlib.reload(importlib.import_module("signal_screener.db"))
    return importlib.reload(importlib.import_module("signal_screener.founder_pipeline"))


def _run_with_mocks(
    founder_pipeline,
    excerpt_text,
    *,
    extraction_call_count,
    transition_date=None,
    founder_tier="Founder-CEO",
):
    from signal_screener.filings.sec_edgar import FilingRef
    from signal_screener.matching.ticker_match import TickerMatch
    from signal_screener.matching.ticker_verify import VerificationResult
    from signal_screener.sources.founder_led_tier1 import FounderLedCandidate
    from signal_screener.summarize.founder_extraction import FounderExtraction

    fake_candidate = FounderLedCandidate("Test Co", "Jane Founder", "Testland")

    match = TickerMatch(ticker="TEST", matched_company_name="Test Co", confidence=100.0)
    verification = VerificationResult(
        verified=True,
        source="yahoo_finance_search",
        checked_date="2026-08-29",
        reason="symbol and company name confirmed (score=100)",
    )
    filing = FilingRef(
        company_name="Test Co",
        form="20-F",
        filing_date="2026-04-01",
        accession_number="0001-26-000001",
        document_url="https://www.sec.gov/fake-filing.htm",
        exchange="NYSE",
        sector="Technology",
    )

    def fake_extract(**kwargs):
        extraction_call_count["n"] += 1
        return FounderExtraction(
            leadership_status="Jane Founder is Chief Executive Officer",
            ownership_stake="10%",
            ownership_pct_numeric=10.0,
            founder_tier=founder_tier,
            transition_date=transition_date,
            network_effect="A network effect exists.",
            network_effect_strength="Established",
            generated_at="2026-08-29T00:00:00+00:00",
        )

    with patch.object(founder_pipeline, "TIER1_CANDIDATES", [fake_candidate]), patch.object(
        founder_pipeline, "TIER2_CANDIDATES", []
    ), patch.object(
        founder_pipeline, "resolve_ticker", return_value=(match, verification)
    ), patch.object(
        founder_pipeline, "get_latest_annual_filing", return_value=filing
    ), patch.object(
        founder_pipeline, "fetch_filing_text", return_value="raw filing text"
    ), patch.object(
        founder_pipeline, "extract_leadership_excerpt", return_value=excerpt_text
    ), patch.object(
        founder_pipeline, "extract_founder_status", side_effect=fake_extract
    ), patch.object(
        founder_pipeline.valuation, "get_session_and_crumb", return_value=None
    ), patch.object(
        founder_pipeline.backtest, "get_current_price", return_value=None
    ):
        return founder_pipeline.run()


def test_run_reuses_extraction_when_excerpt_unchanged(tmp_path, monkeypatch):
    founder_pipeline = _reload(tmp_path, monkeypatch)
    call_count = {"n": 0}

    result_1 = _run_with_mocks(founder_pipeline, "Jane Founder, CEO since founding.", extraction_call_count=call_count)
    assert call_count["n"] == 1
    assert result_1.extractions_reused == 0

    result_2 = _run_with_mocks(founder_pipeline, "Jane Founder, CEO since founding.", extraction_call_count=call_count)
    assert call_count["n"] == 1  # not called again
    assert result_2.extractions_reused == 1

    db = importlib.import_module("signal_screener.db")
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE ticker = 'TEST'").fetchone()
        assert row["founder_tier"] == "Founder-CEO"
        assert row["network_effect_strength"] == "Established"

        # Cache hit must not duplicate the ownership history row.
        ownership_rows = conn.execute("SELECT * FROM ownership WHERE ticker = 'TEST'").fetchall()
        assert len(ownership_rows) == 1


def test_run_regenerates_extraction_when_excerpt_changes(tmp_path, monkeypatch):
    founder_pipeline = _reload(tmp_path, monkeypatch)
    call_count = {"n": 0}

    _run_with_mocks(founder_pipeline, "Jane Founder, CEO since founding.", extraction_call_count=call_count)
    assert call_count["n"] == 1

    result_2 = _run_with_mocks(
        founder_pipeline,
        "Jane Founder stepped back to Chairman in 2026.",
        extraction_call_count=call_count,
    )
    assert call_count["n"] == 2  # regenerated — excerpt text changed
    assert result_2.extractions_reused == 0


def test_recency_rule_still_reapplies_on_a_cache_hit(tmp_path, monkeypatch):
    """A Founder-Chair whose transition_date is now more than 24 months
    ago must still get downgraded to Founder-departed on a cache-hit run
    — the recency check is a function of elapsed time, not of whether the
    excerpt changed, so it must never be skipped just because the Claude
    call was."""
    founder_pipeline = _reload(tmp_path, monkeypatch)
    call_count = {"n": 0}

    # First run: Claude says Founder-Chair, transitioned long ago.
    _run_with_mocks(
        founder_pipeline,
        "Jane Founder stepped back to Chairman.",
        extraction_call_count=call_count,
        transition_date="2020-01-01",
        founder_tier="Founder-Chair",
    )
    db = importlib.import_module("signal_screener.db")
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE ticker = 'TEST'").fetchone()
        assert row["founder_tier"] == "Founder-departed"  # already stale > 24mo at first run

    # Second run, same excerpt (cache hit) — must remain Founder-departed,
    # not silently revert to the raw Founder-Chair Claude originally said.
    result_2 = _run_with_mocks(
        founder_pipeline,
        "Jane Founder stepped back to Chairman.",
        extraction_call_count=call_count,
        transition_date="2020-01-01",
        founder_tier="Founder-Chair",
    )
    assert call_count["n"] == 1  # still not re-called
    assert result_2.extractions_reused == 1
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE ticker = 'TEST'").fetchone()
        assert row["founder_tier"] == "Founder-departed"


def test_no_ticker_match_still_writes_a_flagged_unverified_placeholder(tmp_path, monkeypatch):
    """The brief's "never silently drop an entry" guardrail (same rule
    pipeline.py's biotech side follows): a Tier 1 candidate whose ticker
    can't be resolved at all still gets a placeholder_ticker() row written
    to `companies`, flagged unverified — site.py's founder card renderer
    already has a distinct "ticker unverified" style for this, the same
    as the biotech side. This is NOT the bug (see the two tests below for
    the real one: a stale placeholder never getting cleaned up once a
    later run's match succeeds)."""
    founder_pipeline = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.matching.ticker_match import placeholder_ticker
    from signal_screener.sources.founder_led_tier1 import FounderLedCandidate

    fake_candidate = FounderLedCandidate("Sea Limited", "Forrest Li", "Singapore")

    with patch.object(
        founder_pipeline, "TIER1_CANDIDATES", [fake_candidate]
    ), patch.object(founder_pipeline, "TIER2_CANDIDATES", []), patch.object(
        founder_pipeline, "resolve_ticker", return_value=(None, None)
    ):
        result = founder_pipeline.run()

    assert result.unverified_tickers == 1
    db.init_db()
    with db.connect() as conn:
        row = db.get_company(conn, placeholder_ticker("Sea Limited"))
    assert row is not None
    assert row["founder_tier"] == "N/A"
    assert bool(row["ticker_verified"]) is False


def test_stale_placeholder_removed_once_company_name_resolves_on_a_later_run(tmp_path, monkeypatch):
    """Regression test for the real bug found live: "UNVERIFIED::SEA-
    LIMITED" (written when Sea Limited's match failed entirely on an
    earlier run) sat in `companies` right alongside SE, Sea Ltd's real,
    correctly-matched row from a later run that resolved it properly —
    companies.ticker is the primary key, so the placeholder and the real
    row are two separate rows for the same company_name, never merged.
    Once a run's match succeeds, the leftover placeholder must be deleted."""
    founder_pipeline = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.matching.ticker_match import TickerMatch, placeholder_ticker
    from signal_screener.matching.ticker_verify import VerificationResult
    from signal_screener.sources.founder_led_tier1 import FounderLedCandidate

    fake_candidate = FounderLedCandidate("Sea Limited", "Forrest Li", "Singapore")

    # First run: total match failure — placeholder written.
    with patch.object(
        founder_pipeline, "TIER1_CANDIDATES", [fake_candidate]
    ), patch.object(founder_pipeline, "TIER2_CANDIDATES", []), patch.object(
        founder_pipeline, "resolve_ticker", return_value=(None, None)
    ):
        founder_pipeline.run()

    db.init_db()
    with db.connect() as conn:
        assert db.get_company(conn, placeholder_ticker("Sea Limited")) is not None

    # Second run: the same company_name now resolves to a real ticker.
    match = TickerMatch(ticker="SE", matched_company_name="Sea Ltd", confidence=100.0)
    verification = VerificationResult(
        verified=True,
        source="yahoo_finance_search",
        checked_date="2026-09-24",
        reason="symbol and company name confirmed (score=100)",
    )
    with patch.object(
        founder_pipeline, "TIER1_CANDIDATES", [fake_candidate]
    ), patch.object(founder_pipeline, "TIER2_CANDIDATES", []), patch.object(
        founder_pipeline, "resolve_ticker", return_value=(match, verification)
    ), patch.object(
        founder_pipeline, "get_latest_annual_filing", return_value=None
    ):
        founder_pipeline.run()

    with db.connect() as conn:
        assert db.get_company(conn, placeholder_ticker("Sea Limited")) is None
        real_row = db.get_company(conn, "SE")
    assert real_row is not None
    assert real_row["ticker_verified"]


def test_tier2_stale_placeholder_removed_once_company_name_resolves(tmp_path, monkeypatch):
    founder_pipeline = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")
    from signal_screener.matching.ticker_match import TickerMatch, placeholder_ticker
    from signal_screener.matching.ticker_verify import VerificationResult
    from signal_screener.sources.founder_led_tier2 import Tier2Candidate

    fake_candidate = Tier2Candidate("Some Co", "Nobody", "Nowhere", "XYZ", "DE")

    with patch.object(founder_pipeline, "TIER1_CANDIDATES", []), patch.object(
        founder_pipeline, "TIER2_CANDIDATES", [fake_candidate]
    ), patch.object(founder_pipeline, "_resolve_tier2_ticker", return_value=(None, None)):
        founder_pipeline.run()

    db.init_db()
    with db.connect() as conn:
        assert db.get_company(conn, placeholder_ticker("Some Co")) is not None

    match = TickerMatch(ticker="SOME", matched_company_name="Some Co", confidence=100.0)
    verification = VerificationResult(
        verified=True,
        source="yahoo_finance_search",
        checked_date="2026-09-24",
        reason="symbol and company name confirmed (score=100)",
    )
    with patch.object(founder_pipeline, "TIER1_CANDIDATES", []), patch.object(
        founder_pipeline, "TIER2_CANDIDATES", [fake_candidate]
    ), patch.object(
        founder_pipeline, "_resolve_tier2_ticker", return_value=(match, verification)
    ), patch.object(founder_pipeline, "get_latest_annual_filing", return_value=None):
        founder_pipeline.run()

    with db.connect() as conn:
        assert db.get_company(conn, placeholder_ticker("Some Co")) is None
        real_row = db.get_company(conn, "SOME")
    assert real_row is not None


def test_excerpt_fetch_failure_preserves_prior_real_classification(tmp_path, monkeypatch):
    """End-to-end regression test for the Naver bug: a company that was
    correctly classified on a prior run must keep that classification —
    not get wiped to founder_tier='N/A' — when a later run's excerpt
    fetch fails, while its verification fields still update fresh."""
    founder_pipeline = _reload(tmp_path, monkeypatch)
    db = importlib.import_module("signal_screener.db")

    # First run: succeeds fully, establishes a real classification.
    _run_with_mocks(
        founder_pipeline,
        "Jane Founder stepped back to Chairman.",
        extraction_call_count={"n": 0},
        transition_date="2020-01-01",
        founder_tier="Founder-Chair",
    )
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE ticker = 'TEST'").fetchone()
        assert row["founder_tier"] == "Founder-departed"  # recency rule already downgraded it
        prior_fingerprint = row["founder_extraction_fingerprint"]
        assert prior_fingerprint

    # Second run: the excerpt fetch itself fails outright this time.
    from signal_screener.filings.sec_edgar import FilingRef
    from signal_screener.matching.ticker_match import TickerMatch
    from signal_screener.matching.ticker_verify import VerificationResult
    from signal_screener.sources.founder_led_tier1 import FounderLedCandidate

    fake_candidate = FounderLedCandidate("Test Co", "Jane Founder", "Testland")
    match = TickerMatch(ticker="TEST", matched_company_name="Test Co", confidence=100.0)
    verification = VerificationResult(
        verified=True,
        source="yahoo_finance_search",
        checked_date="2026-09-24",
        reason="symbol and company name confirmed (score=100)",
    )
    filing = FilingRef(
        company_name="Test Co",
        form="20-F",
        filing_date="2026-09-24",
        accession_number="0001-26-000002",
        document_url="https://www.sec.gov/fake-filing-2.htm",
        exchange="NYSE",
        sector="Technology",
    )

    with patch.object(founder_pipeline, "TIER1_CANDIDATES", [fake_candidate]), patch.object(
        founder_pipeline, "TIER2_CANDIDATES", []
    ), patch.object(
        founder_pipeline, "resolve_ticker", return_value=(match, verification)
    ), patch.object(
        founder_pipeline, "get_latest_annual_filing", return_value=filing
    ), patch.object(
        founder_pipeline, "fetch_filing_text", side_effect=RuntimeError("SEC fetch failed")
    ), patch.object(
        founder_pipeline.valuation, "get_session_and_crumb", return_value=None
    ), patch.object(founder_pipeline.backtest, "get_current_price", return_value=None):
        result_2 = founder_pipeline.run()

    assert result_2.filing_lookup_failures == 1
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE ticker = 'TEST'").fetchone()
        # Classification preserved, not wiped to N/A.
        assert row["founder_tier"] == "Founder-departed"
        assert row["founder_extraction_fingerprint"] == prior_fingerprint
        # Verification fields reflect today's real, successful check.
        assert row["ticker_verification_date"] == "2026-09-24"
