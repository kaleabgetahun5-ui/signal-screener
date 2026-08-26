from unittest.mock import patch

from signal_screener.founder_pipeline import (
    _apply_recency_rule,
    _effective_transition_date,
    _resolve_tier2_ticker,
)
from signal_screener.matching.ticker_match import TickerMatch
from signal_screener.matching.ticker_verify import VerificationResult
from signal_screener.sources.founder_led_tier2 import Tier2Candidate


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
