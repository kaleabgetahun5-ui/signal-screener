from unittest.mock import patch

from signal_screener.backtest import BacktestResult
from signal_screener.founder_pipeline import (
    _apply_recency_rule,
    _effective_transition_date,
    _fetch_backtest_for,
    _fetch_valuation_for,
    _preserve_existing_classification,
    _resolve_tier2_ticker,
)
from signal_screener.matching.ticker_match import TickerMatch
from signal_screener.matching.ticker_verify import VerificationResult
from signal_screener.models import Company
from signal_screener.sources.founder_led_tier2 import Tier2Candidate
from signal_screener.valuation import ValuationMetrics


def _failure_company(**overrides):
    fields = dict(
        ticker="035420.KS",
        company_name="NAVER CORP",
        country="South Korea",
        founder_tier="N/A",
        listing_type="primary",
        ticker_verified=True,
        ticker_verification_source="yahoo_finance_search",
        ticker_verification_date="2026-09-21",
        ticker_verification_reason="symbol and company name confirmed",
        ticker_match_confidence=100.0,
        founder_name="Lee Hae-jin",
        exchange="KOSPI",
    )
    fields.update(overrides)
    return Company(**fields)


def test_preserve_existing_classification_returns_failure_company_when_never_classified():
    """No prior real classification to preserve — a company that's never
    been successfully classified still needs to show up as such."""
    result = _preserve_existing_classification(None, _failure_company())
    assert result.founder_tier == "N/A"

    never_classified_row = {"founder_tier": "N/A"}
    result = _preserve_existing_classification(never_classified_row, _failure_company())
    assert result.founder_tier == "N/A"


def test_preserve_existing_classification_keeps_prior_real_tier_on_failure():
    """Regression test for the real bug found live: Naver stuck at
    founder_tier 'N/A' for weeks because every caught excerpt-fetch/
    extraction failure overwrote its last real classification
    (Founder-departed, from real DART data) with the N/A placeholder —
    every single day it failed, permanently, even after the underlying
    transient cause had long passed."""
    existing_row = {
        "founder_tier": "Founder-departed",
        "network_effect": "Naver operates an established network effect...",
        "network_effect_strength": "Established",
        "founder_tier_source": "KR:DART exctvSttus corp_code=00266961",
        "founder_tier_as_of_date": "2026-08-29",
        "founder_extraction_fingerprint": "6ac786675c96c16c21cf9d798adf62d67f941dd3",
        "founder_transition_date": "2015-12-31",
    }
    failure = _failure_company(
        ticker_verification_date="2026-09-22",  # today's real, successful verification
    )
    result = _preserve_existing_classification(existing_row, failure)

    assert result.founder_tier == "Founder-departed"
    assert result.network_effect_strength == "Established"
    assert result.founder_tier_source == "KR:DART exctvSttus corp_code=00266961"
    assert result.founder_extraction_fingerprint == "6ac786675c96c16c21cf9d798adf62d67f941dd3"
    assert result.founder_transition_date == "2015-12-31"
    # Verification fields reflect today's real check, not the stale ones.
    assert result.ticker_verification_date == "2026-09-22"
    assert result.ticker_verified is True


def test_recent_transition_keeps_founder_chair():
    tier, reason = _apply_recency_rule("Founder-Chair", "2026-01-01")
    assert tier == "Founder-Chair"
    assert reason is None


def test_stale_transition_downgrades_to_departed():
    tier, reason = _apply_recency_rule("Founder-Chair", "2020-01-01")
    assert tier == "Founder-departed"
    assert reason is not None


def test_missing_transition_date_leaves_tier_unchanged():
    tier, reason = _apply_recency_rule("Founder-Chair", None)
    assert tier == "Founder-Chair"
    assert reason is None


def test_non_chair_tier_is_never_touched():
    tier, reason = _apply_recency_rule("Founder-CEO", "2015-01-01")
    assert tier == "Founder-CEO"
    assert reason is None


_DE_CANDIDATE = Tier2Candidate("Zalando", "Robert Gentz", "Germany", "XETRA", "DE")
_KR_CANDIDATE = Tier2Candidate(
    "Naver", "Lee Hae-jin", "South Korea", "KOSPI", "KR", founder_name_local="이해진"
)


