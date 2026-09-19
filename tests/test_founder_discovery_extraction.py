"""Tests for summarize/founder_discovery_extraction.py's never-infer
guardrail: a "detected" answer missing a name or title must never survive
as a usable candidate, even if Claude's JSON technically claims
founder_detected: true."""

import json
from unittest.mock import MagicMock, patch

from signal_screener.summarize import founder_discovery_extraction as fde


def _mock_response(payload: dict):
    block = MagicMock()
    block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [block]
    return response


def _run_with_mock_response(payload: dict):
    with patch.object(fde, "ANTHROPIC_API_KEY", "fake-key"), patch.object(
        fde.anthropic, "Anthropic"
    ) as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(payload)
        mock_anthropic_cls.return_value = mock_client
        return fde.detect_founder_leadership(
            company_name="Test Co", report_excerpt="Jane Founder is our CEO."
        )


def test_full_detection_passes_through():
    result = _run_with_mock_response(
        {
            "founder_detected": True,
            "founder_name": "Jane Founder",
            "current_title": "Chief Executive Officer",
            "ownership_pct_numeric": 12.5,
            "ownership_stake": "12.5%",
            "supporting_quote": "Jane Founder is our CEO.",
            "reasoning": "Excerpt names Jane Founder as founder and current CEO.",
        }
    )
    assert result.founder_detected is True
    assert result.founder_name == "Jane Founder"
    assert result.current_title == "Chief Executive Officer"
    assert result.ownership_pct_numeric == 12.5
    assert result.supporting_quote == "Jane Founder is our CEO."


def test_no_detection_passes_through_as_false():
    result = _run_with_mock_response(
        {
            "founder_detected": False,
            "founder_name": None,
            "current_title": None,
            "ownership_pct_numeric": None,
            "ownership_stake": "not disclosed in this excerpt",
            "reasoning": "No named founder in an active leadership role in this excerpt.",
        }
    )
    assert result.founder_detected is False
    assert result.founder_name is None
    assert result.current_title is None


def test_detected_true_but_missing_name_is_forced_false():
    """Guards against a malformed/inconsistent Claude response — this
    project's never-infer rule means a "detected" candidate must have a
    real, named person we can put in front of a human, not just a bare
    true/false flag."""
    result = _run_with_mock_response(
        {
            "founder_detected": True,
            "founder_name": None,
            "current_title": "Chief Executive Officer",
            "ownership_pct_numeric": None,
            "ownership_stake": "not disclosed in this excerpt",
            "reasoning": "malformed",
        }
    )
    assert result.founder_detected is False
    assert result.founder_name is None
    assert result.current_title is None


def test_detected_true_but_missing_title_is_forced_false():
    result = _run_with_mock_response(
        {
            "founder_detected": True,
            "founder_name": "Jane Founder",
            "current_title": None,
            "ownership_pct_numeric": None,
            "ownership_stake": "not disclosed in this excerpt",
            "reasoning": "malformed",
        }
    )
    assert result.founder_detected is False


def test_detected_true_but_missing_supporting_quote_is_forced_false():
    result = _run_with_mock_response(
        {
            "founder_detected": True,
            "founder_name": "Jane Founder",
            "current_title": "Chief Executive Officer",
            "ownership_pct_numeric": None,
            "ownership_stake": "not disclosed in this excerpt",
            "supporting_quote": None,
            "reasoning": "malformed",
        }
    )
    assert result.founder_detected is False


def test_detected_true_but_quote_not_actually_in_excerpt_is_forced_false():
    """The concrete fix for the AES Corp / Allegion false positives found
    live: the model attributing a founder claim it read in a director's
    unrelated outside-company bio (or a board skills-matrix cell) to the
    company being asked about. A supporting_quote that isn't real text
    from the excerpt it was given can't be trusted, regardless of what the
    rest of the JSON claims."""
    result = _run_with_mock_response(
        {
            "founder_detected": True,
            "founder_name": "Jane Founder",
            "current_title": "Chief Executive Officer",
            "ownership_pct_numeric": None,
            "ownership_stake": "not disclosed in this excerpt",
            "supporting_quote": "Jane Founder, Founder and CEO of Some Other Company",
            "reasoning": "hallucinated — not present in the actual excerpt text",
        }
    )
    assert result.founder_detected is False
    assert result.founder_name is None


def test_supporting_quote_matches_despite_whitespace_differences():
    """A quote that's a real substring of the excerpt once whitespace is
    normalized (e.g. the model collapses a line-wrapped quote) must still
    be accepted — the grounding check isn't meant to be defeated by
    incidental spacing, only by a quote that isn't really there."""
    result = _run_with_mock_response(
        {
            "founder_detected": True,
            "founder_name": "Jane Founder",
            "current_title": "Chief Executive Officer",
            "ownership_pct_numeric": None,
            "ownership_stake": "not disclosed in this excerpt",
            "supporting_quote": "Jane   Founder is  our CEO.",
            "reasoning": "grounded",
        }
    )
    assert result.founder_detected is True


def test_missing_api_key_raises():
    with patch.object(fde, "ANTHROPIC_API_KEY", None):
        try:
            fde.detect_founder_leadership(company_name="Test Co", report_excerpt="text")
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
