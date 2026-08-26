from unittest.mock import patch

from signal_screener.founder_pipeline import _apply_recency_rule, _effective_transition_date
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