def test_effective_transition_date_passes_through_for_non_korea_countries():
    """Only Korea has a direct historical-lookback check (filings/korea.py)
    — every other country's extraction is used as-is."""
    with patch("signal_screener.founder_pipeline.korea") as mock_korea:
        result = _effective_transition_date(_DE_CANDIDATE, "2026-01-01")
    assert result == "2026-01-01"
    mock_korea.check_role_predates_recency_window.assert_not_called()


def test_effective_transition_date_uses_dart_anchor_when_claude_found_nothing():
    """The reported case: Claude's excerpt-only extraction correctly
    returns transition_date=None (no "stepped back on X" sentence exists
    in a single current-period DART filing) — the DART historical check
    must supply a real anchor instead of leaving the recency rule with
    nothing to act on."""
    with patch("signal_screener.founder_pipeline.korea") as mock_korea:
        mock_korea.check_role_predates_recency_window.return_value = "2015-12-31"
        result = _effective_transition_date(_KR_CANDIDATE, None)
    assert result == "2015-12-31"


def test_effective_transition_date_prefers_older_of_the_two_dates():
    with patch("signal_screener.founder_pipeline.korea") as mock_korea:
        mock_korea.check_role_predates_recency_window.return_value = "2015-12-31"
        result = _effective_transition_date(_KR_CANDIDATE, "2026-01-01")
    assert result == "2015-12-31"


def test_effective_transition_date_keeps_claude_date_when_dart_has_no_anchor():
    with patch("signal_screener.founder_pipeline.korea") as mock_korea:
        mock_korea.check_role_predates_recency_window.return_value = None
        result = _effective_transition_date(_KR_CANDIDATE, "2026-01-01")
    assert result == "2026-01-01"


_HK_CANDIDATE = Tier2Candidate(
    "Tencent Holdings", "Ma Huateng (Pony Ma)", "Hong Kong", "HKEX", "HK", known_ticker="0700.HK"
)


def test_resolve_tier2_ticker_uses_known_ticker_when_it_verifies():
    """The Tencent case: OpenFIGI's top-ranked candidate (a thinly-traded
    US OTC ticker) verifies too, so the Naver-style retry-until-verified
    fix can't distinguish it from the real HKEX primary listing — the
    known_ticker hint must be tried first and win whenever it verifies."""
    verification = VerificationResult(
        verified=True,
        source="yahoo_finance_search",
        checked_date="2026-08-26",
        reason="symbol and company name confirmed (score=100)",
        delisted_or_acquired=False,
        resolved_ticker=None,
    )
    with patch("signal_screener.founder_pipeline.verify_ticker", return_value=verification) as mock_verify, \
         patch("signal_screener.founder_pipeline.resolve_ticker") as mock_resolve:
        match, result = _resolve_tier2_ticker(_HK_CANDIDATE)

    mock_verify.assert_called_once_with("0700.HK", "Tencent Holdings")
    mock_resolve.assert_not_called()
    assert match == TickerMatch(
        ticker="0700.HK", matched_company_name="Tencent Holdings", confidence=100.0
    )
    assert result == verification


def test_resolve_tier2_ticker_falls_back_when_known_ticker_fails_to_verify():
    failed_verification = VerificationResult(
        verified=False,
        source="yahoo_finance_search",
        checked_date="2026-08-26",
        reason="no match found",
        delisted_or_acquired=False,
        resolved_ticker=None,
    )
    fallback_match = TickerMatch(
        ticker="TCTZF", matched_company_name="Tencent Holdings", confidence=80.0
    )
    with patch(
        "signal_screener.founder_pipeline.verify_ticker", return_value=failed_verification
    ), patch(
        "signal_screener.founder_pipeline.resolve_ticker",
        return_value=(fallback_match, failed_verification),
    ) as mock_resolve:
        match, result = _resolve_tier2_ticker(_HK_CANDIDATE)

    mock_resolve.assert_called_once_with("Tencent Holdings")
    assert match == fallback_match
    assert result == failed_verification


def test_resolve_tier2_ticker_skips_hint_lookup_when_no_known_ticker_set():
    fallback_match = TickerMatch(
        ticker="ZAL.DE", matched_company_name="Zalando", confidence=90.0
    )
    verification = VerificationResult(
        verified=True,
        source="yahoo_finance_search",
        checked_date="2026-08-26",
        reason="symbol and company name confirmed (score=100)",
        delisted_or_acquired=False,
        resolved_ticker=None,
    )
    with patch("signal_screener.founder_pipeline.verify_ticker") as mock_verify, patch(
        "signal_screener.founder_pipeline.resolve_ticker",
        return_value=(fallback_match, verification),
    ) as mock_resolve:
        match, result = _resolve_tier2_ticker(_DE_CANDIDATE)

    mock_verify.assert_not_called()
    mock_resolve.assert_called_once_with("Zalando")
    assert match == fallback_match
    assert result == verification


def test_fetch_valuation_for_returns_empty_dict_when_session_setup_failed():
    """valuation.get_session_and_crumb() returning None (the whole run's
    cookie/crumb dance failed) must degrade every candidate's valuation
    fields to Company's own None defaults, not raise or skip the
    candidate entirely — same never-block philosophy as a failed price
    fetch elsewhere in this pipeline."""
    assert _fetch_valuation_for(None, "MELI") == {}


def test_fetch_valuation_for_returns_empty_dict_when_ticker_fetch_failed():
    with patch(
        "signal_screener.founder_pipeline.valuation.fetch_valuation_metrics", return_value=None
    ):
        result = _fetch_valuation_for((object(), "crumb123"), "MELI")
    assert result == {}


def test_fetch_valuation_for_maps_metrics_to_company_kwargs():
    metrics = ValuationMetrics(
        market_cap=99317571584,
        currency="USD",
        trailing_pe=53.41,
        forward_pe=34.47,
        fifty_two_week_low=1495.0,
        fifty_two_week_high=2548.5,
        beta=1.312,
        dividend_yield_pct=None,
        as_of_date="2026-08-28",
    )
    with patch(
        "signal_screener.founder_pipeline.valuation.fetch_valuation_metrics", return_value=metrics
    ) as mock_fetch:
        result = _fetch_valuation_for((object(), "crumb123"), "MELI")

    mock_fetch.assert_called_once()
    assert result == {
        "market_cap": 99317571584,
        "currency": "USD",
        "trailing_pe": 53.41,
        "forward_pe": 34.47,
        "fifty_two_week_low": 1495.0,
        "fifty_two_week_high": 2548.5,
        "beta": 1.312,
        "dividend_yield_pct": None,
        "valuation_as_of_date": "2026-08-28",
        "valuation_source": "yahoo_finance_quotesummary",
    }


def test_fetch_backtest_for_returns_empty_dict_when_sp500_price_missing():
    """backtest.get_current_price(SP500_TICKER) returning None (the
    whole run's S&P 500 fetch failed) must degrade every candidate's
    backtest fields to Company's own None defaults, not raise or skip
    the candidate entirely."""
    assert _fetch_backtest_for(None, "MELI") == {}


def test_fetch_backtest_for_returns_empty_dict_when_compute_failed():
    with patch(
        "signal_screener.founder_pipeline.backtest.compute_backtest", return_value=None
    ):
        result = _fetch_backtest_for(7711.76, "MELI")
    assert result == {}


def test_fetch_backtest_for_maps_result_to_company_kwargs():
    result = BacktestResult(
        ipo_date="2007-08-10",
        company_ipo_price=28.5,
        company_current_price=1966.25,
        company_currency="USD",
        company_growth_multiple=69.0,
        sp500_price_at_ipo=1453.64,
        sp500_current_price=7711.76,
        sp500_growth_multiple=5.3,
        as_of_date="2026-08-28",
    )
    with patch(
        "signal_screener.founder_pipeline.backtest.compute_backtest", return_value=result
    ) as mock_compute:
        mapped = _fetch_backtest_for(7711.76, "MELI")

    mock_compute.assert_called_once_with("MELI", 7711.76)
    assert mapped == {
        "ipo_date": "2007-08-10",
        "ipo_price": 28.5,
        "backtest_current_price": 1966.25,
        "sp500_price_at_ipo": 1453.64,
        "sp500_current_price": 7711.76,
        "backtest_as_of_date": "2026-08-28",
        "backtest_source": "yahoo_finance_chart",
    }
